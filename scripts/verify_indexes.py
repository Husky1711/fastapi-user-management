"""Verify all database indexes"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.database import get_db
from sqlalchemy import text

db = next(get_db())
result = db.execute(text("SELECT COUNT(*) as count FROM information_schema.statistics WHERE table_schema = DATABASE() AND index_name LIKE 'idx_%'"))
count = result.fetchone()[0]
print(f"Total indexes created: {count}")
db.close()

