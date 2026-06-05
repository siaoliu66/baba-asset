import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from core.models.inventory import InventoryTask, InventoryRecord, InventorySnapshot

app = create_app()
with app.app_context():
    task_id = 11
    print(f"--- Debugging Task #{task_id} ---")
    task = InventoryTask.query.get(task_id)
    if not task:
        print("Task not found")
        exit()

    print(f"Task Status: {task.status}")
    print(f"Scanned Count: {task.scanned_count}")
    print(f"Total Assets: {task.total_assets}")

    print("\n--- Snapshots (Expected) ---")
    snapshots = InventorySnapshot.query.filter_by(task_id=task_id).all()
    snap_ids = []
    for s in snapshots:
        val = s.asset_id
        print(f"ID: '{val}' (len={len(val)}) | Hex: {val.encode('utf-8').hex()}")
        snap_ids.append(val)

    print("\n--- Records (Actual) ---")
    records = InventoryRecord.query.filter_by(task_id=task_id).all()
    rec_ids = []
    for r in records:
        val = r.asset_id
        print(f"ID: '{val}' (len={len(val)}) | Hex: {val.encode('utf-8').hex()}")
        rec_ids.append(val)

    print("\n--- Matching Test ---")
    for s_id in snap_ids:
        # Simulate current logic
        clean_s = s_id.split(':')[-1] if ':' in s_id else s_id
        clean_s = clean_s.strip()
        
        found = False
        for r_id in rec_ids:
            clean_r = r_id.split(':')[-1] if ':' in r_id else r_id
            clean_r = clean_r.strip()
            
            if clean_s == clean_r:
                print(f"MATCH FOUND: Snap '{s_id}' == Rec '{r_id}' (Clean: '{clean_s}')")
                found = True
                break
        
        if not found:
            print(f"NO MATCH for Snap '{s_id}'. Clean S: '{clean_s}'")
            # Try to see what Rec cleans to
            for r_id in rec_ids:
                clean_r = r_id.split(':')[-1] if ':' in r_id else r_id
                clean_r = clean_r.strip()
                print(f"   vs Rec '{r_id}' -> Clean R: '{clean_r}'")
