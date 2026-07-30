#!/usr/bin/env python3
"""
Test runner for DoubanNotionSync project
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_tests():
    """Run all tests using pytest"""
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # Let uv create a reproducible development environment when available.
    if shutil.which("uv"):
        cmd = ["uv", "run", "--extra", "dev", "pytest"]
        env = os.environ.copy()
        env.setdefault(
            "UV_PROJECT_ENVIRONMENT",
            str(Path(tempfile.gettempdir()) / "doubannotionsync-venv"),
        )
    else:
        cmd = [sys.executable, "-m", "pytest"]
        env = None

    try:
        subprocess.run(cmd, check=True, env=env)
        print("All tests passed! ✅")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code: {e.returncode} ❌")
        return e.returncode

if __name__ == "__main__":
    raise SystemExit(run_tests())
