#!/usr/bin/env python3
"""
Clean up test/integration roles from the database.
Keeps only roles that appear to be real/legitimate.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Test/integration role patterns to remove
TEST_PATTERNS = [
    'Integration Role',
    'Smoke Role',
    'Roles Integration',
    'Check',
    'Medidata',
    'Roadmap Role',
    'Gcp DevOps',
    'Hrbp',
    'Whatsapp Messenger',
]

def cleanup_roles():
    db_path = PROJECT_ROOT / 'skilldb.sqlite3'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all roles
    cursor.execute('SELECT id, name FROM roles ORDER BY name')
    all_roles = cursor.fetchall()
    
    print(f"Total roles: {len(all_roles)}\n")
    print("Roles to be REMOVED:")
    print("=" * 60)
    
    roles_to_remove = []
    roles_to_keep = []
    
    for role_id, name in all_roles:
        is_test = any(pattern.lower() in name.lower() for pattern in TEST_PATTERNS)
        if is_test:
            roles_to_remove.append((role_id, name))
            print(f"  ❌ {name}")
        else:
            roles_to_keep.append((role_id, name))
    
    print(f"\nRoles to be KEPT:")
    print("=" * 60)
    for role_id, name in roles_to_keep:
        print(f"  ✅ {name}")
    
    if not roles_to_remove:
        print("\nNo test roles found to remove.")
        conn.close()
        return
    
    # Ask for confirmation
    print(f"\n{'=' * 60}")
    print(f"Will remove {len(roles_to_remove)} test roles and keep {len(roles_to_keep)} legitimate roles.")
    confirm = input("Proceed with cleanup? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cleanup cancelled.")
        conn.close()
        return
    
    # Delete test roles (cascading deletes will handle related records)
    for role_id, name in roles_to_remove:
        cursor.execute('DELETE FROM roles WHERE id = ?', (role_id,))
        print(f"Deleted: {name}")
    
    conn.commit()
    cursor.execute('SELECT COUNT(*) FROM roles')
    remaining_count = cursor.fetchone()[0]
    print(f"\n✅ Cleanup complete. {remaining_count} roles remain.")
    conn.close()

if __name__ == '__main__':
    cleanup_roles()
