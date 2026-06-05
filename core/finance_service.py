from datetime import datetime

class FinanceService:
    @staticmethod
    def calculate_depreciation(asset):
        """
        Calculate current residual value using Straight-Line Method.
        Formula: (PurchaseCost - ResidualValue) / UsefulLife
        """
        if not asset.purchase_date or not asset.purchase_cost or not asset.useful_life:
            return asset.purchase_cost or 0
        
        # Years since purchase
        years_passed = (datetime.now().date() - asset.purchase_date).days / 365.25
        
        if years_passed >= asset.useful_life:
            return 1 # Keep 1 for tracking
            
        # Annual depreciation amount
        annual_depr = asset.purchase_cost / asset.useful_life
        
        # Current Value
        current_value = asset.purchase_cost - (annual_depr * years_passed)
        
        return round(max(current_value, 1), 2)
    
    @staticmethod
    def update_asset_valuation(asset):
        """Update and return the asset object with calculated valuation."""
        asset.current_residual_value = FinanceService.calculate_depreciation(asset)
        return asset
