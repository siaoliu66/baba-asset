import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from core.models.workflow import ApprovalRecord

app = create_app()

with app.app_context():
    print("Checking for duplicate pending records...")
    
    # Check specifically for reference_id 10 (Inventory Task #10)
    target_ref_id = 10
    records = ApprovalRecord.query.filter_by(
        reference_type='inventory_task',
        reference_id=target_ref_id
    ).order_by(ApprovalRecord.id.asc()).all()
    
    print(f"Found {len(records)} records for Inventory Task #{target_ref_id}:")
    for r in records:
        print(f" - ID: {r.id}, Status: {r.status}, Step: {r.step_order}, Approver: {r.selected_approver_id}")
        
    # Check for all duplicates
    all_pending = ApprovalRecord.query.filter_by(status='pending').all()
    pending_map = {}
    duplicates = []
    
    for r in all_pending:
        key = (r.reference_type, r.reference_id)
        if key in pending_map:
            duplicates.append(r)
            print(f"Duplicate found! Record {r.id} is a duplicate of {pending_map[key].id} for {key}")
        else:
            pending_map[key] = r
            
    print(f"\nTotal duplicates detected: {len(duplicates)}")
