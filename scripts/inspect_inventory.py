import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from core.models.inventory import InventoryTask, InventoryRecord, InventorySnapshot
from extensions import db

app = create_app()
with app.app_context():
    task_id = 10
    task = InventoryTask.query.get(task_id)
    if not task:
        print(f"Task #{task_id} not found.")
    else:
        print(f"--- Task #{task_id} Summary ---")
        print(f"Total: {task.total_assets}, Scanned: {task.scanned_count}")
        
        for s in task.snapshots:
            print(f"ID: {s.id}, AssetID: {repr(s.asset_id)}, Name: {s.asset_name}, Status: {s.status}")
            
        print("\n--- Records ---")
        for r in task.records:
            print(f"ID: {r.id}, AssetID: {repr(r.asset_id)}, Result: {r.result}, Lat: {r.gps_lat}, Lng: {r.gps_lng}, Photo: {r.photo_path}")
            
        # Check type and value equality
        if task.snapshots and task.records:
            snap_aid = task.snapshots[0].asset_id
            rec_aid = task.records[0].asset_id
            print(f"\nComparing AssetIDs: Snap={snap_aid} ({type(snap_aid)}), Rec={rec_aid} ({type(rec_aid)})")
            print(f"Match? {str(snap_aid) == str(rec_aid)}")
