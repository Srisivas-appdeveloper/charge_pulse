"""Test setup. Loads .env from backend/ so settings resolve to the live local stack."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure tests use the same .env as the running app.
os.environ.setdefault("APP_ENV", "test")
