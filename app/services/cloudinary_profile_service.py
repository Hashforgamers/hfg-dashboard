"""
Cloudinary service for handling vendor profile images
Images are uploaded to 'profile_images/vendor_{vendor_id}' folder structure
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app
from datetime import datetime

class CloudinaryProfileImageService:
    """
    Service to handle vendor profile image uploads.
    Images are stored in 'profile_images/vendor_{vendor_id}' folder structure.
    """

    @staticmethod
    def is_cloudinary_configured():
        """Check if Cloudinary credentials are available"""
        return all([
            current_app.config.get('CLOUDINARY_CLOUD_NAME'),
            current_app.config.get('CLOUDINARY_API_KEY'),
            current_app.config.get('CLOUDINARY_API_SECRET')
        ])

    @staticmethod
    def configure_cloudinary():
        """Initialize Cloudinary configuration"""
        try:
            if not CloudinaryProfileImageService.is_cloudinary_configured():
                current_app.logger.warning("Cloudinary credentials not configured")
                return False

            cloudinary.config(
                cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
                api_key=current_app.config.get('CLOUDINARY_API_KEY'),
                api_secret=current_app.config.get('CLOUDINARY_API_SECRET')
            )

            current_app.logger.info("Cloudinary configured successfully for profile images")
            return True

        except Exception as e:
            current_app.logger.error(f"Failed to configure Cloudinary: {str(e)}")
            return False

    @staticmethod
    def upload_profile_image(image_file, vendor_id):
        """Upload profile image to Cloudinary in individual vendor folder"""
        try:
            if not image_file or image_file.filename == '':
                return {
                    'success': False,
                    'error': 'No image file provided',
                    'url': None,
                    'public_id': None
                }

            if not CloudinaryProfileImageService.configure_cloudinary():
                return {
                    'success': False,
                    'error': 'Cloudinary not configured',
                    'url': None,
                    'public_id': None
                }

            # Create individual folder for each vendor
            vendor_folder = f"profile_images/vendor_{vendor_id}"
            # Use consistent public_id so it overwrites previous profile image
            public_id = "profile_image"
            
            current_app.logger.info(f"Uploading profile image to: {vendor_folder}/{public_id}")

            upload_result = cloudinary.uploader.upload(
                image_file,
                folder=vendor_folder,
                public_id=public_id,
                overwrite=True,  # Replace existing profile image
                resource_type="image",
                quality="auto:good",
                transformation=[
                    {
                        "width": 400,
                        "height": 400,
                        "crop": "fill",
                        "gravity": "face"  # Focus on face when cropping
                    },
                    {"quality": "auto:good"},  # Optimize quality
                    {"fetch_format": "auto"}   # Auto format (webp when supported)
                ]
            )

            if 'secure_url' in upload_result and 'public_id' in upload_result:
                current_app.logger.info(f"Profile image uploaded successfully for vendor {vendor_id}")
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
            current_app.logger.error(f"Profile image upload error for vendor {vendor_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'url': None,
                'public_id': None
            }

    @staticmethod
    def delete_profile_image(public_id):
        """Delete profile image from Cloudinary"""
        try:
            if not CloudinaryProfileImageService.configure_cloudinary():
                return {'success': False, 'error': 'Cloudinary not configured'}

            result = cloudinary.uploader.destroy(public_id)

            if result.get('result') == 'ok':
                current_app.logger.info(f"Successfully deleted profile image: {public_id}")
                return {'success': True, 'error': None}
            else:
                current_app.logger.warning(f"Failed to delete profile image: {public_id}")
                return {'success': False, 'error': 'Delete failed'}

        except Exception as e:
            current_app.logger.error(f"Error deleting profile image {public_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
