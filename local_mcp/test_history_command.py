#!/usr/bin/env python3
"""
Test condor_history command execution
"""
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_history_command():
    """Test the condor_history command that's failing"""
    
    print("=== Testing condor_history command ===\n")
    
    # Test the exact command from DataFrame
    cmd = ["condor_history", "-format", "ClusterId=%d ProcId=%d Owner=%s JobStatus=%d QDate=%d JobStartDate=%d CompletionDate=%d RemoteHost=%s ExitCode=%d ExitSignal=%d RemoteUserCpu=%f MemoryUsage=%f RequestCpus=%d RequestMemory=%d JobPrio=%d JobUniverse=%d NumJobStarts=%d NumJobMatches=%d NumJobMatchesRejected=%d ExitStatus=%d\\n", 
           "ClusterId", "ProcId", "Owner", "JobStatus", "QDate", "JobStartDate", "CompletionDate", "RemoteHost", "ExitCode", "ExitSignal", "RemoteUserCpu", "MemoryUsage", "RequestCpus", "RequestMemory", "JobPrio", "JobUniverse", "NumJobStarts", "NumJobMatches", "NumJobMatchesRejected", "ExitStatus"]
    
    print(f"Command: {' '.join(cmd[:5])}...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout length: {len(result.stdout)}")
        print(f"Stderr: {result.stderr}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"Output lines: {len(lines)}")
            print("First 3 lines:")
            for i, line in enumerate(lines[:3]):
                print(f"  {i+1}: {line}")
        else:
            print("No output!")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test simpler command
    print("\n=== Testing simpler command ===")
    try:
        simple_cmd = ["condor_history", "-format", "ClusterId=%d Owner=%s\\n", "ClusterId", "Owner"]
        result = subprocess.run(simple_cmd, capture_output=True, text=True, timeout=30)
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout length: {len(result.stdout)}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"Output lines: {len(lines)}")
            print("First 3 lines:")
            for i, line in enumerate(lines[:3]):
                print(f"  {i+1}: {line}")
        else:
            print("No output!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_history_command()
