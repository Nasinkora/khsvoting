from pathlib import Path
import shutil
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
source = BASE_DIR / "database.db"
backup_dir = BASE_DIR / "database" / "backups"
backup_dir.mkdir(exist_ok=True)
destination = backup_dir / f"database_{datetime.now():%Y%m%d_%H%M%S}.db"
shutil.copy2(source, destination)
print(f"Backup created: {destination}")
