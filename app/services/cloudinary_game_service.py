# app/services/cloudinary_game_service.py
"""
Cloudinary service for handling game cover images
Images are uploaded to the 'GAME_COVERS' folder
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app
from datetime import datetime
from werkzeug.utils import secure_filename


class CloudinaryGameImageService:
    """
    Service for handling game cover images
    Images are uploaded to the 'GAME_COVERS' folder
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
            if not CloudinaryGameImageService.is_cloudinary_configured():
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
    def upload_game_cover_image(image_file, game_id, game_name):
        """Upload game cover image to Cloudinary"""
        try:
            if not image_file or image_file.filename == '':
                return {
                    'success': False,
                    'error': 'No image file provided',
                    'url': None,
                    'public_id': None
                }

            if not CloudinaryGameImageService.configure_cloudinary():
                return {
                    'success': False,
                    'error': 'Cloudinary not configured',
                    'url': None,
                    'public_id': None
                }

            # Create organized folder structure for game covers
            safe_game_name = secure_filename(game_name.replace(' ', '_').lower())
            folder_path = f"GAME_COVERS"
            public_id = f"{safe_game_name}_game_{game_id}_{int(datetime.utcnow().timestamp())}"

            current_app.logger.info(f"Uploading game cover image: {folder_path}/{public_id}")

            upload_result = cloudinary.uploader.upload(
                image_file,
                folder=folder_path,
                public_id=public_id,
                resource_type="image",
                overwrite=False,
                quality="auto:best",
                transformation=[
                    {
                        "width": 600,
                        "height": 800,
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
            current_app.logger.error(f"Game cover image upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'url': None,
                'public_id': None
            }

    @staticmethod
    def delete_game_image(public_id):
        """Delete game cover image from Cloudinary"""
        try:
            if not CloudinaryGameImageService.configure_cloudinary():
                return {'success': False, 'error': 'Cloudinary not configured'}

            result = cloudinary.uploader.destroy(public_id)

            if result.get('result') == 'ok':
                current_app.logger.info(f"Successfully deleted game image: {public_id}")
                return {'success': True, 'error': None}
            else:
                current_app.logger.warning(f"Failed to delete game image: {public_id}")
                return {'success': False, 'error': 'Delete failed'}

        except Exception as e:
            current_app.logger.error(f"Error deleting game image {public_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
