import sys
import os
from pathlib import Path

# Add src to Python path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Global test configuration
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest"""
    # Add any global configuration here
    pass


def pytest_sessionstart(session):
    """Called after the Session object has been created and before performing collection and entering the run test loop."""
    pass


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished, right before returning the exit status to the system."""
    pass