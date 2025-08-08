import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import htcondor
from collections import defaultdict
import sqlite3
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTCondorDataFrameManager:
    """
    Manages a comprehensive dataframe of HTCondor data for efficient querying
    and analysis without LLM input limitations.
    """
    
    def __init__(self, db_path: str = "htcondor_data.db"):
        self.db_path = db_path
        self.jobs_df = None
        self.machines_df = None
        self.pools_df = None
        self.last_update = None
        self.update_interval = timedelta(minutes=5)  # Update every 5 minutes
        
    def _serialize_ad(self, ad) -> Dict[str, Any]:
        """Serialize HTCondor ClassAd to dictionary."""
        result = {}
        for key in ad.keys():
            try:
                value = ad[key]
                if hasattr(value, 'eval'):
                    try:
                        value = value.eval()
                    except Exception:
                        # If eval fails, try to get string representation
                        try:
                            value = str(value)
                        except Exception:
                            value = None
                result[key.lower()] = value
            except Exception as e:
                logger.warning(f"Error serializing {key}: {e}")
                result[key.lower()] = None
        return result
    
    def _get_jobs_data(self) -> List[Dict[str, Any]]:
        """Fetch all job data from HTCondor."""
        try:
            schedd = htcondor.Schedd()
            
            # Start with basic attributes that are more likely to work
            basic_attrs = ["ClusterId", "ProcId", "JobStatus", "Owner", "QDate"]
            
            try:
                # Try with basic attributes first
                jobs = schedd.query("True", projection=basic_attrs)
                logger.info(f"Successfully fetched {len(jobs)} jobs with basic attributes")
                return [self._serialize_ad(job) for job in jobs]
            except Exception as e:
                logger.warning(f"Basic job query failed: {e}")
                
                # Fallback: try with minimal attributes
                try:
                    jobs = schedd.query("True", projection=["ClusterId", "JobStatus"])
                    logger.info(f"Successfully fetched {len(jobs)} jobs with minimal attributes")
                    return [self._serialize_ad(job) for job in jobs]
                except Exception as e2:
                    logger.error(f"Minimal job query also failed: {e2}")
                    return []
            
        except Exception as e:
            logger.error(f"Error fetching jobs data: {e}")
            return []
    
    def _get_machines_data(self) -> List[Dict[str, Any]]:
        """Fetch all machine data from HTCondor."""
        try:
            collector = htcondor.Collector()
            
            # Start with basic machine attributes
            basic_attrs = ["Name", "Machine", "State", "Activity", "LoadAvg", "Cpus", "Memory"]
            
            try:
                # Try with basic attributes first
                machines = collector.query(htcondor.AdTypes.Startd, "True", projection=basic_attrs)
                logger.info(f"Successfully fetched {len(machines)} machines with basic attributes")
                return [self._serialize_ad(machine) for machine in machines]
            except Exception as e:
                logger.warning(f"Basic machine query failed: {e}")
                
                # Fallback: try with minimal attributes
                try:
                    machines = collector.query(htcondor.AdTypes.Startd, "True", projection=["Name", "State"])
                    logger.info(f"Successfully fetched {len(machines)} machines with minimal attributes")
                    return [self._serialize_ad(machine) for machine in machines]
                except Exception as e2:
                    logger.error(f"Minimal machine query also failed: {e2}")
                    return []
            
        except Exception as e:
            logger.error(f"Error fetching machines data: {e}")
            return []
    
    def _get_pools_data(self) -> List[Dict[str, Any]]:
        """Fetch pool information."""
        try:
            collector = htcondor.Collector()
            pools = collector.query(htcondor.AdTypes.Negotiator, "True")
            return [self._serialize_ad(pool) for pool in pools]
        except Exception as e:
            logger.error(f"Error fetching pools data: {e}")
            return []
    
    def update_dataframe(self, force_update: bool = False) -> Dict[str, Any]:
        """
        Update the comprehensive dataframe with fresh HTCondor data.
        
        Args:
            force_update: If True, update regardless of time interval
            
        Returns:
            Dict with update status and statistics
        """
        try:
            # Check if update is needed
            if not force_update and self.last_update:
                if datetime.now() - self.last_update < self.update_interval:
                    return {
                        "success": True,
                        "message": "Data is up to date",
                        "last_update": self.last_update.isoformat(),
                        "jobs_count": len(self.jobs_df) if self.jobs_df is not None else 0,
                        "machines_count": len(self.machines_df) if self.machines_df is not None else 0
                    }
            
            logger.info("Updating HTCondor dataframe...")
            
            # Fetch fresh data
            jobs_data = self._get_jobs_data()
            machines_data = self._get_machines_data()
            pools_data = self._get_pools_data()
            
            # Convert to DataFrames
            self.jobs_df = pd.DataFrame(jobs_data) if jobs_data else pd.DataFrame()
            self.machines_df = pd.DataFrame(machines_data) if machines_data else pd.DataFrame()
            self.pools_df = pd.DataFrame(pools_data) if pools_data else pd.DataFrame()
            
            # Add computed columns with better error handling
            if not self.jobs_df.empty:
                try:
                    # Handle numeric conversions more safely
                    for col_name, source_col in [
                        ('job_duration', 'committedtime'),
                        ('cpu_time', 'remoteusercpu'),
                        ('memory_usage', 'memoryusage')
                    ]:
                        if source_col in self.jobs_df.columns:
                            # Convert to string first, then to numeric to handle expressions
                            self.jobs_df[col_name] = pd.to_numeric(
                                self.jobs_df[source_col].astype(str).str.extract(r'(\d+\.?\d*)')[0], 
                                errors='coerce'
                            )
                        else:
                            self.jobs_df[col_name] = 0.0
                    
                    # Handle datetime conversions
                    for col_name, source_col in [
                        ('qdate_dt', 'qdate'),
                        ('completion_date_dt', 'completiondate')
                    ]:
                        if source_col in self.jobs_df.columns:
                            # Convert to string first, then to datetime
                            self.jobs_df[col_name] = pd.to_datetime(
                                pd.to_numeric(self.jobs_df[source_col].astype(str).str.extract(r'(\d+)')[0], errors='coerce'),
                                unit='s', 
                                errors='coerce'
                            )
                        else:
                            self.jobs_df[col_name] = pd.NaT
                except Exception as e:
                    logger.warning(f"Error adding computed columns to jobs: {e}")
            
            if not self.machines_df.empty:
                try:
                    # Handle numeric conversions for machines
                    for col_name, source_col in [
                        ('total_cpus', 'totalcpus'),
                        ('total_memory', 'totalmemory'),
                        ('load_avg', 'loadavg')
                    ]:
                        if source_col in self.machines_df.columns:
                            # Convert to string first, then to numeric to handle expressions
                            self.machines_df[col_name] = pd.to_numeric(
                                self.machines_df[source_col].astype(str).str.extract(r'(\d+\.?\d*)')[0], 
                                errors='coerce'
                            )
                        else:
                            self.machines_df[col_name] = 0.0
                except Exception as e:
                    logger.warning(f"Error adding computed columns to machines: {e}")
            
            self.last_update = datetime.now()
            
            # Save to SQLite for persistence
            self._save_to_sqlite()
            
            return {
                "success": True,
                "message": "Dataframe updated successfully",
                "last_update": self.last_update.isoformat(),
                "jobs_count": len(self.jobs_df),
                "machines_count": len(self.machines_df),
                "pools_count": len(self.pools_df),
                "jobs_columns": list(self.jobs_df.columns) if not self.jobs_df.empty else [],
                "machines_columns": list(self.machines_df.columns) if not self.machines_df.empty else []
            }
            
        except Exception as e:
            logger.error(f"Error updating dataframe: {e}")
            return {
                "success": False,
                "message": f"Error updating dataframe: {str(e)}"
            }
    
    def _save_to_sqlite(self):
        """Save dataframes to SQLite for persistence."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if not self.jobs_df.empty:
                    self.jobs_df.to_sql('jobs', conn, if_exists='replace', index=False)
                if not self.machines_df.empty:
                    self.machines_df.to_sql('machines', conn, if_exists='replace', index=False)
                if not self.pools_df.empty:
                    self.pools_df.to_sql('pools', conn, if_exists='replace', index=False)
        except Exception as e:
            logger.error(f"Error saving to SQLite: {e}")
    
    def _load_from_sqlite(self):
        """Load dataframes from SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                self.jobs_df = pd.read_sql('SELECT * FROM jobs', conn) if 'jobs' in [table[0] for table in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else pd.DataFrame()
                self.machines_df = pd.read_sql('SELECT * FROM machines', conn) if 'machines' in [table[0] for table in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else pd.DataFrame()
                self.pools_df = pd.read_sql('SELECT * FROM pools', conn) if 'pools' in [table[0] for table in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading from SQLite: {e}")
    
    def get_jobs_summary(self, owner: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for jobs."""
        if self.jobs_df is None or self.jobs_df.empty:
            return {"success": False, "message": "No job data available"}
        
        try:
            df = self.jobs_df.copy()
            
            # Apply filters
            if owner:
                df = df[df['owner'].str.lower() == owner.lower()]
            if status:
                status_map = {"running": 2, "idle": 1, "held": 5, "completed": 4, "removed": 3}
                status_code = status_map.get(status.lower())
                if status_code is not None:
                    df = df[df['jobstatus'] == status_code]
            
            if df.empty:
                return {"success": True, "message": "No jobs match the criteria", "summary": {}}
            
            # Calculate statistics
            summary = {
                "total_jobs": len(df),
                "status_distribution": df['jobstatus'].value_counts().to_dict(),
                "owners": df['owner'].value_counts().to_dict(),
                "total_cpu_time": float(df['cpu_time'].sum()),
                "total_memory_usage": float(df['memory_usage'].sum()),
                "average_cpu_per_job": float(df['cpu_time'].mean()),
                "average_memory_per_job": float(df['memory_usage'].mean()),
                "oldest_job_date": df['qdate_dt'].min().isoformat() if 'qdate_dt' in df.columns else None,
                "newest_job_date": df['qdate_dt'].max().isoformat() if 'qdate_dt' in df.columns else None
            }
            
            return {"success": True, "summary": summary}
            
        except Exception as e:
            return {"success": False, "message": f"Error generating summary: {str(e)}"}
    
    def get_job_details(self, cluster_id: int, proc_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed information for specific job(s)."""
        if self.jobs_df is None or self.jobs_df.empty:
            return {"success": False, "message": "No job data available"}
        
        try:
            df = self.jobs_df[self.jobs_df['clusterid'] == cluster_id]
            
            if proc_id is not None:
                df = df[df['procid'] == proc_id]
            
            if df.empty:
                return {"success": False, "message": f"No job found with cluster_id={cluster_id}"}
            
            # Convert to list of dictionaries
            jobs = df.to_dict('records')
            
            return {
                "success": True,
                "jobs": jobs,
                "count": len(jobs)
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error getting job details: {str(e)}"}
    
    def get_machines_summary(self, status: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for machines."""
        if self.machines_df is None or self.machines_df.empty:
            return {"success": False, "message": "No machine data available"}
        
        try:
            df = self.machines_df.copy()
            
            if status:
                df = df[df['state'].str.lower() == status.lower()]
            
            if df.empty:
                return {"success": True, "message": "No machines match the criteria", "summary": {}}
            
            summary = {
                "total_machines": len(df),
                "state_distribution": df['state'].value_counts().to_dict(),
                "activity_distribution": df['activity'].value_counts().to_dict(),
                "total_cpus": float(df['total_cpus'].sum()),
                "total_memory": float(df['total_memory'].sum()),
                "average_load": float(df['load_avg'].mean()),
                "operating_systems": df['opsys'].value_counts().to_dict() if 'opsys' in df.columns else {}
            }
            
            return {"success": True, "summary": summary}
            
        except Exception as e:
            return {"success": False, "message": f"Error generating machine summary: {str(e)}"}
    
    def search_jobs(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """Search jobs using various criteria."""
        if self.jobs_df is None or self.jobs_df.empty:
            return {"success": False, "message": "No job data available"}
        
        try:
            df = self.jobs_df.copy()
            
            # Convert all columns to string for searching
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            # Search across all columns
            mask = df.apply(lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1)
            results = df[mask].head(limit)
            
            return {
                "success": True,
                "results": results.to_dict('records'),
                "count": len(results),
                "query": query
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error searching jobs: {str(e)}"}
    
    def get_utilization_stats(self, time_range: str = "24h") -> Dict[str, Any]:
        """Get resource utilization statistics."""
        if self.jobs_df is None or self.jobs_df.empty:
            return {"success": False, "message": "No job data available"}
        
        try:
            df = self.jobs_df.copy()
            
            # Filter by time range
            if time_range == "24h":
                cutoff = datetime.now() - timedelta(hours=24)
            elif time_range == "7d":
                cutoff = datetime.now() - timedelta(days=7)
            elif time_range == "30d":
                cutoff = datetime.now() - timedelta(days=30)
            else:
                cutoff = datetime.now() - timedelta(hours=24)  # default to 24h
            
            if 'qdate_dt' in df.columns:
                df = df[df['qdate_dt'] >= cutoff]
            
            if df.empty:
                return {"success": True, "message": "No jobs in specified time range", "stats": {}}
            
            stats = {
                "time_range": time_range,
                "total_jobs": len(df),
                "completed_jobs": len(df[df['jobstatus'] == 4]),
                "failed_jobs": len(df[df['jobstatus'] == 3]),
                "total_cpu_time": float(df['cpu_time'].sum()),
                "total_memory_usage": float(df['memory_usage'].sum()),
                "average_job_duration": float(df['job_duration'].mean()),
                "cpu_efficiency": float(df['cpu_time'].sum() / df['job_duration'].sum()) if df['job_duration'].sum() > 0 else 0,
                "top_owners": df['owner'].value_counts().head(10).to_dict()
            }
            
            return {"success": True, "stats": stats}
            
        except Exception as e:
            return {"success": False, "message": f"Error calculating utilization stats: {str(e)}"}
    
    def export_data(self, data_type: str = "jobs", format: str = "json", filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Export data in various formats."""
        try:
            if data_type == "jobs":
                df = self.jobs_df
            elif data_type == "machines":
                df = self.machines_df
            elif data_type == "pools":
                df = self.pools_df
            else:
                return {"success": False, "message": f"Unknown data type: {data_type}"}
            
            if df is None or df.empty:
                return {"success": False, "message": f"No {data_type} data available"}
            
            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    if key in df.columns:
                        df = df[df[key] == value]
            
            if df.empty:
                return {"success": True, "message": "No data matches filters", "data": []}
            
            if format.lower() == "json":
                data = df.to_dict('records')
            elif format.lower() == "csv":
                data = df.to_csv(index=False)
            elif format.lower() == "summary":
                data = {
                    "total_records": len(df),
                    "columns": list(df.columns),
                    "sample_data": df.head(5).to_dict('records')
                }
            else:
                return {"success": False, "message": f"Unsupported format: {format}"}
            
            return {
                "success": True,
                "data_type": data_type,
                "format": format,
                "total_records": len(df),
                "data": data
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error exporting data: {str(e)}"}
    
    def get_dataframe_info(self) -> Dict[str, Any]:
        """Get information about the current dataframe state."""
        return {
            "success": True,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "jobs_count": len(self.jobs_df) if self.jobs_df is not None else 0,
            "machines_count": len(self.machines_df) if self.machines_df is not None else 0,
            "pools_count": len(self.pools_df) if self.pools_df is not None else 0,
            "jobs_columns": list(self.jobs_df.columns) if self.jobs_df is not None and not self.jobs_df.empty else [],
            "machines_columns": list(self.machines_df.columns) if self.machines_df is not None and not self.machines_df.empty else [],
            "pools_columns": list(self.pools_df.columns) if self.pools_df is not None and not self.pools_df.empty else []
        }

# Global instance
dataframe_manager = HTCondorDataFrameManager()
