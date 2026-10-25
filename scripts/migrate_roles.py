"""Migrate legacy roles in SQLite database to the 4 supported roles:
DEVELOPER, TESTER, QA, PROJECT_MANAGER.
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "projectpulse.db"


def migrate_roles():
    if not DB_PATH.exists():
        print(f"[!] Database file not found at {DB_PATH}, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    legacy_roles = ("DEVOPS", "DESIGNER", "TEAM_LEAD", "REVIEWER")
    placeholders = ",".join(f"'{r}'" for r in legacy_roles)

    # 1. Update users
    cursor.execute(f"UPDATE users SET role = 'DEVELOPER' WHERE role IN ({placeholders})")
    users_updated = cursor.rowcount

    # 2. Update agents
    cursor.execute(f"UPDATE agents SET role = 'DEVELOPER' WHERE role IN ({placeholders})")
    agents_updated = cursor.rowcount

    # 3. Update events
    cursor.execute(f"UPDATE project_events SET role = 'DEVELOPER' WHERE role IN ({placeholders})")
    events_updated = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"[+] Role migration completed successfully:")
    print(f"    - Users migrated: {users_updated}")
    print(f"    - Agents migrated: {agents_updated}")
    print(f"    - Events migrated: {events_updated}")


if __name__ == "__main__":
    migrate_roles()
