import razorpay
import hmac
import hashlib
from datetime import datetime, timezone  # ✅ ADD timezone
from flask import current_app


def get_razorpay_client():
    """Initialize Razorpay client with keys from config"""
    return razorpay.Client(
        auth=(
            current_app.config['RAZORPAY_KEY_ID'],
            current_app.config['RAZORPAY_KEY_SECRET']
        )
    )


def create_order(amount, currency='INR', receipt=None, notes=None):
    """
    Create a Razorpay order for subscription payment
    
    Args:
        amount: Amount in INR (will be converted to paise)
        currency: Currency code (default: INR)
        receipt: Unique receipt ID
        notes: Dict of additional notes
    
    Returns:
        dict: Razorpay order object with id, amount, currency, etc.
    """
    client = get_razorpay_client()
    
    # Convert amount to paise (Razorpay requires smallest currency unit)
    # ₹1 = 100 paise
    amount_paise = int(float(amount) * 100)
    
    order_data = {
        'amount': amount_paise,
        'currency': currency,
        'receipt': receipt or f'sub_{int(datetime.now(timezone.utc).timestamp())}',  # ✅ FIXED
        'notes': notes or {}
    }
    
    current_app.logger.info(f"Creating Razorpay order: {order_data}")
    order = client.order.create(data=order_data)
    current_app.logger.info(f"Razorpay order created: {order['id']}")
    
    return order


def verify_payment_signature(order_id, payment_id, signature):
    """
    Verify Razorpay payment signature for security
    
    Args:
        order_id: Razorpay order ID
        payment_id: Razorpay payment ID
        signature: Signature from Razorpay callback
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    secret = current_app.config['RAZORPAY_KEY_SECRET']
    
    # Create signature verification string
    message = f"{order_id}|{payment_id}"
    
    generated_signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    is_valid = hmac.compare_digest(generated_signature, signature)
    
    current_app.logger.info(f"Payment signature verification: {is_valid}")
    return is_valid


def get_payment_details(payment_id):
    """
    Fetch payment details from Razorpay
    
    Args:
        payment_id: Razorpay payment ID
        
    Returns:
        dict: Payment details including amount, status, method, etc.
    """
    client = get_razorpay_client()
    payment = client.payment.fetch(payment_id)
    current_app.logger.info(f"Fetched payment details: {payment_id}")
    return payment


def get_test_price():
    """Get test price for development mode"""
    if current_app.config.get('SUBSCRIPTION_DEV_MODE', False):
        return current_app.config.get('SUBSCRIPTION_TEST_PRICE', 1)
    return None

def get_order_details(order_id):
    """
    Get order details from Razorpay
    
    Args:
        order_id: Razorpay order ID
        
    Returns:
        dict: Order details including payment status
    """
    client = get_razorpay_client()
    order = client.order.fetch(order_id)
    current_app.logger.info(f"Fetched order details: {order_id}")
    return order
