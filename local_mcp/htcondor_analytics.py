#!/usr/bin/env python3
"""
HTCondor Analytics Module
Provides aggregated insights from large job datasets
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import datetime
from htcondor_dataframe import HTCondorDataFrame

class HTCondorAnalytics:
    """Analytics engine for large HTCondor datasets"""
    
    def __init__(self, dataframe: HTCondorDataFrame):
        self.df = dataframe
        self.cache = {}
    
    def get_executive_summary(self) -> Dict:
        """Get high-level summary suitable for LLM consumption"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        stats = self.df.get_summary_stats()
        
        # Calculate key metrics
        summary = {
            "total_jobs": stats['total_jobs'],
            "success_rate": round(stats['success_rate'], 1),
            "unique_users": stats['unique_owners'],
            "date_range": stats['date_range'],
            "data_sources": {
                "current_queue": stats['current_queue_jobs'],
                "historical": stats['historical_jobs']
            }
        }
        
        # Add status distribution
        if 'jobstatus' in df.columns:
            status_counts = df['jobstatus'].value_counts().to_dict()
            status_map = {1: 'Idle', 2: 'Running', 3: 'Removed', 4: 'Completed', 5: 'Held', 7: 'Suspended'}
            summary['status_distribution'] = {
                status_map.get(k, f'Status_{k}'): v for k, v in status_counts.items()
            }
        
        # Add recent activity
        if 'qdate_datetime' in df.columns:
            recent_24h = df[df['qdate_datetime'] >= datetime.datetime.now() - datetime.timedelta(hours=24)]
            recent_7d = df[df['qdate_datetime'] >= datetime.datetime.now() - datetime.timedelta(days=7)]
            summary['recent_activity'] = {
                'last_24h': len(recent_24h),
                'last_7_days': len(recent_7d)
            }
        
        return summary
    
    def get_performance_metrics(self) -> Dict:
        """Get performance metrics and insights"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        metrics = {}
        
        # Wait time analysis
        if 'wait_time_minutes' in df.columns:
            wait_times = df['wait_time_minutes'].dropna()
            if len(wait_times) > 0:
                metrics['wait_time'] = {
                    'average_minutes': round(wait_times.mean(), 1),
                    'median_minutes': round(wait_times.median(), 1),
                    'p95_minutes': round(wait_times.quantile(0.95), 1),
                    'p99_minutes': round(wait_times.quantile(0.99), 1)
                }
        
        # Runtime analysis
        if 'runtime_minutes' in df.columns:
            runtimes = df['runtime_minutes'].dropna()
            if len(runtimes) > 0:
                metrics['runtime'] = {
                    'average_minutes': round(runtimes.mean(), 1),
                    'median_minutes': round(runtimes.median(), 1),
                    'p95_minutes': round(runtimes.quantile(0.95), 1)
                }
        
        # Resource efficiency
        if 'cpu_efficiency' in df.columns:
            cpu_eff = df['cpu_efficiency'].dropna()
            if len(cpu_eff) > 0:
                metrics['resource_efficiency'] = {
                    'avg_cpu_efficiency': round(cpu_eff.mean() * 100, 1),
                    'low_efficiency_jobs': len(cpu_eff[cpu_eff < 0.5]),
                    'high_efficiency_jobs': len(cpu_eff[cpu_eff > 0.8])
                }
        
        return metrics
    
    def get_user_insights(self, top_n: int = 10) -> Dict:
        """Get insights about top users"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0 or 'owner' not in df.columns:
            return {"error": "No user data available"}
        
        # User statistics
        user_stats = df.groupby('owner').agg({
            'clusterid': 'count',
            'is_successful': 'sum',
            'is_failed': 'sum',
            'wait_time_minutes': 'mean',
            'runtime_minutes': 'mean'
        }).round(2)
        
        user_stats.columns = ['total_jobs', 'successful_jobs', 'failed_jobs', 'avg_wait_time', 'avg_runtime']
        user_stats['success_rate'] = (user_stats['successful_jobs'] / user_stats['total_jobs'] * 100).round(1)
        
        # Get top users by job count
        top_users = user_stats.nlargest(top_n, 'total_jobs')
        
        return {
            'top_users_by_job_count': top_users.to_dict('index'),
            'total_unique_users': len(user_stats)
        }
    
    def get_failure_analysis(self) -> Dict:
        """Analyze job failures"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        # Filter failed jobs
        failed_jobs = df[df['is_failed'] == True]
        
        if len(failed_jobs) == 0:
            return {"message": "No failed jobs found"}
        
        analysis = {
            'total_failures': len(failed_jobs),
            'failure_rate': round(len(failed_jobs) / len(df) * 100, 1)
        }
        
        # Failure reasons by status
        if 'jobstatus' in failed_jobs.columns:
            status_counts = failed_jobs['jobstatus'].value_counts().to_dict()
            status_map = {3: 'Removed', 5: 'Held', 7: 'Suspended'}
            analysis['failures_by_status'] = {
                status_map.get(k, f'Status_{k}'): v for k, v in status_counts.items()
            }
        
        # Exit code analysis
        if 'exitcode' in failed_jobs.columns:
            exit_codes = failed_jobs['exitcode'].dropna()
            if len(exit_codes) > 0:
                top_exit_codes = exit_codes.value_counts().head(5).to_dict()
                analysis['top_exit_codes'] = top_exit_codes
        
        return analysis
    
    def get_temporal_patterns(self) -> Dict:
        """Analyze temporal patterns in job submissions"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0 or 'qdate_datetime' not in df.columns:
            return {"error": "No temporal data available"}
        
        # Hourly distribution
        df['hour'] = df['qdate_datetime'].dt.hour
        hourly_dist = df['hour'].value_counts().sort_index().to_dict()
        
        # Daily distribution (last 30 days)
        recent_30d = df[df['qdate_datetime'] >= datetime.datetime.now() - datetime.timedelta(days=30)]
        if len(recent_30d) > 0:
            recent_30d['date'] = recent_30d['qdate_datetime'].dt.date
            daily_dist = recent_30d['date'].value_counts().sort_index().tail(7).to_dict()
            daily_dist = {str(k): v for k, v in daily_dist.items()}
        else:
            daily_dist = {}
        
        return {
            'hourly_distribution': hourly_dist,
            'daily_distribution_last_7_days': daily_dist,
            'peak_hour': max(hourly_dist.items(), key=lambda x: x[1])[0] if hourly_dist else None,
            'peak_day': max(daily_dist.items(), key=lambda x: x[1])[0] if daily_dist else None
        }
    
    def get_resource_analysis(self) -> Dict:
        """Analyze resource usage patterns"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # CPU analysis
        if 'requestcpus' in df.columns:
            cpu_stats = df['requestcpus'].dropna()
            if len(cpu_stats) > 0:
                analysis['cpu_requests'] = {
                    'average': round(cpu_stats.mean(), 1),
                    'median': round(cpu_stats.median(), 1),
                    'max': int(cpu_stats.max()),
                    'distribution': cpu_stats.value_counts().head(5).to_dict()
                }
        
        # Memory analysis
        if 'requestmemory' in df.columns:
            mem_stats = df['requestmemory'].dropna()
            if len(mem_stats) > 0:
                analysis['memory_requests'] = {
                    'average_mb': round(mem_stats.mean(), 1),
                    'median_mb': round(mem_stats.median(), 1),
                    'max_mb': int(mem_stats.max()),
                    'average_gb': round(mem_stats.mean() / 1024, 1)
                }
        
        return analysis
    
    def get_anomaly_insights(self) -> Dict:
        """Identify potential anomalies and issues"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        insights = []
        
        # Check for long wait times
        if 'wait_time_hours' in df.columns:
            long_wait_jobs = df[df['wait_time_hours'] > 24]
            if len(long_wait_jobs) > 0:
                insights.append(f"{len(long_wait_jobs)} jobs waited more than 24 hours")
        
        # Check for resource inefficiency
        if 'cpu_efficiency' in df.columns:
            low_efficiency = df[df['cpu_efficiency'] < 0.2]
            if len(low_efficiency) > 0:
                insights.append(f"{len(low_efficiency)} jobs had very low CPU efficiency (<20%)")
        
        # Check for high failure rates
        if 'owner' in df.columns:
            user_failure_rates = df.groupby('owner')['is_failed'].mean()
            high_failure_users = user_failure_rates[user_failure_rates > 0.5]
            if len(high_failure_users) > 0:
                insights.append(f"{len(high_failure_users)} users have >50% failure rate")
        
        return {
            'anomalies_detected': len(insights),
            'insights': insights
        }
    
    def get_queue_analysis(self) -> Dict:
        """Analyze queue performance and bottlenecks"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # Queue depth analysis
        if 'qdate_datetime' in df.columns:
            # Jobs submitted but not started
            queued_jobs = df[(df['jobstatus'] == 1) & (df['data_source'] == 'current_queue')]
            analysis['current_queue_depth'] = len(queued_jobs)
            
            # Queue wait time distribution
            if 'wait_time_minutes' in df.columns:
                wait_times = df['wait_time_minutes'].dropna()
                analysis['queue_performance'] = {
                    'avg_wait_time_minutes': round(wait_times.mean(), 1),
                    'median_wait_time_minutes': round(wait_times.median(), 1),
                    'p95_wait_time_minutes': round(wait_times.quantile(0.95), 1),
                    'p99_wait_time_minutes': round(wait_times.quantile(0.99), 1)
                }
        
        # Job priority analysis
        if 'jobprio' in df.columns:
            priority_stats = df['jobprio'].describe()
            analysis['priority_distribution'] = {
                'min_priority': int(priority_stats['min']),
                'max_priority': int(priority_stats['max']),
                'avg_priority': round(priority_stats['mean'], 1),
                'median_priority': round(priority_stats['50%'], 1)
            }
        
        return analysis
    
    def get_machine_analysis(self) -> Dict:
        """Analyze execution machine performance"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # Machine utilization
        if 'remotehost' in df.columns:
            machine_stats = df.groupby('remotehost').agg({
                'clusterid': 'count',
                'runtime_minutes': 'mean',
                'is_successful': 'mean'
            }).round(2)
            
            machine_stats.columns = ['total_jobs', 'avg_runtime_minutes', 'success_rate']
            machine_stats['success_rate'] = machine_stats['success_rate'] * 100
            
            # Top machines by job count
            top_machines = machine_stats.nlargest(10, 'total_jobs')
            analysis['top_execution_machines'] = top_machines.to_dict('index')
            
            # Machine reliability
            reliable_machines = machine_stats[machine_stats['success_rate'] > 95]
            analysis['reliable_machines'] = len(reliable_machines)
            
            # Problematic machines
            problematic_machines = machine_stats[machine_stats['success_rate'] < 80]
            analysis['problematic_machines'] = len(problematic_machines)
        
        return analysis
    
    def get_job_universe_analysis(self) -> Dict:
        """Analyze job universe types and performance"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        if 'jobuniverse' in df.columns:
            universe_map = {
                1: 'Standard', 2: 'Pipes', 3: 'Linda', 4: 'PVM',
                5: 'Vanilla', 6: 'Scheduler', 7: 'MPI', 9: 'Grid',
                10: 'Java', 11: 'Parallel', 12: 'Local', 13: 'Docker'
            }
            
            df['universe_name'] = df['jobuniverse'].map(universe_map)
            universe_stats = df.groupby('universe_name').agg({
                'clusterid': 'count',
                'is_successful': 'mean',
                'wait_time_minutes': 'mean',
                'runtime_minutes': 'mean'
            }).round(2)
            
            universe_stats.columns = ['total_jobs', 'success_rate', 'avg_wait_time', 'avg_runtime']
            universe_stats['success_rate'] = universe_stats['success_rate'] * 100
            
            analysis['universe_performance'] = universe_stats.to_dict('index')
        
        return analysis
    
    def get_file_transfer_analysis(self) -> Dict:
        """Analyze file transfer patterns and issues"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # File transfer status
        if 'transferin' in df.columns and 'transferout' in df.columns:
            transfer_in_jobs = df[df['transferin'] == True]
            transfer_out_jobs = df[df['transferout'] == True]
            
            analysis['file_transfers'] = {
                'jobs_with_input_transfer': len(transfer_in_jobs),
                'jobs_with_output_transfer': len(transfer_out_jobs),
                'input_transfer_rate': round(len(transfer_in_jobs) / len(df) * 100, 1),
                'output_transfer_rate': round(len(transfer_out_jobs) / len(df) * 100, 1)
            }
        
        # File path analysis
        file_columns = ['in', 'out', 'err', 'userlog']
        file_analysis = {}
        
        for col in file_columns:
            if col in df.columns:
                file_paths = df[col].dropna()
                if len(file_paths) > 0:
                    # Analyze file path patterns
                    common_paths = file_paths.value_counts().head(5).to_dict()
                    file_analysis[f'{col}_files'] = {
                        'total_files': len(file_paths),
                        'common_paths': common_paths
                    }
        
        if file_analysis:
            analysis['file_patterns'] = file_analysis
        
        return analysis
    
    def get_job_requirement_analysis(self) -> Dict:
        """Analyze job requirements and constraints"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # Requirements analysis
        if 'requirements' in df.columns:
            requirements = df['requirements'].dropna()
            if len(requirements) > 0:
                # Count common requirement patterns
                common_reqs = requirements.value_counts().head(10).to_dict()
                analysis['common_requirements'] = common_reqs
        
        # Rank analysis
        if 'rank' in df.columns:
            rank_values = df['rank'].dropna()
            if len(rank_values) > 0:
                analysis['rank_distribution'] = {
                    'total_ranked_jobs': len(rank_values),
                    'avg_rank_value': round(rank_values.mean(), 2),
                    'rank_usage_rate': round(len(rank_values) / len(df) * 100, 1)
                }
        
        return analysis
    
    def get_job_matching_analysis(self) -> Dict:
        """Analyze job matching and scheduling efficiency"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # Job matching statistics
        matching_columns = ['numjobmatches', 'numjobmatchesrejected', 'numjobstarts']
        
        for col in matching_columns:
            if col in df.columns:
                values = df[col].dropna()
                if len(values) > 0:
                    analysis[f'{col}_stats'] = {
                        'total_jobs': len(values),
                        'average': round(values.mean(), 2),
                        'median': round(values.median(), 2),
                        'max': int(values.max()),
                        'jobs_with_zero': len(values[values == 0])
                    }
        
        # Matching efficiency
        if 'numjobmatches' in df.columns and 'numjobmatchesrejected' in df.columns:
            df['matching_efficiency'] = df['numjobmatches'] / (df['numjobmatches'] + df['numjobmatchesrejected'])
            efficiency = df['matching_efficiency'].dropna()
            if len(efficiency) > 0:
                analysis['matching_efficiency'] = {
                    'avg_efficiency': round(efficiency.mean() * 100, 1),
                    'jobs_with_low_efficiency': len(efficiency[efficiency < 0.5])
                }
        
        return analysis
    
    def get_time_series_analysis(self) -> Dict:
        """Analyze temporal patterns and trends"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0 or 'qdate_datetime' not in df.columns:
            return {"error": "No temporal data available"}
        
        analysis = {}
        
        # Daily job submission trends
        df['date'] = df['qdate_datetime'].dt.date
        daily_submissions = df.groupby('date')['clusterid'].count()
        
        if len(daily_submissions) > 0:
            analysis['daily_trends'] = {
                'total_days': len(daily_submissions),
                'avg_jobs_per_day': round(daily_submissions.mean(), 1),
                'max_jobs_per_day': int(daily_submissions.max()),
                'min_jobs_per_day': int(daily_submissions.min()),
                'busiest_day': str(daily_submissions.idxmax()),
                'quietest_day': str(daily_submissions.idxmin())
            }
        
        # Weekly patterns
        df['weekday'] = df['qdate_datetime'].dt.day_name()
        weekday_patterns = df.groupby('weekday')['clusterid'].count()
        analysis['weekly_patterns'] = weekday_patterns.to_dict()
        
        # Monthly trends
        df['month'] = df['qdate_datetime'].dt.to_period('M')
        monthly_trends = df.groupby('month')['clusterid'].count()
        analysis['monthly_trends'] = {
            'total_months': len(monthly_trends),
            'avg_jobs_per_month': round(monthly_trends.mean(), 1),
            'trend_direction': 'increasing' if monthly_trends.iloc[-1] > monthly_trends.iloc[0] else 'decreasing'
        }
        
        return analysis
    
    def get_resource_utilization_analysis(self) -> Dict:
        """Detailed resource utilization analysis"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # CPU utilization patterns
        if 'requestcpus' in df.columns and 'remotesusercpu' in df.columns:
            df['cpu_utilization'] = df['remotesusercpu'] / df['requestcpus']
            cpu_util = df['cpu_utilization'].dropna()
            
            if len(cpu_util) > 0:
                analysis['cpu_utilization'] = {
                    'avg_utilization': round(cpu_util.mean() * 100, 1),
                    'median_utilization': round(cpu_util.median() * 100, 1),
                    'underutilized_jobs': len(cpu_util[cpu_util < 0.5]),
                    'overutilized_jobs': len(cpu_util[cpu_util > 1.0]),
                    'efficient_jobs': len(cpu_util[cpu_util.between(0.8, 1.2)])
                }
        
        # Memory utilization patterns
        if 'requestmemory' in df.columns and 'memoryusage' in df.columns:
            df['memory_utilization'] = df['memoryusage'] / df['requestmemory']
            mem_util = df['memory_utilization'].dropna()
            
            if len(mem_util) > 0:
                analysis['memory_utilization'] = {
                    'avg_utilization': round(mem_util.mean() * 100, 1),
                    'median_utilization': round(mem_util.median() * 100, 1),
                    'underutilized_jobs': len(mem_util[mem_util < 0.5]),
                    'overutilized_jobs': len(mem_util[mem_util > 1.0])
                }
        
        # Resource request patterns
        if 'requestcpus' in df.columns:
            cpu_requests = df['requestcpus'].dropna()
            analysis['cpu_requests'] = {
                'avg_request': round(cpu_requests.mean(), 1),
                'median_request': round(cpu_requests.median(), 1),
                'max_request': int(cpu_requests.max()),
                'common_requests': cpu_requests.value_counts().head(5).to_dict()
            }
        
        if 'requestmemory' in df.columns:
            mem_requests = df['requestmemory'].dropna()
            analysis['memory_requests'] = {
                'avg_request_mb': round(mem_requests.mean(), 1),
                'avg_request_gb': round(mem_requests.mean() / 1024, 1),
                'median_request_mb': round(mem_requests.median(), 1),
                'max_request_mb': int(mem_requests.max())
            }
        
        return analysis
    
    def get_error_analysis(self) -> Dict:
        """Detailed error and failure analysis"""
        
        df = self.df.get_all_jobs()
        if len(df) == 0:
            return {"error": "No data available"}
        
        analysis = {}
        
        # Exit code analysis
        if 'exitcode' in df.columns:
            exit_codes = df['exitcode'].dropna()
            if len(exit_codes) > 0:
                analysis['exit_codes'] = {
                    'total_jobs_with_exit_codes': len(exit_codes),
                    'successful_exits': len(exit_codes[exit_codes == 0]),
                    'failed_exits': len(exit_codes[exit_codes != 0]),
                    'common_exit_codes': exit_codes.value_counts().head(10).to_dict()
                }
        
        # Signal analysis
        if 'exitsignal' in df.columns:
            signals = df['exitsignal'].dropna()
            if len(signals) > 0:
                signal_names = {
                    9: 'SIGKILL', 15: 'SIGTERM', 11: 'SIGSEGV', 
                    6: 'SIGABRT', 8: 'SIGFPE', 4: 'SIGILL'
                }
                signals['signal_name'] = signals.map(signal_names)
                analysis['exit_signals'] = signals['signal_name'].value_counts().to_dict()
        
        # Job status failure analysis
        if 'jobstatus' in df.columns:
            failed_statuses = df[df['is_failed'] == True]['jobstatus'].value_counts()
            analysis['failure_by_status'] = failed_statuses.to_dict()
        
        return analysis
    
    def get_comprehensive_report(self) -> Dict:
        """Get a comprehensive report suitable for LLM consumption"""
        
        return {
            "executive_summary": self.get_executive_summary(),
            "performance_metrics": self.get_performance_metrics(),
            "user_insights": self.get_user_insights(top_n=5),
            "failure_analysis": self.get_failure_analysis(),
            "temporal_patterns": self.get_temporal_patterns(),
            "resource_analysis": self.get_resource_analysis(),
            "anomaly_insights": self.get_anomaly_insights(),
            "queue_analysis": self.get_queue_analysis(),
            "machine_analysis": self.get_machine_analysis(),
            "job_universe_analysis": self.get_job_universe_analysis(),
            "file_transfer_analysis": self.get_file_transfer_analysis(),
            "job_requirement_analysis": self.get_job_requirement_analysis(),
            "job_matching_analysis": self.get_job_matching_analysis(),
            "time_series_analysis": self.get_time_series_analysis(),
            "resource_utilization_analysis": self.get_resource_utilization_analysis(),
            "error_analysis": self.get_error_analysis()
        }

def main():
    """Test the analytics module"""
    
    print("=== HTCondor Analytics Test ===\n")
    
    # Create DataFrame and Analytics instances
    htcondor_df = HTCondorDataFrame()
    analytics = HTCondorAnalytics(htcondor_df)
    
    # Get comprehensive report
    print("📊 Generating comprehensive analytics report...")
    report = analytics.get_comprehensive_report()
    
    # Display results
    print("\n📈 EXECUTIVE SUMMARY:")
    summary = report['executive_summary']
    print(f"   Total jobs: {summary['total_jobs']}")
    print(f"   Success rate: {summary['success_rate']}%")
    print(f"   Unique users: {summary['unique_users']}")
    print(f"   Recent activity (24h): {summary['recent_activity']['last_24h']} jobs")
    
    print("\n⏱️ PERFORMANCE METRICS:")
    perf = report['performance_metrics']
    if 'wait_time' in perf:
        print(f"   Average wait time: {perf['wait_time']['average_minutes']} minutes")
        print(f"   95th percentile wait: {perf['wait_time']['p95_minutes']} minutes")
    
    print("\n👥 TOP USERS:")
    users = report['user_insights']
    if 'top_users_by_job_count' in users:
        for user, stats in list(users['top_users_by_job_count'].items())[:3]:
            print(f"   {user}: {stats['total_jobs']} jobs ({stats['success_rate']}% success)")
    
    print("\n❌ FAILURE ANALYSIS:")
    failures = report['failure_analysis']
    if 'total_failures' in failures:
        print(f"   Total failures: {failures['total_failures']}")
        print(f"   Failure rate: {failures['failure_rate']}%")
    
    print("\n📅 TEMPORAL PATTERNS:")
    temporal = report['temporal_patterns']
    if 'peak_hour' in temporal:
        print(f"   Peak submission hour: {temporal['peak_hour']}:00")
    
    print("\n💡 ANOMALY INSIGHTS:")
    anomalies = report['anomaly_insights']
    if 'insights' in anomalies:
        for insight in anomalies['insights']:
            print(f"   - {insight}")
    
    print("\n📊 QUEUE ANALYSIS:")
    queue = report['queue_analysis']
    if 'current_queue_depth' in queue:
        print(f"   Current queue depth: {queue['current_queue_depth']} jobs")
    if 'queue_performance' in queue:
        perf = queue['queue_performance']
        print(f"   Average wait time: {perf['avg_wait_time_minutes']} minutes")
    
    print("\n🖥️ MACHINE ANALYSIS:")
    machines = report['machine_analysis']
    if 'reliable_machines' in machines:
        print(f"   Reliable machines: {machines['reliable_machines']}")
        print(f"   Problematic machines: {machines['problematic_machines']}")
    
    print("\n🌌 JOB UNIVERSE ANALYSIS:")
    universe = report['job_universe_analysis']
    if 'universe_performance' in universe:
        print(f"   Universe types analyzed: {len(universe['universe_performance'])}")
    
    print("\n📁 FILE TRANSFER ANALYSIS:")
    transfers = report['file_transfer_analysis']
    if 'file_transfers' in transfers:
        ft = transfers['file_transfers']
        print(f"   Input transfer rate: {ft['input_transfer_rate']}%")
        print(f"   Output transfer rate: {ft['output_transfer_rate']}%")
    
    print("\n⚙️ JOB MATCHING ANALYSIS:")
    matching = report['job_matching_analysis']
    if 'matching_efficiency' in matching:
        me = matching['matching_efficiency']
        print(f"   Average matching efficiency: {me['avg_efficiency']}%")
    
    print("\n📈 TIME SERIES ANALYSIS:")
    time_series = report['time_series_analysis']
    if 'daily_trends' in time_series:
        dt = time_series['daily_trends']
        print(f"   Average jobs per day: {dt['avg_jobs_per_day']}")
        print(f"   Trend direction: {dt.get('trend_direction', 'N/A')}")
    
    print("\n💾 RESOURCE UTILIZATION:")
    resources = report['resource_utilization_analysis']
    if 'cpu_utilization' in resources:
        cpu = resources['cpu_utilization']
        print(f"   Average CPU utilization: {cpu['avg_utilization']}%")
        print(f"   Efficient jobs: {cpu['efficient_jobs']}")
    
    print("\n❌ ERROR ANALYSIS:")
    errors = report['error_analysis']
    if 'exit_codes' in errors:
        ec = errors['exit_codes']
        print(f"   Failed exits: {ec['failed_exits']}")
        print(f"   Common exit codes: {len(ec['common_exit_codes'])}")
    
    print(f"\n✅ Comprehensive analytics complete! Report contains {len(report)} analysis sections.")
    print("This aggregated data provides complete HTCondor insights suitable for LLM consumption.")

if __name__ == "__main__":
    main()
