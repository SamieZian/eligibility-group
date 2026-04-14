import os
import sys
from pathlib import Path

# Make app importable without installing
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent / "libs" / "python-common" / "src"))

os.environ.setdefault("SERVICE_NAME", "group")
os.environ.setdefault("LOG_LEVEL", "WARNING")
