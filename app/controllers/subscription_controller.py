from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.services.subscription_service import (
    get_active_subscription, 
    change_subscription, 
    provision_default_subscription, 
    get_vendor_pc_limit,
    create_subscription,
    renew_subscription,
    is_subscription_active
)
from app.services.razorpay_service import create_order, verify_payment_signature, get_payment_details
from app.models.package import Package


bp_subs = Blueprint('subscriptions', __name__, url_prefix='/api/vendors/<int:vendor_id>/subscription')


@bp_subs.get('/')
def get_subscription(vendor_id):
    """Get current subscription status for vendor"""
    sub = get_active_subscription(vendor_id)
    if not sub:
        return jsonify({"status": "none", "has_active": False}), 200
    
    is_active, _ = is_subscription_active(vendor_id)
    
    return jsonify({
        "status": sub.status.value,
        "has_active": is_active,
        "package": {
            "id": sub.package.id,
            "code": sub.package.code,
            "name": sub.package.name,
            "pc_limit": sub.package.pc_limit,
            "price": float(sub.package.features.get('price_inr', 0))
        },
        "pc_limit": sub.package.pc_limit,
        "period_start": sub.current_period_start.isoformat(),
        "period_end": sub.current_period_end.isoformat(),
        "amount_paid": float(sub.unit_amount)
    }), 200


@bp_subs.get('/status')
def check_subscription_status(vendor_id):
    """Check if vendor subscription is active (for dashboard lock)"""
    is_active, sub = is_subscription_active(vendor_id)
    
    return jsonify({
        "is_active": is_active,
        "locked": not is_active,
        "message": "Subscription expired. Please renew to continue." if not is_active else "Active"
    }), 200


@bp_subs.post('/provision-default')
def provision_default(vendor_id):
    """Provision default subscription for new vendor"""
    provision_default_subscription(vendor_id)
    return jsonify({"ok": True}), 201


@bp_subs.post('/change')
def change(vendor_id):
    """Change subscription package (admin use)"""
    data = request.get_json()
    pkg = data['package_code']
    immediate = data.get('immediate', True)
    unit_amount = data.get('unit_amount', 0)
    res = change_subscription(vendor_id, pkg, immediate=immediate, unit_amount=unit_amount)
    return jsonify({"ok": True, "new_package": res.package.code}), 200


@bp_subs.get('/limit')
def get_limit(vendor_id):
    """Get PC limit for vendor"""
    return jsonify({"pc_limit": get_vendor_pc_limit(vendor_id)}), 200


# 🆕 NEW ENDPOINTS FOR RAZORPAY PAYMENT

@bp_subs.post('/create-order')
def create_payment_order(vendor_id):
    """
    Create Razorpay order for subscription purchase
    
    Request body:
    {
        "package_code": "base" | "grow" | "elite",
        "action": "new" | "renew"  // optional, default: "new"
    }
    """
    try:
        data = request.get_json()
        package_code = data.get('package_code')
        action = data.get('action', 'new')  # 'new' or 'renew'
        
        if not package_code:
            return jsonify({"error": "package_code is required"}), 400
        
        # Get package details
        package = Package.query.filter_by(code=package_code, active=True).first()
        if not package:
            return jsonify({"error": "Invalid package"}), 404
        
        # Get price from package features
        price = float(package.features.get('price_inr', 0))
        
        if price == 0:
            return jsonify({"error": "Cannot create order for free package"}), 400
        
        # Create Razorpay order
        order = create_order(
            amount=price,
            currency='INR',
            receipt=f'sub_{vendor_id}_{package_code}_{int(datetime.now().timestamp())}',
            notes={
                'vendor_id': vendor_id,
                'package_code': package_code,
                'action': action
            }
        )
        
        return jsonify({
            "order_id": order['id'],
            "amount": price,
            "currency": "INR",
            "key_id": current_app.config['RAZORPAY_KEY_ID'],
            "package": {
                "code": package.code,
                "name": package.name,
                "price": price,
                "pc_limit": package.pc_limit
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error creating Razorpay order: {str(e)}")
        return jsonify({"error": "Failed to create order"}), 500


@bp_subs.post('/verify-payment')
def verify_and_activate(vendor_id):
    """
    Verify Razorpay payment and activate subscription
    
    Request body:
    {
        "razorpay_order_id": "order_xxx",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_signature": "signature_xxx",
        "package_code": "base",
        "action": "new" | "renew"
    }
    """
    try:
        data = request.get_json()
        
        order_id = data.get('razorpay_order_id')
        payment_id = data.get('razorpay_payment_id')
        signature = data.get('razorpay_signature')
        package_code = data.get('package_code')
        action = data.get('action', 'new')
        
        if not all([order_id, payment_id, signature, package_code]):
            return jsonify({"error": "Missing required payment fields"}), 400
        
        # Verify signature
        is_valid = verify_payment_signature(order_id, payment_id, signature)
        
        if not is_valid:
            return jsonify({"error": "Invalid payment signature"}), 400
        
        # Get payment details from Razorpay
        payment_details = get_payment_details(payment_id)
        amount_paid = payment_details['amount'] / 100  # Convert paise to rupees
        
        # Create or renew subscription
        if action == 'renew':
            subscription = renew_subscription(
                vendor_id=vendor_id,
                payment_amount=amount_paid,
                external_ref=payment_id
            )
        else:
            subscription = create_subscription(
                vendor_id=vendor_id,
                package_code=package_code,
                payment_amount=amount_paid,
                external_ref=payment_id
            )
        
        return jsonify({
            "success": True,
            "message": "Subscription activated successfully!",
            "subscription": {
                "id": subscription.id,
                "package": subscription.package.name,
                "status": subscription.status.value,
                "period_end": subscription.current_period_end.isoformat(),
                "amount_paid": float(subscription.unit_amount)
            }
        }), 200
        
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"Payment verification failed: {str(e)}")
        return jsonify({"error": "Payment verification failed"}), 500


from datetime import datetime
