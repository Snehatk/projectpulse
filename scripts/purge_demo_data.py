"""Purge fictional demo data (DLX E-Commerce Platform) from ProjectPulse AI database.
Creates a safety backup at data/projectpulse_backup.db first.
"""

from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "projectpulse.db"
BACKUP_PATH = DATA_DIR / "projectpulse_backup.db"


def purge_demo_data():
    if not DB_PATH.exists():
        print(f"[!] Database file does not exist at {DB_PATH}. Nothing to purge.")
        return

    # 1. Create safety backup
    print(f"[+] Creating database backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[+] Backup created successfully.")

    # 2. Connect and delete fictional DLX records
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables_and_queries = [
        ("ai_risks", "DELETE FROM ai_risks WHERE project_id IN ('DLX', 'P001')"),
        ("evidence", "DELETE FROM evidence WHERE project_id IN ('DLX', 'P001')"),
        ("defects", "DELETE FROM defects WHERE project_id IN ('DLX', 'P001')"),
        ("tasks", "DELETE FROM tasks WHERE project_id IN ('DLX', 'P001')"),
        ("project_events", "DELETE FROM project_events WHERE project_id IN ('DLX', 'P001')"),
        ("agents", "DELETE FROM agents WHERE project_id IN ('DLX', 'P001')"),
        ("projects_external", "DELETE FROM projects_external WHERE project_id IN ('DLX', 'P001')"),
        ("projects", "DELETE FROM projects WHERE project_id IN ('DLX', 'P001')"),
        ("users", "DELETE FROM users WHERE user_id IN ('DEV-001', 'DEV-002', 'DEV-003', 'TEST-001', 'TEST-002', 'QA-001', 'PM-001', 'U001')"),
    ]

    for table, query in tables_and_queries:
        try:
            cursor.execute(query)
            print(f"    - Purged {cursor.rowcount} rows from {table}")
        except sqlite3.OperationalError as exc:
            print(f"    - Table {table} skipped ({exc})")

    conn.commit()
    conn.close()
    print("[+] All fictional DLX records successfully purged.")


if __name__ == "__main__":
    purge_demo_data()
