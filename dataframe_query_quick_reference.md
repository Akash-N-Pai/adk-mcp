# HTCondor Dataframe Query Quick Reference

## Getting Started

```python
from local_mcp.dataframe_manager import dataframe_manager

# Initialize with fresh data
result = dataframe_manager.update_dataframe(force_update=True)
```

## Available Query Methods

### 1. Basic Information
```python
# Get dataframe info
info = dataframe_manager.get_dataframe_info()
print(f"Jobs: {info['jobs_count']}, Machines: {info['machines_count']}")

# Get jobs summary
summary = dataframe_manager.get_jobs_summary()
print(f"Total jobs: {summary['summary']['total_jobs']}")
```

### 2. Filtered Queries
```python
# Jobs by owner
owner_jobs = dataframe_manager.get_jobs_summary(owner="username")

# Jobs by status
running_jobs = dataframe_manager.get_jobs_summary(status="running")
idle_jobs = dataframe_manager.get_jobs_summary(status="idle")
held_jobs = dataframe_manager.get_jobs_summary(status="held")
completed_jobs = dataframe_manager.get_jobs_summary(status="completed")
```

### 3. Job Details
```python
# Get specific job details
job_details = dataframe_manager.get_job_details(cluster_id=12345)
job_details = dataframe_manager.get_job_details(cluster_id=12345, proc_id=0)
```

### 4. Machine Queries
```python
# Get machines summary
machines = dataframe_manager.get_machines_summary()

# Get idle machines
idle_machines = dataframe_manager.get_machines_summary(status="idle")
```

### 5. Search Jobs
```python
# Search for jobs containing text
search_results = dataframe_manager.search_jobs("username", limit=10)
search_results = dataframe_manager.search_jobs("running", limit=5)
```

### 6. Utilization Statistics
```python
# Get utilization stats for different time ranges
util_24h = dataframe_manager.get_utilization_stats("24h")
util_7d = dataframe_manager.get_utilization_stats("7d")
util_30d = dataframe_manager.get_utilization_stats("30d")
```

### 7. Export Data
```python
# Export as JSON
export_json = dataframe_manager.export_data(
    data_type="jobs", 
    format="json", 
    filters={"owner": "username"}
)

# Export as summary
export_summary = dataframe_manager.export_data(
    data_type="jobs", 
    format="summary"
)

# Export as CSV
export_csv = dataframe_manager.export_data(
    data_type="jobs", 
    format="csv"
)
```

## Direct Dataframe Access (Advanced)

```python
# Access raw dataframes directly
jobs_df = dataframe_manager.jobs_df
machines_df = dataframe_manager.machines_df
pools_df = dataframe_manager.pools_df

# Example: Get high CPU jobs using pandas
high_cpu_jobs = jobs_df[jobs_df['cpu_time'] > 1000]

# Example: Get jobs by owner
owner_jobs = jobs_df[jobs_df['owner'] == 'username']

# Example: Get running jobs
running_jobs = jobs_df[jobs_df['jobstatus'] == 2]

# Example: Get job statistics
job_stats = jobs_df.groupby('owner')['cpu_time'].sum()
```

## Job Status Codes

- `1` = Idle
- `2` = Running  
- `3` = Removed
- `4` = Completed
- `5` = Held

## Machine States

- `Idle` = Available for jobs
- `Busy` = Running jobs
- `Down` = Unavailable
- `Owner` = Owner is using

## Common Query Patterns

### Get all jobs for a user
```python
user_jobs = dataframe_manager.get_jobs_summary(owner="username")
```

### Get running jobs for a user
```python
# Method 1: Using filtered summary
running_user_jobs = dataframe_manager.get_jobs_summary(owner="username", status="running")

# Method 2: Using direct dataframe access
running_user_jobs = dataframe_manager.jobs_df[
    (dataframe_manager.jobs_df['owner'] == 'username') & 
    (dataframe_manager.jobs_df['jobstatus'] == 2)
]
```

### Get machine utilization
```python
machines = dataframe_manager.get_machines_summary()
print(f"Total CPUs: {machines['summary']['total_cpus']}")
print(f"Average load: {machines['summary']['average_load']}")
```

### Export user's jobs to JSON
```python
export_result = dataframe_manager.export_data(
    data_type="jobs",
    format="json", 
    filters={"owner": "username"}
)
print(f"Exported {export_result['total_records']} jobs")
```

## Error Handling

All methods return a dictionary with a `success` field:

```python
result = dataframe_manager.get_jobs_summary()
if result["success"]:
    print("Query successful:", result["summary"])
else:
    print("Query failed:", result["message"])
```

## Running the Examples

To see all examples in action:

```bash
python query_dataframe_examples.py
```

This will run through all the query methods with real data from your HTCondor cluster.
