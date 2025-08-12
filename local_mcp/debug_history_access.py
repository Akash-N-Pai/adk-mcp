#!/usr/bin/env python3
"""
Debug condor_history access issues
"""
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_history_access():
    """Debug condor_history access issues"""
    
    print("=== Debugging condor_history access ===\n")
    
    # Test 1: Basic condor_history
    print("1. Basic condor_history:")
    try:
        result = subprocess.run(["condor_history"], capture_output=True, text=True, timeout=30)
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)}")
        print(f"   Stderr: {result.stderr}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"   Lines: {len(lines)}")
            print(f"   First line: {lines[0] if lines else 'None'}")
        else:
            print("   No output!")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Simple format
    print("\n2. Simple format:")
    try:
        cmd = ["condor_history", "-format", "%d", "ClusterId"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)}")
        print(f"   Stderr: {result.stderr}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"   Lines: {len(lines)}")
            print(f"   First 3 values: {lines[:3] if lines else 'None'}")
        else:
            print("   No output!")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Check if history is enabled
    print("\n3. Check history configuration:")
    try:
        cmd = ["condor_config_val", "HISTORY"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(f"   HISTORY config: {result.stdout.strip()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Check history file
    print("\n4. Check history file:")
    try:
        cmd = ["condor_config_val", "HISTORY"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        history_file = result.stdout.strip()
        print(f"   History file: {history_file}")
        
        if history_file and history_file != "UNDEFINED":
            import os
            if os.path.exists(history_file):
                size = os.path.getsize(history_file)
                print(f"   File exists, size: {size} bytes")
            else:
                print(f"   File does not exist")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 5: Try with limit
    print("\n5. Try with limit:")
    try:
        cmd = ["condor_history", "-limit", "10", "-format", "%d", "ClusterId"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"   Lines: {len(lines)}")
            print(f"   Values: {lines[:5] if lines else 'None'}")
        else:
            print("   No output!")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 6: Check permissions
    print("\n6. Check user permissions:")
    try:
        import getpass
        user = getpass.getuser()
        print(f"   Current user: {user}")
        
        # Try to run condor_history as current user
        cmd = ["condor_history", "-user", user, "-limit", "5"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout length: {len(result.stdout)}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            print(f"   Lines: {len(lines)}")
        else:
            print("   No output!")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    debug_history_access()
