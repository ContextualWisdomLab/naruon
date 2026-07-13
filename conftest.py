import sys
from pathlib import Path

# Add the repository root to sys.path so that tests can import root modules like 'connector'
sys.path.insert(0, str(Path(__file__).parent))
