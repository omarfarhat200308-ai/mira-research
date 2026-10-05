import os

# Set before any `mira` import: config.py reads these at module import time.
os.environ.setdefault("MIRA_MOCK_LLM", "1")
os.environ.setdefault("MIRA_LOG_DIR", os.path.join(os.path.dirname(__file__), ".test_logs"))
