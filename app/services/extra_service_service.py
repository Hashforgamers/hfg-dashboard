# services/extra_service_service.py - Complete implementation
from app.extension.extensions import db
from app.models.extraServiceCategory import ExtraServiceCategory
from app.models.extraServiceMenu import ExtraServiceMenu
from app.models.extraServiceMenuImage import ExtraServiceMenuImage
from flask import current_app
from sqlalchemy.orm import joinedload

class ExtraServiceService:
    
    @staticmethod
    def get_categories_with_menus(vendor_id):
        """Get all active categories with their menu items for a vendor"""
        try:
            current_app.logger.info(f"Fetching extra services for vendor {vendor_id}")
            
            # Query categories with eager loading of menus and images
            categories = db.session.query(ExtraServiceCategory).options(
                joinedload(ExtraServiceCategory.menus).joinedload(ExtraServiceMenu.images)
            ).filter(
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True
            ).order_by(ExtraServiceCategory.name).all()

            if not categories:
                current_app.logger.info(f"No categories found for vendor {vendor_id}")
                return {
                    'success': True,
                    'message': 'No categories found',
                    'categories': []
                }, 200

            result = []
            total_items = 0
            
            for category in categories:
                # Filter only active menu items
                active_menus = [menu for menu in category.menus if menu.is_active]
                
                menu_items = []
                for menu in active_menus:
                    # Get menu images
                    menu_images = []
                    for img in menu.images:
                        menu_images.append({
                            'id': img.id,
                            'image_url': img.image_url,
                            'public_id': img.public_id
                        })

                    menu_item = {
                        'id': menu.id,
                        'name': menu.name,
                        'price': float(menu.price),  # Ensure float for JSON
                        'description': menu.description or '',
                        'is_active': menu.is_active,
                        'images': menu_images
                    }
                    menu_items.append(menu_item)
                    total_items += 1

                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description or '',
                    'is_active': category.is_active,
                    'menu_count': len(menu_items),
                    'menus': menu_items
                }
                result.append(category_data)

            current_app.logger.info(f"Found {len(categories)} categories with {total_items} total menu items")

            return {
                'success': True,
                'message': f'Found {len(categories)} categories with {total_items} items',
                'categories': result,
                'summary': {
                    'total_categories': len(categories),
                    'total_items': total_items
                }
            }, 200

        except Exception as e:
            current_app.logger.error(f"Error fetching extra services for vendor {vendor_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to fetch extra services: {str(e)}'
            }, 500

    @staticmethod
    def get_menu_item_details(vendor_id, menu_item_id):
        """Get detailed information about a specific menu item"""
        try:
            menu_item = db.session.query(ExtraServiceMenu).join(
                ExtraServiceCategory
            ).options(
                joinedload(ExtraServiceMenu.images),
                joinedload(ExtraServiceMenu.category)
            ).filter(
                ExtraServiceMenu.id == menu_item_id,
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceMenu.is_active == True,
                ExtraServiceCategory.is_active == True
            ).first()

            if not menu_item:
                return {
                    'success': False,
                    'error': 'Menu item not found or inactive'
                }, 404

            images = []
            for img in menu_item.images:
                images.append({
                    'id': img.id,
                    'image_url': img.image_url,
                    'public_id': img.public_id
                })

            result = {
                'id': menu_item.id,
                'name': menu_item.name,
                'price': float(menu_item.price),
                'description': menu_item.description or '',
                'is_active': menu_item.is_active,
                'category': {
                    'id': menu_item.category.id,
                    'name': menu_item.category.name,
                    'description': menu_item.category.description or ''
                },
                'images': images
            }

            return {
                'success': True,
                'menu_item': result
            }, 200

        except Exception as e:
            current_app.logger.error(f"Error fetching menu item {menu_item_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to fetch menu item: {str(e)}'
            }, 500

    @staticmethod
    def create_category(vendor_id, data):
        """Create new service category"""
        try:
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()

            if not name:
                return {'error': 'Category name is required'}, 400

            # Check if category name already exists for this vendor
            existing = db.session.query(ExtraServiceCategory).filter(
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.name.ilike(name)
            ).first()

            if existing:
                return {'error': 'Category name already exists'}, 400

            category = ExtraServiceCategory(
                vendor_id=vendor_id,
                name=name,
                description=description,
                is_active=True
            )

            db.session.add(category)
            db.session.commit()

            return {
                'success': True,
                'message': 'Category created successfully',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description
                }
            }, 201

        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    @staticmethod
    def create_menu_item(vendor_id, category_id, data, image_file=None):
        """Create menu item with optional image"""
        try:
            # Validate category belongs to vendor
            category = db.session.query(ExtraServiceCategory).filter(
                ExtraServiceCategory.id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True
            ).first()

            if not category:
                return {'error': 'Category not found'}, 404

            name = data.get('name', '').strip()
            price = data.get('price')
            description = data.get('description', '').strip()

            if not name:
                return {'error': 'Menu item name is required'}, 400

            try:
                price = float(price)
                if price < 0:
                    return {'error': 'Price must be non-negative'}, 400
            except (TypeError, ValueError):
                return {'error': 'Invalid price format'}, 400

            # Check if menu item name already exists in this category
            existing = db.session.query(ExtraServiceMenu).filter(
                ExtraServiceMenu.category_id == category_id,
                ExtraServiceMenu.name.ilike(name)
            ).first()

            if existing:
                return {'error': 'Menu item name already exists in this category'}, 400

            menu_item = ExtraServiceMenu(
                category_id=category_id,
                name=name,
                price=price,
                description=description,
                is_active=True
            )

            db.session.add(menu_item)
            db.session.flush()  # Get the ID

            # Handle image upload if provided
            image_data = None
            if image_file:
                # You'll need to implement image upload to Cloudinary here
                # This is a placeholder for your existing image upload logic
                pass

            db.session.commit()

            result = {
                'id': menu_item.id,
                'name': menu_item.name,
                'price': menu_item.price,
                'description': menu_item.description,
                'category_id': menu_item.category_id
            }

            return {
                'success': True,
                'message': 'Menu item created successfully',
                'menu_item': result
            }, 201

        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    @staticmethod
    def delete_category(vendor_id, category_id):
        """Delete category (soft delete by setting is_active to False)"""
        try:
            category = db.session.query(ExtraServiceCategory).filter(
                ExtraServiceCategory.id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id
            ).first()

            if not category:
                return {'error': 'Category not found'}, 404

            # Soft delete - set is_active to False
            category.is_active = False
            
            # Also deactivate all menu items in this category
            db.session.query(ExtraServiceMenu).filter(
                ExtraServiceMenu.category_id == category_id
            ).update({'is_active': False})

            db.session.commit()

            return {
                'success': True,
                'message': 'Category deleted successfully'
            }, 200

        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    @staticmethod
    def delete_menu_item(vendor_id, category_id, menu_id):
        """Delete menu item (soft delete by setting is_active to False)"""
        try:
            menu_item = db.session.query(ExtraServiceMenu).join(
                ExtraServiceCategory
            ).filter(
                ExtraServiceMenu.id == menu_id,
                ExtraServiceMenu.category_id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id
            ).first()

            if not menu_item:
                return {'error': 'Menu item not found'}, 404

            # Soft delete
            menu_item.is_active = False
            db.session.commit()

            return {
                'success': True,
                'message': 'Menu item deleted successfully'
            }, 200

        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500
