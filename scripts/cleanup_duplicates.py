import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from core.models.workflow import ApprovalRecord

def run_cleanup():
    app = create_app()
    with app.app_context():
        print("Starting cleanup of stale pending records...")
        
        # Strategy: Group by (reference_type, reference_id)
        # Verify if there is ANY record for this ref that is newer (higher ID) than a pending record
        
        all_records = ApprovalRecord.query.order_by(ApprovalRecord.reference_type, ApprovalRecord.reference_id, ApprovalRecord.id.asc()).all()
        
        groups = {}
        for r in all_records:
            key = (r.reference_type, r.reference_id)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)
            
        deleted_count = 0
        cancelled_count = 0
        
        for key, records in groups.items():
            # records are sorted by ID asc (oldest first)
            
            # Find the "latest" valid state
            # Logic: If I have a record at Step 2 (pending or approved), then any Step 1 PENDING record is stale.
            # Basically, for a given workflow, there should only be ONE active pending record at a time generally.
            # Or simpler: If there is a record with ID > current_record.ID, then current_record shouldn't be pending? 
            # Not necessarily, parallel approvals exist. But here it's linear.
            
            # Let's verify specifically for the case we saw:
            # ID 1 (Step 1, Pending) -> ID 2 (Step 1, Approved) -> ID 4 (Step 2, Pending)
            # ID 1 is clearly zombie.
            
            latest_record = records[-1] # The one with highest ID
            
            print(f"Checking group {key}: {len(records)} records. Latest ID: {latest_record.id} (Step {latest_record.step_order}, {latest_record.status})")
            
            for r in records:
                if r.id == latest_record.id:
                    continue
                    
                # If a record is 'pending' but there is a newer record (by ID) that exists
                if r.status == 'pending':
                    print(f" -> Found stale pending record: ID {r.id} (Step {r.step_order}). Latest is ID {latest_record.id}")
                    
                    # Fix: Mark as 'skipped' or delete. Deleting is cleaner for now to remove ghosts.
                    print(f"    [DELETE] Deleting stale record {r.id}")
                    db.session.delete(r)
                    deleted_count += 1
        
        db.session.commit()
        print(f"\nCleanup complete. Deleted {deleted_count} stale pending records.")

if __name__ == '__main__':
    run_cleanup()
