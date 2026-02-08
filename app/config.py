import os

class Config:
    SECRET_KEY = "DEV"
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "postgresql://postgres:postgres@db:5432/vendor_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Add safe engine options for Neon
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # test connection before use
        "pool_recycle": 1800,    # recycle every 30min
        "pool_size": 5,          # keep small pool
        "max_overflow": 10       # allow bursts
    }

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

    # Booking bridge
    BOOKING_SOCKET_URL = os.getenv("BOOKING_SOCKET_URL", "wss://hfg-booking-hmnx.onrender.com")
    BOOKING_BRIDGE_NAMESPACE = os.getenv("BOOKING_BRIDGE_NAMESPACE") 
    
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
    
     # 🆕 Development Mode Settings
    SUBSCRIPTION_DEV_MODE = os.getenv('SUBSCRIPTION_DEV_MODE', 'true').lower() == 'true'
    SUBSCRIPTION_TEST_PRICE = 1  # ₹1 for testing
    SUBSCRIPTION_TEST_DURATION_DAYS = 1  # 1 day for testing
