# services/extra_service_service.py - Complete implementation
from app.extension.extensions import db
from app.models.extraServiceCategory import ExtraServiceCategory
from app.models.extraServiceMenu import ExtraServiceMenu
from app.models.extraServiceMenuImage import ExtraServiceMenuImage
from app.models.amenity import Amenity
from app.services.cloudinary_services import CloudinaryMenuImageService

from flask import current_app
from sqlalchemy.orm import joinedload

class ExtraServiceService:

    @staticmethod
    def _to_int_or_default(value, default=0):
        try:
            if value is None or value == "":
                return int(default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _sync_food_amenity(vendor_id: int):
        """Enable Food amenity if any active menu item exists; disable otherwise."""
        active_item_exists = (
            db.session.query(ExtraServiceMenu.id)
            .join(ExtraServiceCategory, ExtraServiceMenu.category_id == ExtraServiceCategory.id)
            .filter(
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True,
                ExtraServiceMenu.is_active == True,
            )
            .first()
            is not None
        )

        amenity = (
            db.session.query(Amenity)
            .filter(
                Amenity.vendor_id == vendor_id,
                Amenity.name.ilike("%food%"),
            )
            .first()
        )
        if not amenity:
            amenity = Amenity(vendor_id=vendor_id, name="food", available=active_item_exists)
            db.session.add(amenity)
        else:
            amenity.available = bool(active_item_exists)
    
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
                        'stock_quantity': int(menu.stock_quantity) if menu.stock_quantity is not None else None,
                        'stock_unit': menu.stock_unit or 'units',
                        'low_stock_threshold': int(menu.low_stock_threshold or 0),
                        'is_low_stock': bool(
                            menu.stock_quantity is not None
                            and int(menu.stock_quantity) <= int(menu.low_stock_threshold or 0)
                        ),
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
                'stock_quantity': int(menu_item.stock_quantity) if menu_item.stock_quantity is not None else None,
                'stock_unit': menu_item.stock_unit or 'units',
                'low_stock_threshold': int(menu_item.low_stock_threshold or 0),
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
            stock_quantity = data.get('stock_quantity')
            stock_unit = str(data.get('stock_unit') or 'units').strip() or 'units'
            low_stock_threshold = data.get('low_stock_threshold')

            if not name:
               return {'error': 'Menu item name is required'}, 400

            try:
                price = float(price)
                if price < 0:
                    return {'error': 'Price must be non-negative'}, 400
            except (TypeError, ValueError):
                 return {'error': 'Invalid price format'}, 400

            if stock_unit and len(stock_unit) > 32:
                return {'error': 'stock_unit must be 32 characters or fewer'}, 400
            if stock_quantity is not None and stock_quantity != "":
                try:
                    stock_quantity = int(stock_quantity)
                except (TypeError, ValueError):
                    return {'error': 'stock_quantity must be an integer'}, 400
                if stock_quantity < 0:
                    return {'error': 'stock_quantity cannot be negative'}, 400
            else:
                stock_quantity = None

            if low_stock_threshold is not None and low_stock_threshold != "":
                try:
                    low_stock_threshold = int(low_stock_threshold)
                except (TypeError, ValueError):
                    return {'error': 'low_stock_threshold must be an integer'}, 400
                if low_stock_threshold < 0:
                    return {'error': 'low_stock_threshold cannot be negative'}, 400
            else:
                low_stock_threshold = 0

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
                 is_active=True,
                 stock_quantity=stock_quantity,
                 stock_unit=stock_unit,
                 low_stock_threshold=low_stock_threshold
            )

            db.session.add(menu_item)
            db.session.flush()  # Get the ID

        # Handle image upload if provided
            menu_images = []
            if image_file and image_file.filename:
                current_app.logger.info(f"Processing image upload for menu item: {name}")
            
            # Use the dedicated Cloudinary service
                upload_result = CloudinaryMenuImageService.upload_menu_item_image(
                    image_file=image_file,
                    vendor_id=vendor_id,
                    category_name=category.name,
                    item_name=name
                )
            
                if upload_result['success']:
                   current_app.logger.info(f"Image uploaded successfully: {upload_result['url']}")
                
                # Create image record in database
                   menu_image = ExtraServiceMenuImage(
                       menu_id=menu_item.id,
                       image_url=upload_result['url'],
                       public_id=upload_result['public_id']
                    )
                
                   db.session.add(menu_image)
                   db.session.flush()  # Get the image ID
                
                # Add to response images array
                   menu_images.append({
                       'id': menu_image.id,
                        'image_url': upload_result['url'],
                        'public_id': upload_result['public_id']
                    })
                
                else:
                   current_app.logger.error(f"Failed to upload image: {upload_result['error']}")
                # Continue without image if upload fails

            db.session.commit()
            current_app.logger.info(f"Menu item created successfully: {name} (ID: {menu_item.id})")

            # Ensure Food amenity is enabled when at least one menu exists.
            try:
                ExtraServiceService._sync_food_amenity(vendor_id)
                db.session.commit()
            except Exception:
                db.session.rollback()

        # FIXED: Include all necessary fields including images
            result = {
               'id': menu_item.id,
                 'name': menu_item.name,
                 'price': float(menu_item.price),  # Ensure float for JSON consistency
                 'description': menu_item.description,
                 'category_id': menu_item.category_id,
                  'is_active': menu_item.is_active,
                  'stock_quantity': int(menu_item.stock_quantity) if menu_item.stock_quantity is not None else None,
                  'stock_unit': menu_item.stock_unit or 'units',
                  'low_stock_threshold': int(menu_item.low_stock_threshold or 0),
                  'images': menu_images  # CRITICAL: Include images array in response
            }

            return {
               'success': True,
                'message': 'Menu item created successfully',
                'menu_item': result
            }, 201

        except Exception as e:
          db.session.rollback()
          current_app.logger.error(f"Error creating menu item for vendor {vendor_id}: {str(e)}")
          return {'error': str(e)}, 500


    @staticmethod
    def delete_category(vendor_id, category_id):
        """Soft delete category and its menu items."""
        try:
            category = db.session.query(ExtraServiceCategory).filter(
                ExtraServiceCategory.id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True
            ).first()

            if not category:
                return {'error': 'Category not found'}, 404

            # Soft delete category and its menus
            category.is_active = False
            db.session.query(ExtraServiceMenu).filter(
                ExtraServiceMenu.category_id == category_id
            ).update({"is_active": False})

            ExtraServiceService._sync_food_amenity(vendor_id)
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
        """Soft delete menu item."""
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

            menu_item.is_active = False
            ExtraServiceService._sync_food_amenity(vendor_id)
            db.session.commit()

            return {
                'success': True,
                'message': 'Menu item deleted successfully'
            }, 200
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    @staticmethod
    def update_menu_inventory(vendor_id, category_id, menu_id, payload):
        """Set or increment stock quantity for a menu item."""
        try:
            menu_item = db.session.query(ExtraServiceMenu).join(
                ExtraServiceCategory
            ).filter(
                ExtraServiceMenu.id == menu_id,
                ExtraServiceMenu.category_id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id
            ).first()

            if not menu_item:
                return {'success': False, 'error': 'Menu item not found'}, 404

            mode = str(payload.get("mode") or "set").strip().lower()
            if mode not in {"set", "increment", "decrement"}:
                return {'success': False, 'error': 'mode must be set/increment/decrement'}, 400

            quantity_value = payload.get("quantity")
            if quantity_value is None:
                return {'success': False, 'error': 'quantity is required'}, 400

            try:
                quantity_value = int(quantity_value)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'quantity must be an integer'}, 400

            if quantity_value < 0:
                return {'success': False, 'error': 'quantity cannot be negative'}, 400

            current_qty = menu_item.stock_quantity
            if current_qty is None:
                current_qty = 0

            if mode == "set":
                next_qty = quantity_value
            elif mode == "increment":
                next_qty = current_qty + quantity_value
            else:
                next_qty = current_qty - quantity_value

            if next_qty < 0:
                return {'success': False, 'error': 'Resulting stock cannot be negative'}, 400

            stock_unit = payload.get("stock_unit")
            if stock_unit is not None:
                stock_unit = str(stock_unit).strip() or "units"
                if len(stock_unit) > 32:
                    return {'success': False, 'error': 'stock_unit must be 32 characters or fewer'}, 400
                menu_item.stock_unit = stock_unit

            if "low_stock_threshold" in payload:
                threshold = payload.get("low_stock_threshold")
                if threshold in (None, ""):
                    threshold = 0
                try:
                    threshold = int(threshold)
                except (TypeError, ValueError):
                    return {'success': False, 'error': 'low_stock_threshold must be an integer'}, 400
                if threshold < 0:
                    return {'success': False, 'error': 'low_stock_threshold cannot be negative'}, 400
                menu_item.low_stock_threshold = threshold

            menu_item.stock_quantity = next_qty
            db.session.commit()

            return {
                'success': True,
                'message': 'Inventory updated successfully',
                'menu_item': {
                    'id': menu_item.id,
                    'name': menu_item.name,
                    'stock_quantity': int(menu_item.stock_quantity),
                    'stock_unit': menu_item.stock_unit or 'units',
                    'low_stock_threshold': int(menu_item.low_stock_threshold or 0),
                    'is_low_stock': bool(
                        menu_item.stock_quantity is not None
                        and int(menu_item.stock_quantity) <= int(menu_item.low_stock_threshold or 0)
                    ),
                }
            }, 200
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}, 500

    @staticmethod
    def update_menu_item_status(vendor_id, category_id, menu_id, is_active):
        """Activate/deactivate a menu item."""
        try:
            menu_item = db.session.query(ExtraServiceMenu).join(
                ExtraServiceCategory
            ).filter(
                ExtraServiceMenu.id == menu_id,
                ExtraServiceMenu.category_id == category_id,
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True
            ).first()

            if not menu_item:
                return {'success': False, 'error': 'Menu item not found'}, 404

            menu_item.is_active = bool(is_active)
            ExtraServiceService._sync_food_amenity(vendor_id)
            db.session.commit()

            return {
                'success': True,
                'message': 'Menu item status updated successfully',
                'menu_item': {
                    'id': menu_item.id,
                    'name': menu_item.name,
                    'is_active': bool(menu_item.is_active),
                }
            }, 200
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}, 500

    @staticmethod
    def get_low_stock_alerts(vendor_id):
        """Return low-stock menu items for notification surfaces."""
        try:
            rows = db.session.query(ExtraServiceMenu, ExtraServiceCategory).join(
                ExtraServiceCategory, ExtraServiceMenu.category_id == ExtraServiceCategory.id
            ).filter(
                ExtraServiceCategory.vendor_id == vendor_id,
                ExtraServiceCategory.is_active == True,
                ExtraServiceMenu.is_active == True,
                ExtraServiceMenu.stock_quantity.isnot(None),
                ExtraServiceMenu.low_stock_threshold.isnot(None),
                ExtraServiceMenu.low_stock_threshold > 0,
                ExtraServiceMenu.stock_quantity <= ExtraServiceMenu.low_stock_threshold
            ).order_by(ExtraServiceMenu.stock_quantity.asc(), ExtraServiceMenu.name.asc()).all()

            alerts = []
            for menu_item, category in rows:
                alerts.append({
                    "menu_id": int(menu_item.id),
                    "menu_name": menu_item.name,
                    "category_id": int(category.id),
                    "category_name": category.name,
                    "stock_quantity": int(menu_item.stock_quantity or 0),
                    "stock_unit": menu_item.stock_unit or "units",
                    "low_stock_threshold": int(menu_item.low_stock_threshold or 0),
                    "is_low_stock": True,
                    "severity": "critical" if int(menu_item.stock_quantity or 0) <= 0 else "warning",
                })

            return {
                "success": True,
                "alerts": alerts,
                "count": len(alerts)
            }, 200
        except Exception as e:
            return {'success': False, 'error': str(e)}, 500
    
