#!/usr/bin/env python3
"""
Test runner for DoubanNotionSync project
"""
import subprocess
import sys
import os
from pathlib import Path

def run_tests():
    """Run all tests using pytest"""
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/", 
        "-v", 
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("All tests passed! ✅")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code: {e.returncode} ❌")
        return e.returncode

if __name__ == "__main__":
    exit(run_tests())