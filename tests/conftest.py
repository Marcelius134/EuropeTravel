import sys
from pathlib import Path

# Make the project root importable when pytest is run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
