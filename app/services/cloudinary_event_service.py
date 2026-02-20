"""
Cloudinary service for handling event banner images.
Images are uploaded to the 'EVENT_BANNERS' folder.
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app
from datetime import datetime
from werkzeug.utils import secure_filename


class CloudinaryEventImageService:

    @staticmethod
    def is_cloudinary_configured():
        return all([
            current_app.config.get('CLOUDINARY_CLOUD_NAME'),
            current_app.config.get('CLOUDINARY_API_KEY'),
            current_app.config.get('CLOUDINARY_API_SECRET')
        ])

    @staticmethod
    def configure_cloudinary():
        try:
            if not CloudinaryEventImageService.is_cloudinary_configured():
                current_app.logger.warning("Cloudinary credentials not configured")
                return False

            cloudinary.config(
                cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
                api_key=current_app.config.get('CLOUDINARY_API_KEY'),
                api_secret=current_app.config.get('CLOUDINARY_API_SECRET')
            )
            current_app.logger.info("Cloudinary configured for event banners")
            return True

        except Exception as e:
            current_app.logger.error(f"Failed to configure Cloudinary: {str(e)}")
            return False

    @staticmethod
    def upload_event_banner(image_file, vendor_id, event_title):
        """Upload event banner image to Cloudinary — EVENT_BANNERS folder"""
        try:
            if not image_file or image_file.filename == '':
                return {'success': False, 'error': 'No image file provided', 'url': None, 'public_id': None}

            if not CloudinaryEventImageService.configure_cloudinary():
                return {'success': False, 'error': 'Cloudinary not configured', 'url': None, 'public_id': None}

            safe_title = secure_filename(event_title.replace(' ', '_').lower())
            folder_path = "EVENT_BANNERS"
            public_id   = f"vendor_{vendor_id}_{safe_title}_{int(datetime.utcnow().timestamp())}"

            current_app.logger.info(f"Uploading event banner: {folder_path}/{public_id}")

            upload_result = cloudinary.uploader.upload(
                image_file,
                folder=folder_path,
                public_id=public_id,
                resource_type="image",
                overwrite=False,
                quality="auto:best",
                transformation=[
                    {
                        "width": 1200,
                        "height": 630,
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
                return {'success': False, 'error': 'Invalid Cloudinary response', 'url': None, 'public_id': None}

        except Exception as e:
            current_app.logger.error(f"Event banner upload error: {str(e)}")
            return {'success': False, 'error': str(e), 'url': None, 'public_id': None}

    @staticmethod
    def delete_event_banner(public_id):
        """Delete event banner from Cloudinary"""
        try:
            if not CloudinaryEventImageService.configure_cloudinary():
                return {'success': False, 'error': 'Cloudinary not configured'}

            result = cloudinary.uploader.destroy(public_id)

            if result.get('result') == 'ok':
                current_app.logger.info(f"Deleted event banner: {public_id}")
                return {'success': True, 'error': None}
            else:
                return {'success': False, 'error': 'Delete failed'}

        except Exception as e:
            current_app.logger.error(f"Error deleting event banner {public_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
