#!/usr/bin/env python3
"""
HTCondor Comprehensive DataFrame Tool
Retrieves all job data from both condor_q and condor_history
"""

import htcondor
import pandas as pd
import numpy as np
import subprocess
import datetime
import time
import logging
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTCondorDataFrame:
    """Comprehensive HTCondor job data management using pandas DataFrame"""
    
    def __init__(self):
        self.df = None
        self.last_update = None
        self.update_interval = 300  # 5 minutes default
        self.schedd = htcondor.Schedd()
        
        # Define comprehensive job attributes
        self.job_attributes = [
            # Basic job info
            "ClusterId", "ProcId", "JobStatus", "Owner", "Cmd", "Arguments",
            "Iwd", "JobUniverse", "Requirements", "Rank",
            
            # Timing information
            "QDate", "JobStartDate", "JobCurrentStartDate", "CompletionDate",
            "LastMatchTime", "LastSuspensionTime", "LastJobLeaseRenewal",
            "LastJobStatusUpdate", "LastJobStatusUpdateTime",
            
            # Resource usage
            "RemoteUserCpu", "RemoteSysCpu", "ImageSize", "MemoryUsage", 
            "DiskUsage", "CommittedTime", "WallClockCheckpoint",
            
            # Resource requests
            "RequestCpus", "RequestMemory", "RequestDisk", "RequestGpus",
            
            # Job execution info
            "NumJobStarts", "NumJobReconnects", "NumJobReleases", 
            "NumJobMatches", "NumJobMatchesRejected", "NumJobMatchesRejectedTotal",
            "JobPrio", "NiceUser",
            
            # Exit information
            "ExitStatus", "ExitCode", "ExitBySignal", "ExitSignal",
            
            # File information
            "In", "Out", "Err", "UserLog", "TransferIn", "TransferOut",
            
            # Machine information
            "RemoteHost", "RemoteSlotID", "RemoteUserCpu", "RemoteSysCpu",
            
            # Additional metadata
            "JobDescription", "JobLeaseDuration", "JobLeaseRenewalTime",
            "JobLeaseRenewalTime", "JobLeaseRenewalTime", "JobLeaseRenewalTime"
        ]
    
    def get_current_queue_jobs(self) -> List[Dict]:
        """Get jobs from current queue using schedd.query()"""
        logger.info("Retrieving current queue jobs...")
        
        try:
            # Query all jobs in current queue
            jobs = self.schedd.query("True", projection=self.job_attributes)
            
            job_data = []
            for ad in jobs:
                job_info = {}
                for attr in self.job_attributes:
                    v = ad.get(attr)
                    if hasattr(v, "eval"):
                        try:
                            v = v.eval()
                        except Exception:
                            v = None
                    job_info[attr.lower()] = v
                
                # Add data source indicator
                job_info['data_source'] = 'current_queue'
                job_info['retrieved_at'] = datetime.datetime.now().isoformat()
                
                job_data.append(job_info)
            
            logger.info(f"Retrieved {len(job_data)} jobs from current queue")
            return job_data
            
        except Exception as e:
            logger.error(f"Error retrieving current queue jobs: {e}")
            return []
    
    def get_historical_jobs(self, time_range: Optional[str] = None) -> List[Dict]:
        """Get jobs from history using HTCondor Python API"""
        logger.info("Retrieving historical jobs using Python API...")
        
        try:
            # Use HTCondor Python API to get historical jobs
            schedd = htcondor.Schedd()
            
            # Build constraint for time range if specified
            constraint = None
            if time_range:
                # Convert time range to constraint
                # For now, we'll get all history and filter later
                logger.info(f"Time range specified: {time_range} (will be applied in filtering)")
            
            # Get historical jobs with all attributes
            logger.info("Querying historical jobs from schedd...")
            historical_jobs = schedd.history(
                constraint=constraint,
                match=5000,  # Get up to 5,000 jobs (reduced from 10,000 to prevent timeout)
                projection=self.job_attributes
            )
            
            job_data = []
            for job in historical_jobs:
                try:
                    # Convert ClassAd to dictionary
                    job_info = {}
                    for attr in self.job_attributes:
                        if attr in job:
                            value = job[attr]
                            # Handle ClassAd values
                            if hasattr(value, 'eval'):
                                try:
                                    job_info[attr.lower()] = value.eval()
                                except Exception:
                                    job_info[attr.lower()] = str(value.eval())
                            else:
                                job_info[attr.lower()] = value
                        else:
                            job_info[attr.lower()] = None
                    
                    # Add data source indicator
                    job_info['data_source'] = 'history'
                    job_info['retrieved_at'] = datetime.datetime.now().isoformat()
                    
                    job_data.append(job_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to process historical job: {e}")
                    continue
            
            logger.info(f"Retrieved {len(job_data)} jobs from history using Python API")
            return job_data
            
        except Exception as e:
            logger.error(f"Error retrieving historical jobs using Python API: {e}")
            logger.info("Falling back to command-line approach...")
            
            # Fallback to command-line approach if API fails
            return self._get_historical_jobs_fallback(time_range)
    
    def _get_historical_jobs_fallback(self, time_range: Optional[str] = None) -> List[Dict]:
        """Fallback method using condor_history command"""
        logger.info("Using fallback condor_history command...")
        
        try:
            # Build condor_history command to get full output
            cmd = ["condor_history"]
            
            if time_range:
                cmd.extend(["-since", time_range])
            
            # Execute command with increased timeout
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # Increased from 120 to 300 seconds to prevent timeout errors
            
            if result.returncode != 0:
                logger.error(f"condor_history command failed: {result.stderr}")
                return []
            
            # Parse output - full history format
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            if lines and 'ID' in lines[0] and 'OWNER' in lines[0]:
                lines = lines[1:]
            
            job_data = []
            for line in lines:
                if not line.strip():
                    continue
                
                try:
                    # Parse the full history line format:
                    # ID     OWNER          SUBMITTED   RUN_TIME     ST COMPLETED   CMD
                    # 6820169.0 selbor          8/12 12:00   0+01:01:33 C   8/12 13:01 /home/selbor/...
                    
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    
                    # Extract job ID (format: clusterid.procid)
                    job_id_parts = parts[0].split('.')
                    cluster_id = int(job_id_parts[0])
                    proc_id = int(job_id_parts[1]) if len(job_id_parts) > 1 else 0
                    
                    # Extract owner
                    owner = parts[1]
                    
                    # Extract status (ST column)
                    status_char = parts[4]
                    status_map = {
                        'C': 4,  # Completed
                        'X': 3,  # Removed
                        'H': 5,  # Held
                        'S': 7,  # Suspended
                        'I': 1,  # Idle
                        'R': 2,  # Running
                        'T': 6   # Transferring
                    }
                    job_status = status_map.get(status_char, 0)
                    
                    # Extract timestamps and runtime
                    submitted = parts[2] + ' ' + parts[3]  # "8/12 12:00"
                    run_time = parts[5]  # "0+01:01:33"
                    
                    # Parse completion time if available
                    completed = None
                    cmd_start_idx = 6
                    if len(parts) > 6 and parts[6] != 'X':
                        completed = parts[6] + ' ' + parts[7]  # "8/12 13:01"
                        cmd_start_idx = 8
                    
                    # Extract command (everything after completion time)
                    cmd = ' '.join(parts[cmd_start_idx:]) if len(parts) > cmd_start_idx else None
                    
                    # Create job info
                    job_info = {
                        'clusterid': cluster_id,
                        'procid': proc_id,
                        'owner': owner,
                        'jobstatus': job_status,
                        'status_description': status_char,
                        'submitted_str': submitted,
                        'run_time_str': run_time,
                        'completed_str': completed,
                        'cmd': cmd,
                        'data_source': 'history',
                        'retrieved_at': datetime.datetime.now().isoformat()
                    }
                    
                    # Try to parse timestamps
                    try:
                        # Convert submitted time to timestamp
                        # Format: "8/12 12:00" -> need to add year and convert
                        import datetime as dt
                        current_year = dt.datetime.now().year
                        submitted_parts = submitted.split()
                        if len(submitted_parts) == 2:
                            date_part, time_part = submitted_parts
                            month, day = map(int, date_part.split('/'))
                            hour, minute = map(int, time_part.split(':'))
                            submitted_dt = dt.datetime(current_year, month, day, hour, minute)
                            job_info['qdate'] = int(submitted_dt.timestamp())
                        
                        # Convert completion time if available
                        if completed:
                            completed_parts = completed.split()
                            if len(completed_parts) == 2:
                                date_part, time_part = completed_parts
                                month, day = map(int, date_part.split('/'))
                                hour, minute = map(int, time_part.split(':'))
                                completed_dt = dt.datetime(current_year, month, day, hour, minute)
                                job_info['completiondate'] = int(completed_dt.timestamp())
                    except Exception as e:
                        logger.debug(f"Failed to parse timestamps for job {cluster_id}: {e}")
                    
                    # Parse runtime
                    try:
                        # Format: "0+01:01:33" -> days+hours:minutes:seconds
                        if '+' in run_time:
                            days_part, time_part = run_time.split('+')
                            days = int(days_part)
                            hours, minutes, seconds = map(int, time_part.split(':'))
                            total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
                            job_info['runtime_seconds'] = total_seconds
                            job_info['runtime_minutes'] = total_seconds / 60
                            job_info['runtime_hours'] = total_seconds / 3600
                    except Exception as e:
                        logger.debug(f"Failed to parse runtime for job {cluster_id}: {e}")
                    
                    job_data.append(job_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse history line: {line[:100]}... Error: {e}")
                    continue
            
            logger.info(f"Retrieved {len(job_data)} jobs from history using fallback method")
            return job_data
            
        except subprocess.TimeoutExpired:
            logger.error("condor_history command timed out")
            return []
        except Exception as e:
            logger.error(f"Error retrieving historical jobs: {e}")
            return []
    
    def get_all_jobs(self, time_range: Optional[str] = None, force_update: bool = False) -> pd.DataFrame:
        """Get all jobs (current queue + history) as DataFrame"""
        
        # Check if update is needed
        if (not force_update and self.df is not None and 
            self.last_update and 
            (datetime.datetime.now() - self.last_update).seconds < self.update_interval):
            logger.info("Using cached DataFrame")
            return self.df
        
        logger.info("Building comprehensive job DataFrame...")
        
        # Get current queue jobs
        current_jobs = self.get_current_queue_jobs()
        
        # Get historical jobs
        historical_jobs = self.get_historical_jobs(time_range)
        
        # Combine all jobs
        all_jobs = current_jobs + historical_jobs
        
        if not all_jobs:
            logger.warning("No jobs found")
            return pd.DataFrame()
        
        # Clean and convert data before creating DataFrame
        cleaned_jobs = self._clean_job_data(all_jobs)
        
        # Convert to DataFrame safely
        self.df = self._create_dataframe_safely(cleaned_jobs)
        
        # Add computed columns
        self.df = self.add_computed_columns(self.df)
        
        # Update timestamp
        self.last_update = datetime.datetime.now()
        
        logger.info(f"Created DataFrame with {len(self.df)} jobs")
        return self.df
    
    def _clean_job_data(self, jobs: List[Dict]) -> List[Dict]:
        """Clean and convert job data to handle ClassAd values"""
        cleaned_jobs = []
        
        for job in jobs:
            cleaned_job = {}
            for key, value in job.items():
                try:
                    # Handle ClassAd values and convert to appropriate types
                    if hasattr(value, 'eval'):  # ClassAd expression
                        try:
                            # Try to evaluate as number
                            cleaned_value = float(value.eval())
                        except (ValueError, TypeError):
                            # If not numeric, get string representation
                            cleaned_value = str(value.eval())
                    elif isinstance(value, (int, float, str, bool)):
                        cleaned_value = value
                    elif value is None:
                        cleaned_value = None
                    else:
                        # Convert other types to string
                        cleaned_value = str(value)
                    
                    cleaned_job[key] = cleaned_value
                except Exception as e:
                    # If conversion fails, use string representation
                    logger.warning(f"Failed to convert {key}={value}: {e}")
                    cleaned_job[key] = str(value) if value is not None else None
            
            cleaned_jobs.append(cleaned_job)
        
        return cleaned_jobs
    
    def _create_dataframe_safely(self, jobs: List[Dict]) -> pd.DataFrame:
        """Create DataFrame with explicit handling of problematic data types"""
        if not jobs:
            return pd.DataFrame()
        
        # First, ensure all values are basic Python types
        safe_jobs = []
        for job in jobs:
            safe_job = {}
            for key, value in job.items():
                # Convert all values to strings first to avoid pandas conversion issues
                if value is None:
                    safe_job[key] = None
                else:
                    safe_job[key] = str(value)
            safe_jobs.append(safe_job)
        
        # Create DataFrame with object dtype to avoid automatic type conversion
        df = pd.DataFrame(safe_jobs, dtype=object)
        
        # Now convert numeric columns back to appropriate types
        numeric_columns = ['clusterid', 'procid', 'jobstatus', 'qdate', 'jobstartdate', 
                          'jobcurrentstartdate', 'completiondate', 'requestcpus', 
                          'requestmemory', 'remotesusercpu', 'memoryusage', 'jobprio',
                          'exitcode', 'exitsignal']
        
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # Convert to numeric, coercing errors to NaN
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except Exception as e:
                    logger.warning(f"Failed to convert column {col} to numeric: {e}")
        
        return df
    
    def add_computed_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add computed columns to the DataFrame"""
        
        # Convert timestamps to datetime with safe handling
        timestamp_columns = ['qdate', 'jobstartdate', 'jobcurrentstartdate', 'completiondate']
        for col in timestamp_columns:
            if col in df.columns:
                try:
                    # Filter out invalid timestamp values
                    valid_timestamps = df[col].dropna()
                    if len(valid_timestamps) > 0:
                        # Check for reasonable timestamp range (1970-2030)
                        min_valid = 0  # Unix epoch start
                        max_valid = 2000000000  # ~2033
                        
                        # Filter out extreme values that could cause overflow
                        valid_mask = (valid_timestamps >= min_valid) & (valid_timestamps <= max_valid)
                        
                        # Additional safety check for very large values
                        if valid_timestamps.max() > 1e12:  # If timestamps are in milliseconds
                            valid_mask = valid_mask & (valid_timestamps <= 1e12)
                            # Convert milliseconds to seconds
                            df[f'{col}_datetime'] = pd.to_datetime(
                                (df[col].where(valid_mask) / 1000).astype(float), 
                                unit='s', 
                                errors='coerce'
                            )
                        else:
                            df[f'{col}_datetime'] = pd.to_datetime(
                                df[col].where(valid_mask), 
                                unit='s', 
                                errors='coerce'
                            )
                    else:
                        df[f'{col}_datetime'] = pd.NaT
                except Exception as e:
                    logger.warning(f"Failed to convert timestamps for column {col}: {e}")
                    df[f'{col}_datetime'] = pd.NaT
        
        # Calculate wait time with safe handling
        if 'qdate' in df.columns and 'jobstartdate' in df.columns:
            try:
                # Only calculate for valid timestamp pairs
                valid_mask = df['qdate'].notna() & df['jobstartdate'].notna()
                df['wait_time_seconds'] = np.where(
                    valid_mask,
                    df['jobstartdate'] - df['qdate'],
                    np.nan
                )
                df['wait_time_minutes'] = df['wait_time_seconds'] / 60
                df['wait_time_hours'] = df['wait_time_seconds'] / 3600
            except Exception as e:
                logger.warning(f"Failed to calculate wait times: {e}")
                df['wait_time_seconds'] = np.nan
                df['wait_time_minutes'] = np.nan
                df['wait_time_hours'] = np.nan
        
        # Calculate runtime with safe handling
        if 'jobstartdate' in df.columns and 'completiondate' in df.columns:
            try:
                # Only calculate for valid timestamp pairs
                valid_mask = df['jobstartdate'].notna() & df['completiondate'].notna()
                df['runtime_seconds'] = np.where(
                    valid_mask,
                    df['completiondate'] - df['jobstartdate'],
                    np.nan
                )
                df['runtime_minutes'] = df['runtime_seconds'] / 60
                df['runtime_hours'] = df['runtime_seconds'] / 3600
            except Exception as e:
                logger.warning(f"Failed to calculate runtime: {e}")
                df['runtime_seconds'] = np.nan
                df['runtime_minutes'] = np.nan
                df['runtime_hours'] = np.nan
        
        # Add status descriptions
        status_map = {
            1: 'Idle', 2: 'Running', 3: 'Removed', 4: 'Completed',
            5: 'Held', 6: 'Transferring Output', 7: 'Suspended'
        }
        df['status_description'] = df['jobstatus'].map(status_map)
        
        # Add success/failure indicators
        df['is_successful'] = df['jobstatus'] == 4
        df['is_failed'] = df['jobstatus'].isin([3, 5, 7])
        
        # Add resource efficiency
        if 'requestcpus' in df.columns and 'remotesusercpu' in df.columns:
            df['cpu_efficiency'] = df['remotesusercpu'] / df['requestcpus']
        
        if 'requestmemory' in df.columns and 'memoryusage' in df.columns:
            df['memory_efficiency'] = df['memoryusage'] / df['requestmemory']
        
        return df
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics from the DataFrame"""
        if self.df is None or len(self.df) == 0:
            return {}
        
        stats = {
            'total_jobs': len(self.df),
            'current_queue_jobs': len(self.df[self.df['data_source'] == 'current_queue']),
            'historical_jobs': len(self.df[self.df['data_source'] == 'history']),
            'successful_jobs': len(self.df[self.df['is_successful'] == True]),
            'failed_jobs': len(self.df[self.df['is_failed'] == True]),
            'success_rate': (len(self.df[self.df['is_successful'] == True]) / len(self.df)) * 100,
            'unique_owners': self.df['owner'].nunique(),
            'date_range': {
                'earliest': self.df['qdate_datetime'].min().isoformat() if 'qdate_datetime' in self.df.columns else None,
                'latest': self.df['qdate_datetime'].max().isoformat() if 'qdate_datetime' in self.df.columns else None
            }
        }
        
        return stats
    
    def filter_jobs(self, filters: Dict) -> pd.DataFrame:
        """Filter jobs based on criteria"""
        if self.df is None:
            return pd.DataFrame()
        
        filtered_df = self.df.copy()
        
        for key, value in filters.items():
            if key in filtered_df.columns:
                if isinstance(value, (list, tuple)):
                    filtered_df = filtered_df[filtered_df[key].isin(value)]
                else:
                    filtered_df = filtered_df[filtered_df[key] == value]
        
        return filtered_df
    
    def get_job_by_cluster(self, cluster_id: int) -> pd.DataFrame:
        """Get specific job by cluster ID"""
        if self.df is None:
            return pd.DataFrame()
        
        return self.df[self.df['clusterid'] == cluster_id]
    
    def export_to_csv(self, filename: str, filters: Optional[Dict] = None):
        """Export DataFrame to CSV"""
        if self.df is None:
            logger.error("No DataFrame to export")
            return
        
        df_to_export = self.filter_jobs(filters) if filters else self.df
        df_to_export.to_csv(filename, index=False)
        logger.info(f"Exported {len(df_to_export)} jobs to {filename}")
    
    def get_recent_jobs(self, hours: int = 24) -> pd.DataFrame:
        """Get jobs from the last N hours"""
        if self.df is None or 'qdate_datetime' not in self.df.columns:
            return pd.DataFrame()
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        return self.df[self.df['qdate_datetime'] >= cutoff_time]

def main():
    """Test the HTCondorDataFrame functionality"""
    
    print("=== HTCondor Comprehensive DataFrame Test ===\n")
    
    # Create DataFrame instance
    htcondor_df = HTCondorDataFrame()
    
    # Get all jobs
    print("📊 Retrieving all job data...")
    df = htcondor_df.get_all_jobs()
    
    if len(df) == 0:
        print("❌ No jobs found")
        return
    
    print(f"✅ Retrieved {len(df)} total jobs")
    
    # Get summary statistics
    stats = htcondor_df.get_summary_stats()
    print(f"\n📈 Summary Statistics:")
    print(f"   Total jobs: {stats['total_jobs']}")
    print(f"   Current queue: {stats['current_queue_jobs']}")
    print(f"   Historical: {stats['historical_jobs']}")
    print(f"   Successful: {stats['successful_jobs']}")
    print(f"   Failed: {stats['failed_jobs']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    print(f"   Unique owners: {stats['unique_owners']}")
    
    # Show DataFrame info
    print(f"\n📋 DataFrame Info:")
    print(f"   Shape: {df.shape}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    
    # Show sample data
    print(f"\n📄 Sample Data (first 5 rows):")
    print(df.head().to_string())
    
    # Show column names
    print(f"\n🔍 Available Columns:")
    for i, col in enumerate(df.columns, 1):
        print(f"   {i:2d}. {col}")
    
    # Test filtering
    print(f"\n🔍 Testing Filters:")
    
    # Filter by status
    running_jobs = htcondor_df.filter_jobs({'jobstatus': 2})
    print(f"   Running jobs: {len(running_jobs)}")
    
    # Filter by owner (if available)
    if 'owner' in df.columns and len(df['owner'].unique()) > 0:
        sample_owner = df['owner'].iloc[0]
        owner_jobs = htcondor_df.filter_jobs({'owner': sample_owner})
        print(f"   Jobs by {sample_owner}: {len(owner_jobs)}")
    
    # Get recent jobs
    recent_jobs = htcondor_df.get_recent_jobs(hours=24)
    print(f"   Jobs in last 24h: {len(recent_jobs)}")
    
    # Export sample
    print(f"\n💾 Exporting sample data...")
    htcondor_df.export_to_csv('htcondor_jobs_sample.csv', {'jobstatus': [2, 4]})  # Running and completed jobs
    
    print(f"\n✅ Test complete! Check 'htcondor_jobs_sample.csv' for exported data.")

if __name__ == "__main__":
    main()
