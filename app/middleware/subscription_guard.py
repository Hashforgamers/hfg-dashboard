from functools import wraps
from flask import jsonify, current_app
from app.services.subscription_service import is_subscription_active


def subscription_required(f):
    """
    Decorator to protect routes that require active subscription
    
    Usage:
        @bp.route('/protected-route')
        @subscription_required
        def my_route(vendor_id):
            # Route logic
            pass
    
    Note: Expects vendor_id in route parameters
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract vendor_id from kwargs (from route)
        vendor_id = kwargs.get('vendor_id')
        
        if not vendor_id:
            current_app.logger.error("subscription_required: vendor_id not found in route")
            return jsonify({
                "error": "Vendor ID required",
                "locked": True
            }), 400
        
        # Check subscription status
        is_active, subscription = is_subscription_active(vendor_id)
        
        if not is_active:
            current_app.logger.warning(f"Vendor {vendor_id} attempted to access protected route with expired subscription")
            return jsonify({
                "error": "Subscription expired",
                "message": "Your subscription has expired. Please renew to continue using the dashboard.",
                "locked": True,
                "redirect": f"/vendor/{vendor_id}/subscription/renew"
            }), 403
        
        # Subscription is active, allow access
        return f(*args, **kwargs)
    
    return decorated_function


def check_subscription_or_warn(f):
    """
    Soft check decorator - warns but doesn't block access
    Useful for non-critical features
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        vendor_id = kwargs.get('vendor_id')
        
        if vendor_id:
            is_active, subscription = is_subscription_active(vendor_id)
            if not is_active:
                current_app.logger.warning(
                    f"Vendor {vendor_id} accessing route with expired subscription"
                )
        
        return f(*args, **kwargs)
    
    return decorated_function
