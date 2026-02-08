from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import datetime

from app.services.subscription_service import (
    get_active_subscription, 
    change_subscription, 
    provision_default_subscription, 
    get_vendor_pc_limit,
    create_subscription,
    renew_subscription,
    is_subscription_active,
    get_package_price  # ✅ ADD THIS
)
from app.services.razorpay_service import create_order, verify_payment_signature, get_payment_details
from app.models.package import Package
from app.extension.extensions import db  # ✅ ADD THIS


bp_subs = Blueprint('subscriptions', __name__)


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


# 🆕 RAZORPAY PAYMENT ENDPOINTS

@bp_subs.post('/create-order')
def create_payment_order(vendor_id):
    """Create Razorpay order for subscription purchase"""
    try:
        data = request.get_json()
        package_code = data.get('package_code')
        action = data.get('action', 'new')
        
        if not package_code:
            return jsonify({"error": "package_code is required"}), 400
        
        package = Package.query.filter_by(code=package_code, active=True).first()
        if not package:
            return jsonify({"error": "Invalid package code"}), 404
        
        price = get_package_price(package_code)
        
        if price == 0:
            return jsonify({
                "error": "Cannot create payment order for free package",
                "message": "This package is free. Use provision-default endpoint instead."
            }), 400
        
        # Create Razorpay order
        order = create_order(
            amount=price,
            currency='INR',
            receipt=f'sub_{vendor_id}_{package_code}_{int(datetime.now().timestamp())}',
            notes={
                'vendor_id': str(vendor_id),
                'package_code': package_code,
                'action': action,
                'dev_mode': str(current_app.config.get('SUBSCRIPTION_DEV_MODE', False))
            }
        )
        
        # ✅ Determine if test or live mode
        key_id = current_app.config['RAZORPAY_KEY_ID']
        is_test_mode = key_id.startswith('rzp_test_')
        
        return jsonify({
            "success": True,
            "order_id": order['id'],
            "amount": price,
            "currency": "INR",
            "key_id": key_id,
            "test_mode": is_test_mode,  # ✅ ADD THIS
            "package": {
                "code": package.code,
                "name": package.name,
                "price": price,
                "pc_limit": package.pc_limit,
                "features": package.features
            },
            "dev_mode": current_app.config.get('SUBSCRIPTION_DEV_MODE', False)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error creating Razorpay order for vendor {vendor_id}: {str(e)}")
        return jsonify({"error": "Failed to create payment order", "details": str(e)}), 500


@bp_subs.post('/verify-payment')
def verify_and_activate(vendor_id):
    """
    Verify Razorpay payment signature and activate subscription
    
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
        
        # Validate required fields
        if not all([order_id, payment_id, signature, package_code]):
            return jsonify({
                "error": "Missing required fields",
                "required": ["razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "package_code"]
            }), 400
        
        # Verify payment signature
        current_app.logger.info(f"Verifying payment for vendor {vendor_id}")
        is_valid = verify_payment_signature(order_id, payment_id, signature)
        
        if not is_valid:
            current_app.logger.error(f"Invalid payment signature for vendor {vendor_id}")
            return jsonify({
                "error": "Payment verification failed",
                "message": "Invalid payment signature. Please contact support."
            }), 400
        
        # Get payment details from Razorpay
        payment_details = get_payment_details(payment_id)
        amount_paid = payment_details['amount'] / 100  # Convert paise to rupees
        payment_status = payment_details.get('status')
        
        if payment_status != 'captured':
            return jsonify({
                "error": "Payment not completed",
                "message": f"Payment status: {payment_status}"
            }), 400
        
        # Create or renew subscription
        if action == 'renew':
            subscription = renew_subscription(
                vendor_id=vendor_id,
                payment_amount=amount_paid,
                external_ref=payment_id
            )
            message = "Subscription renewed successfully!"
        else:
            subscription = create_subscription(
                vendor_id=vendor_id,
                package_code=package_code,
                payment_amount=amount_paid,
                external_ref=payment_id
            )
            message = "Subscription activated successfully!"
        
        current_app.logger.info(f"Subscription activated for vendor {vendor_id}: {subscription.id}")
        
        return jsonify({
            "success": True,
            "message": message,
            "subscription": {
                "id": subscription.id,
                "package_code": subscription.package.code,
                "package_name": subscription.package.name,
                "status": subscription.status.value,
                "pc_limit": subscription.package.pc_limit,
                "period_start": subscription.current_period_start.isoformat(),
                "period_end": subscription.current_period_end.isoformat(),
                "amount_paid": float(subscription.unit_amount),
                "payment_id": payment_id
            }
        }), 200
        
    except ValueError as ve:
        current_app.logger.error(f"ValueError during payment verification: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"Payment verification failed for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "error": "Payment verification failed",
            "message": "An error occurred while processing your payment. Please contact support.",
            "details": str(e)
        }), 500


@bp_subs.get('/history')
def get_subscription_history(vendor_id):
    """Get subscription history for vendor"""
    from app.models.subscription import Subscription
    
    subscriptions = (Subscription.query
                     .filter_by(vendor_id=vendor_id)
                     .order_by(Subscription.created_at.desc())
                     .all())
    
    return jsonify({
        "subscriptions": [
            {
                "id": sub.id,
                "package": {
                    "code": sub.package.code,
                    "name": sub.package.name,
                    "pc_limit": sub.package.pc_limit
                },
                "status": sub.status.value,
                "period_start": sub.current_period_start.isoformat(),
                "period_end": sub.current_period_end.isoformat(),
                "amount_paid": float(sub.unit_amount),
                "payment_ref": sub.external_ref,
                "created_at": sub.created_at.isoformat()
            }
            for sub in subscriptions
        ]
    }), 200


# 🔥 TEMPORARY DEBUG ENDPOINT - REMOVE IN PRODUCTION!
@bp_subs.post('/debug/force-expire')
def debug_force_expire(vendor_id):
    """Force expire subscription for testing - REMOVE IN PRODUCTION"""
    from datetime import timezone
    
    sub = get_active_subscription(vendor_id)
    if sub:
        sub.current_period_end = datetime(2026, 2, 7, tzinfo=timezone.utc)
        db.session.commit()  # ✅ Now db is imported
        current_app.logger.info(f"Debug: Force expired subscription for vendor {vendor_id}")
        return jsonify({"ok": True, "message": f"Subscription {sub.id} expired"})
    
    return jsonify({"error": "No active subscription"}), 404
