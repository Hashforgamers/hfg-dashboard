from datetime import datetime
from app.extension.extensions import db
from app.models.extraServiceCategory import ExtraServiceCategory
from app.models.extraServiceMenu import ExtraServiceMenu
from app.models.extraServiceMenuImage import ExtraServiceMenuImage
from app.services.cloudinary_services import CloudinaryMenuImageService
from flask import current_app

class ExtraServiceService:
    
    @staticmethod
    def create_category(vendor_id, data):
        """Create a new service category"""
        try:
            name = data.get('name')
            description = data.get('description', '')

            if not name:
                return {"error": "Category name required"}, 400

            category = ExtraServiceCategory(
                vendor_id=vendor_id,
                name=name,
                description=description,
                is_active=True
            )
            
            db.session.add(category)
            db.session.commit()
            
            return {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "is_active": category.is_active
            }, 201
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating category: {str(e)}")
            return {"error": str(e)}, 500

    @staticmethod
    def create_menu_item(vendor_id, category_id, data, image_file=None):
        """Create menu item with optional image"""
        try:
            # Verify category belongs to vendor
            category = ExtraServiceCategory.query.filter_by(
                id=category_id, 
                vendor_id=vendor_id, 
                is_active=True
            ).first()
            
            if not category:
                return {"error": "Category not found"}, 404

            name = data.get('name')
            price = data.get('price')
            description = data.get('description', '')

            if not name or price is None:
                return {"error": "Menu name and price required"}, 400

            # Create menu item
            menu = ExtraServiceMenu(
                category_id=category.id,
                name=name,
                price=float(price),
                description=description,
                is_active=True
            )
            
            db.session.add(menu)
            db.session.flush()  # Get menu.id

            # Handle image upload
            image_data = None
            if image_file:
                upload_result = CloudinaryMenuImageService.upload_menu_item_image(
                    image_file, 
                    vendor_id,
                    category.name, 
                    name
                )
                
                if upload_result['success']:
                    menu_image = ExtraServiceMenuImage(
                        menu_id=menu.id,
                        image_url=upload_result['url'],
                        public_id=upload_result['public_id'],
                        alt_text=f"{name} image",
                        is_primary=True,
                        is_active=True
                    )
                    db.session.add(menu_image)
                    
                    image_data = {
                        "image_url": menu_image.image_url,
                        "public_id": menu_image.public_id
                    }

            db.session.commit()
            
            return {
                "id": menu.id,
                "name": menu.name,
                "price": menu.price,
                "description": menu.description,
                "is_active": menu.is_active,
                "image": image_data
            }, 201
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating menu item: {str(e)}")
            return {"error": str(e)}, 500

    @staticmethod
    def get_categories_with_menus(vendor_id):
        """Get all categories with menu items"""
        try:
            categories = ExtraServiceCategory.query.filter_by(
                vendor_id=vendor_id, 
                is_active=True
            ).all()
            
            result = []
            for category in categories:
                menus = []
                for menu in category.menus:
                    if menu.is_active:
                        # Get primary image
                        primary_image = None
                        for img in menu.images:
                            if img.is_active and img.is_primary:
                                primary_image = img.image_url
                                break
                        
                        menus.append({
                            "id": menu.id,
                            "name": menu.name,
                            "price": menu.price,
                            "description": menu.description,
                            "is_active": menu.is_active,
                            "image": primary_image
                        })
                
                result.append({
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                    "items": menus
                })
            
            return result, 200
            
        except Exception as e:
            current_app.logger.error(f"Error fetching categories: {str(e)}")
            return {"error": str(e)}, 500

    @staticmethod
    def delete_category(vendor_id, category_id):
        """Delete category and cleanup images"""
        try:
            category = ExtraServiceCategory.query.filter_by(
                id=category_id, 
                vendor_id=vendor_id, 
                is_active=True
            ).first()
            
            if not category:
                return {"error": "Category not found"}, 404

            # Delete images from Cloudinary
            for menu in category.menus:
                if menu.is_active:
                    for image in menu.images:
                        if image.is_active:
                            CloudinaryMenuImageService.delete_menu_image(image.public_id)
                            image.is_active = False
                    menu.is_active = False

            category.is_active = False
            db.session.commit()
            
            return {"message": "Category deleted successfully"}, 200
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting category: {str(e)}")
            return {"error": str(e)}, 500

    @staticmethod
    def delete_menu_item(vendor_id, category_id, menu_id):
        """Delete menu item and cleanup images"""
        try:
            category = ExtraServiceCategory.query.filter_by(
                id=category_id, 
                vendor_id=vendor_id, 
                is_active=True
            ).first()
            
            if not category:
                return {"error": "Category not found"}, 404
                
            menu = ExtraServiceMenu.query.filter_by(
                id=menu_id, 
                category_id=category.id, 
                is_active=True
            ).first()
            
            if not menu:
                return {"error": "Menu item not found"}, 404

            # Delete images from Cloudinary
            for image in menu.images:
                if image.is_active:
                    CloudinaryMenuImageService.delete_menu_image(image.public_id)
                    image.is_active = False
            
            menu.is_active = False
            db.session.commit()
            
            return {"message": "Menu item deleted successfully"}, 200
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting menu item: {str(e)}")
            return {"error": str(e)}, 500
