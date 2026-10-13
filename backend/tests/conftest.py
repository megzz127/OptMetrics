"""
Pytest configuration for OptMetrics test suite.
Adds the backend directory to sys.path so 'app' can be imported cleanly.
"""

import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
