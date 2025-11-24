import sys
from pathlib import Path

pytest_plugins = [
    "tests.utils.test_helpers",
]

ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT_DIR)

if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

