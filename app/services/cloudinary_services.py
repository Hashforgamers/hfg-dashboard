# services/cloudinary_service.py
"""
Updated Cloudinary service for handling game cover images in 'poc' folder
Fixed: Removed invalid format="auto" parameter that was causing API errors
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app
from datetime import datetime
from werkzeug.utils import secure_filename


class CloudinaryMenuImageService:
    """
    Service for handling menu cover images
    Images are uploaded to the 'poc' folder
    """

    @staticmethod
    def is_cloudinary_configured():
        """Checking if Cloudinary credentials are available"""
        return all([
            current_app.config.get('CLOUDINARY_CLOUD_NAME'),
            current_app.config.get('CLOUDINARY_API_KEY'),
            current_app.config.get('CLOUDINARY_API_SECRET')
        ])

    @staticmethod
    def configure_cloudinary():
        """Initialize Cloudinary configuration"""
        try:
            if not CloudinaryMenuImageService.is_cloudinary_configured():
                current_app.logger.warning("Cloudinary credentials not configured")
                return False

            cloudinary.config(
                cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
                api_key=current_app.config.get('CLOUDINARY_API_KEY'),
                api_secret=current_app.config.get('CLOUDINARY_API_SECRET')
            )

            current_app.logger.info("Cloudinary configured successfully for game images")
            return True

        except Exception as e:
            current_app.logger.error(f"Failed to configure Cloudinary: {str(e)}")
            return False

    @staticmethod
    def upload_menu_item_image(image_file, vendor_id, category_name, item_name):
        """Upload menu item image to Cloudinary"""
        try:
            if not image_file or image_file.filename == '':
                return {
                    'success': False,
                    'error': 'No image file provided',
                    'url': None,
                    'public_id': None
                }

            if not CloudinaryMenuImageService.configure_cloudinary():
                return {
                    'success': False,
                    'error': 'Cloudinary not configured',
                    'url': None,
                    'public_id': None
                }

            # Create organized folder structure
            safe_category = secure_filename(category_name.replace(' ', '_').lower())
            safe_item = secure_filename(item_name.replace(' ', '_').lower())
            folder_path = f"EXTRA_SERVICES/vendor_{vendor_id}/{safe_category}"
            public_id = f"{safe_item}_{int(datetime.utcnow().timestamp())}"

            current_app.logger.info(f"Uploading menu item image: {folder_path}/{public_id}")

            upload_result = cloudinary.uploader.upload(
                image_file,
                folder=folder_path,
                public_id=public_id,
                resource_type="image",
                overwrite=False,
                quality="auto:best",
                transformation=[
                    {
                        "width": 400,
                        "height": 300,
                        "crop": "fill",
                        "gravity": "center"
                    }
                ]
            )

            if 'secure_url' in upload_result and 'public_id' in upload_result:
                return {
                    'success': True,
                    'url': upload_result['secure_url'],
                    'public_id': upload_result['public_id'],
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'error': 'Invalid Cloudinary response',
                    'url': None,
                    'public_id': None
                }

        except Exception as e:
            current_app.logger.error(f"Menu item image upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'url': None,
                'public_id': None
            }

    @staticmethod
    def delete_menu_image(public_id):
        """Delete menu item image from Cloudinary"""
        try:
            if not CloudinaryMenuImageService.configure_cloudinary():
                return {'success': False, 'error': 'Cloudinary not configured'}

            result = cloudinary.uploader.destroy(public_id)

            if result.get('result') == 'ok':
                current_app.logger.info(f"Successfully deleted menu image: {public_id}")
                return {'success': True, 'error': None}
            else:
                current_app.logger.warning(f"Failed to delete menu image: {public_id}")
                return {'success': False, 'error': 'Delete failed'}

        except Exception as e:
            current_app.logger.error(f"Error deleting menu image {public_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
