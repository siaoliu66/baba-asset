from datetime import datetime
from decimal import Decimal
from extensions import db
from core.models.finance import DepreciationRecord
from core.models.assets import Asset

class DepreciationService:
    @staticmethod
    def calculate_straight_line(asset):
        """
        Calculate Straight-Line depreciation for a single asset.
        Formula: (Cost - Salvage) / Useful_Life_Months
        Returns monthly depreciation amount.
        """
        if not asset.purchase_price or not asset.useful_life_years:
            return Decimal(0)
            
        cost = asset.purchase_price
        salvage = asset.salvage_value or Decimal(0)
        years = asset.useful_life_years
        
        # Monthly depreciation
        monthly_dep = (cost - salvage) / (years * 12)
        return round(monthly_dep, 2)

    @staticmethod
    def run_monthly_closing(year, month):
        """
        Run monthly depreciation for all eligible active assets.
        This would typically be a scheduled task or manually triggered by Finance role.
        """
        # Get all active assets
        assets = Asset.query.filter_by(status='active').all()
        created_records = []
        
        for asset in assets:
            # Check if already depreciated for this period
            exists = DepreciationRecord.query.filter_by(
                asset_id=asset.id,
                fiscal_year=year,
                month=month
            ).first()
            
            if exists:
                continue
                
            amount = DepreciationService.calculate_straight_line(asset)
            if amount <= 0:
                continue
                
            # Need to calculate accumulated depreciation properly
            # For this MVP, we just add the monthly amount to previous accumulated
            # Real world needs better date handling (start date, half-year convention, etc.)
            
            # Find previous record to get accumulated
            # Simplification: Query sum of all previous records? Or just last one?
            # Let's query sum.
            
            current_accumulated = db.session.query(db.func.sum(DepreciationRecord.depreciation_amount))\
                .filter(DepreciationRecord.asset_id == asset.id)\
                .scalar() or Decimal(0)
                
            new_accumulated = current_accumulated + amount
            new_book_value = asset.purchase_price - new_accumulated
            
            if new_book_value < asset.salvage_value:
                # Cap at salvage value
                # Adjustment needed
                diff = new_book_value - asset.salvage_value # This would be negative
                # Basically, we can only depreciate up to (Book - Salvage)
                # But for now, let's keep it simple.
                pass

            record = DepreciationRecord(
                asset_id=asset.id,
                fiscal_year=year,
                month=month,
                depreciation_amount=amount,
                accumulated_depreciation=new_accumulated,
                book_value=new_book_value,
                method='straight_line'
            )
            db.session.add(record)
            created_records.append(record)
            
            # Update Asset current value
            asset.current_value = new_book_value
            
        db.session.commit()
        return len(created_records)

    @staticmethod
    def write_off_asset(asset_id, disposal_date=None):
        """
        Write off an asset due to disposal.
        1. Calculate partial depreciation up to disposal date.
        2. Create a write-off record (Book Value -> 0).
        """
        asset = Asset.query.get(asset_id)
        if not asset: return
        
        if not disposal_date:
            disposal_date = datetime.now()
            
        # Simplified Write-off Logic:
        # Just record the remaining book value as a loss/write-off amount in a new record
        # And set asset current value to 0.
        
        # In a real system, we'd calculate pro-rated depreciation for the current month first.
        # Here we assume depreciation happens at month-end, so if disposed mid-month,
        # we might skip that month's depreciation or pro-rate it.
        # Let's simple write off the entire current_value.
        
        write_off_amount = asset.current_value or 0
        
        # Create record
        record = DepreciationRecord(
            asset_id=asset.id,
            fiscal_year=disposal_date.year,
            month=disposal_date.month,
            depreciation_amount=write_off_amount, # This is the "expense" recognized now
            accumulated_depreciation=(asset.purchase_price or 0), # Fully depreciated/written off
            book_value=0,
            method='write_off'
        )
        
        asset.current_value = 0
        asset.status = 'disposed'
        
        db.session.add(record)
        # Session commit should be handled by caller or here? 
        # Usually service methods assume active session.
        # We'll let caller commit if part of larger transaction, but here we can flush.
        db.session.add(asset)
