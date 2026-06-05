import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from core.models.inventory import InventoryPlan
from core.models.assets import Asset

def sync_plans():
    app = create_app()
    with app.app_context():
        print("Starting manual sync of completed plans...")
        
        # Get all completed plans
        completed_plans = InventoryPlan.query.filter_by(status='completed').all()
        print(f"Found {len(completed_plans)} completed plans.")
        
        total_updated = 0
        
        for plan in completed_plans:
            print(f"Syncing Plan #{plan.id}: {plan.name}...")
            updated_in_plan = 0
            
            for task in plan.tasks:
                # Map records for quick lookup
                records_map = {r.asset_id: r for r in task.records}
                
                for snap in task.snapshots:
                    asset = Asset.query.get(snap.asset_id)
                    if not asset: continue
                    
                    # Determine final status for this asset from this plan
                    final_result = 'normal' # Default
                    
                    # Check if scanned
                    clean_id = snap.asset_id.split(':')[-1] if ':' in snap.asset_id else snap.asset_id
                    if clean_id in records_map:
                        rec = records_map[clean_id]
                        final_result = rec.result
                    else:
                        # Not scanned = Missing
                        final_result = 'missing'
                        
                    # Apply to Asset
                    if final_result == 'missing':
                        if asset.status != 'lost':
                            print(f"  [UPDATE] Asset {asset.id} ({asset.name}) -> LOST")
                            asset.status = 'lost'
                            updated_in_plan += 1
                    elif final_result == 'damaged':
                        if asset.status != 'maintenance':
                            print(f"  [UPDATE] Asset {asset.id} ({asset.name}) -> MAINTENANCE")
                            asset.status = 'maintenance'
                            updated_in_plan += 1
                    elif final_result in ['normal', 'found']:
                        # If asset was previously lost/maintenance, restore it
                        if asset.status in ['lost', 'maintenance']:
                            print(f"  [UPDATE] Asset {asset.id} ({asset.name}) -> ACTIVE (Restored)")
                            asset.status = 'active'
                            updated_in_plan += 1
                            
            print(f"  -> Updated {updated_in_plan} assets in Plan #{plan.id}")
            total_updated += updated_in_plan
            
        db.session.commit()
        print(f"\nSync complete. Total assets updated across all plans: {total_updated}")

if __name__ == '__main__':
    sync_plans()
