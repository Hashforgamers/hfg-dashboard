import os

class Config:
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "Hash@2025")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    RBAC_ENFORCEMENT = os.getenv("RBAC_ENFORCEMENT", "false").lower() == "true"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "postgresql://postgres:postgres@db:5432/vendor_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Add safe engine options for Neon
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SEC", "1800")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SEC", "30")),
    }
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"

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
    SUBSCRIPTION_DEV_MODE = os.getenv('SUBSCRIPTION_DEV_MODE', 'false').lower() == 'true'
    SUBSCRIPTION_TEST_PRICE = float(os.getenv("SUBSCRIPTION_TEST_PRICE", "1"))
    SUBSCRIPTION_TEST_DURATION_DAYS = int(os.getenv("SUBSCRIPTION_TEST_DURATION_DAYS", "1"))
    ENABLE_DEBUG_SUBSCRIPTION_ENDPOINTS = os.getenv("ENABLE_DEBUG_SUBSCRIPTION_ENDPOINTS", "false").lower() == "true"

    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    TRUST_PROXY = os.getenv("TRUST_PROXY", "true").lower() in ("true", "1", "t", "yes", "y")
    API_ENABLE_TIMING_HEADERS = os.getenv("API_ENABLE_TIMING_HEADERS", "true").lower() in ("true", "1", "t", "yes", "y")
    API_SLOW_REQUEST_MS = int(os.getenv("API_SLOW_REQUEST_MS", "120") or 120)
    API_DEFAULT_CACHE_CONTROL = os.getenv("API_DEFAULT_CACHE_CONTROL", "no-store")
