import qrcode
import os
from io import BytesIO
from flask import current_app

class QRHelper:
    @staticmethod
    def generate_asset_qr(asset_id):
        """
        Generate a QR code image for a specific asset ID.
        Returns the relative path to the generated image.
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        # Data format for scanner: APP_ID:ASSET_ID
        data = f"ASSETV2:{asset_id}"
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        filename = f"qr_{asset_id}.png"
        directory = os.path.join(current_app.root_path, 'static', 'uploads', 'qrcodes')
        os.makedirs(directory, exist_ok=True)
        
        filepath = os.path.join(directory, filename)
        img.save(filepath)
        
        return f"uploads/qrcodes/{filename}"
