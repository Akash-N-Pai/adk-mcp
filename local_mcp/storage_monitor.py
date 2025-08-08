#!/usr/bin/env python3
"""
Storage monitoring tool for HTCondor dataframe solution.
Tracks storage usage and provides recommendations.
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import psutil
import shutil

class StorageMonitor:
    """Monitor storage usage for the dataframe solution."""
    
    def __init__(self, db_path: str = "htcondor_data.db"):
        self.db_path = db_path
        self.dataframe_dir = os.path.dirname(db_path)
    
    def get_storage_info(self) -> dict:
        """Get comprehensive storage information."""
        try:
            # Get disk usage
            disk_usage = shutil.disk_usage(self.dataframe_dir)
            
            # Get dataframe file sizes
            df_sizes = self._get_dataframe_sizes()
            
            # Get memory usage
            memory_info = self._get_memory_info()
            
            return {
                "success": True,
                "disk": {
                    "total_gb": disk_usage.total / (1024**3),
                    "used_gb": disk_usage.used / (1024**3),
                    "free_gb": disk_usage.free / (1024**3),
                    "usage_percent": (disk_usage.used / disk_usage.total) * 100
                },
                "dataframe": df_sizes,
                "memory": memory_info,
                "recommendations": self._get_recommendations(disk_usage, df_sizes)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting storage info: {str(e)}"
            }
    
    def _get_dataframe_sizes(self) -> dict:
        """Get sizes of dataframe files."""
        sizes = {}
        
        # Check SQLite database
        if os.path.exists(self.db_path):
            sizes["sqlite_db_mb"] = os.path.getsize(self.db_path) / (1024**2)
        
        # Check for any CSV exports
        csv_files = list(Path(self.dataframe_dir).glob("*.csv"))
        sizes["csv_files_count"] = len(csv_files)
        sizes["csv_total_mb"] = sum(f.stat().st_size for f in csv_files) / (1024**2)
        
        # Check for JSON exports
        json_files = list(Path(self.dataframe_dir).glob("*.json"))
        sizes["json_files_count"] = len(json_files)
        sizes["json_total_mb"] = sum(f.stat().st_size for f in json_files) / (1024**2)
        
        # Get table sizes from SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    # Estimate size (rough calculation)
                    estimated_size_mb = row_count * 0.001  # ~1KB per row estimate
                    sizes[f"{table_name}_rows"] = row_count
                    sizes[f"{table_name}_estimated_mb"] = estimated_size_mb
        except Exception:
            pass
        
        return sizes
    
    def _get_memory_info(self) -> dict:
        """Get memory usage information."""
        try:
            memory = psutil.virtual_memory()
            return {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_gb": memory.used / (1024**3),
                "usage_percent": memory.percent
            }
        except Exception:
            return {"error": "Could not get memory info"}
    
    def _get_recommendations(self, disk_usage, df_sizes) -> list:
        """Get storage recommendations."""
        recommendations = []
        
        # Disk space analysis
        free_gb = disk_usage.free / (1024**3)
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        
        if free_gb > 1000:
            recommendations.append("✅ Excellent: Over 1TB free space available")
        elif free_gb > 100:
            recommendations.append("✅ Good: Over 100GB free space available")
        elif free_gb > 10:
            recommendations.append("⚠️ Adequate: Over 10GB free space available")
        else:
            recommendations.append("❌ Warning: Low disk space available")
        
        # Dataframe size analysis
        total_df_mb = sum(v for k, v in df_sizes.items() if k.endswith('_mb'))
        
        if total_df_mb < 10:
            recommendations.append("✅ Very small: Dataframe uses less than 10MB")
        elif total_df_mb < 100:
            recommendations.append("✅ Small: Dataframe uses less than 100MB")
        elif total_df_mb < 1000:
            recommendations.append("⚠️ Medium: Dataframe uses less than 1GB")
        else:
            recommendations.append("❌ Large: Dataframe uses over 1GB")
        
        # Capacity estimates
        estimated_capacity = int(free_gb * 1000 / max(total_df_mb, 1))  # Rough estimate
        recommendations.append(f"📊 Estimated capacity: Can store ~{estimated_capacity}x current data size")
        
        return recommendations
    
    def cleanup_old_exports(self, days_old: int = 7) -> dict:
        """Clean up old export files."""
        try:
            cleaned_files = []
            total_cleaned_mb = 0
            
            # Clean CSV files
            csv_files = list(Path(self.dataframe_dir).glob("*.csv"))
            for file in csv_files:
                if (datetime.now() - datetime.fromtimestamp(file.stat().st_mtime)).days > days_old:
                    size_mb = file.stat().st_size / (1024**2)
                    file.unlink()
                    cleaned_files.append(str(file))
                    total_cleaned_mb += size_mb
            
            # Clean JSON files
            json_files = list(Path(self.dataframe_dir).glob("*.json"))
            for file in json_files:
                if (datetime.now() - datetime.fromtimestamp(file.stat().st_mtime)).days > days_old:
                    size_mb = file.stat().st_size / (1024**2)
                    file.unlink()
                    cleaned_files.append(str(file))
                    total_cleaned_mb += size_mb
            
            return {
                "success": True,
                "cleaned_files": cleaned_files,
                "total_cleaned_mb": total_cleaned_mb,
                "files_count": len(cleaned_files)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error cleaning up files: {str(e)}"
            }

# Global instance
storage_monitor = StorageMonitor()

def get_storage_status():
    """Get current storage status."""
    return storage_monitor.get_storage_info()

def cleanup_old_data(days_old: int = 7):
    """Clean up old export data."""
    return storage_monitor.cleanup_old_exports(days_old)
