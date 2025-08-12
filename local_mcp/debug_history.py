#!/usr/bin/env python3
"""
Debug script to test condor_history parsing
"""
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_condor_history_parsing():
    """Test different condor_history parsing approaches"""
    
    print("=== Testing condor_history parsing ===\n")
    
    # Test 1: Basic line count
    print("1. Basic line count:")
    try:
        result = subprocess.run(["condor_history"], capture_output=True, text=True, timeout=30)
        line_count = len(result.stdout.strip().split('\n'))
        print(f"   condor_history | wc -l: {line_count}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Formatted count
    print("\n2. Formatted job count:")
    try:
        cmd = ["condor_history", "-format", "%d\\n", "ClusterId"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        job_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
        print(f"   condor_history -format '%d\\n' ClusterId | wc -l: {job_count}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Sample output
    print("\n3. Sample output (first 5 jobs):")
    try:
        cmd = ["condor_history", "-format", "ClusterId=%d ProcId=%d Owner=%s\\n", "ClusterId", "ProcId", "Owner"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = result.stdout.strip().split('\n')[:10]
        for i, line in enumerate(lines):
            print(f"   Line {i+1}: {line}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Parse like DataFrame does
    print("\n4. Parsing like DataFrame (first 10 lines):")
    try:
        cmd = ["condor_history", "-format", "ClusterId=%d\\n", "ClusterId"]
        cmd.extend(["-format", "ProcId=%d\\n", "ProcId"])
        cmd.extend(["-format", "Owner=%s\\n", "Owner"])
        cmd.extend(["-format", "JobStatus=%d\\n", "JobStatus"])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = result.stdout.strip().split('\n')[:20]
        
        print(f"   Total lines: {len(lines)}")
        for i, line in enumerate(lines[:10]):
            print(f"   Line {i+1}: {line}")
            
        # Count unique jobs
        job_data = []
        current_job = {}
        
        for line in lines:
            if not line.strip():
                if current_job:
                    job_data.append(current_job)
                    current_job = {}
            else:
                if '=' in line:
                    key, value = line.split('=', 1)
                    current_job[key.strip().lower()] = value.strip()
        
        if current_job:
            job_data.append(current_job)
        
        print(f"   Parsed jobs: {len(job_data)}")
        
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_condor_history_parsing()
