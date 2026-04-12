from flask import Flask, request, make_response, g
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os
import logging
import time
import uuid
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extension.extensions import db
from app.services.websocket_service import socketio, register_dashboard_events, start_upstream_bridge
from app.middleware.rbac_guard import enforce_rbac_permissions

jwt = JWTManager()

def _is_insecure_secret(value: str, placeholders: set[str]) -> bool:
    if not value:
        return True
    candidate = str(value).strip()
    if candidate in placeholders:
        return True
    return len(candidate) < 32


def _validate_production_config(app: Flask) -> None:
    app_env = str(app.config.get("APP_ENV", "development")).lower()
    is_production = app_env in {"prod", "production"}
    if not is_production:
        return
    weak_secret = _is_insecure_secret(
        app.config.get("SECRET_KEY", ""),
        {"dev-secret-change-me", "changeme"},
    )
    weak_jwt_secret = _is_insecure_secret(
        app.config.get("JWT_SECRET_KEY", ""),
        {"Hash@2025", "dev", "changeme"},
    )
    if weak_secret or weak_jwt_secret:
        raise RuntimeError(
            "In production, SECRET_KEY and JWT_SECRET_KEY must be strong non-default values with length >= 32."
        )


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    _validate_production_config(app)
    if app.config.get("TRUST_PROXY", True):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # JWT config
    app.config.setdefault("JWT_SECRET_KEY", app.config.get("JWT_SECRET_KEY"))
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers"])
    app.config.setdefault("JWT_HEADER_NAME", "Authorization")
    app.config.setdefault("JWT_HEADER_TYPE", "Bearer")
    app.config.setdefault("JWT_ALGORITHM", "HS256")
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=8))
    jwt.init_app(app)

    # ✅ CORS - allow dashboard origins across all response paths
    CORS(app, 
     origins=app.config.get("CORS_ALLOWED_ORIGINS", "*"),
     methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Cache-Control", "Pragma", "Expires"],
     supports_credentials=False
    )

    def _apply_cors_headers(response):
        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
        response.headers["Vary"] = "Origin"
        requested_headers = request.headers.get("Access-Control-Request-Headers")
        response.headers["Access-Control-Allow-Headers"] = requested_headers if requested_headers else "Content-Type, Authorization, X-Requested-With, Cache-Control, Pragma, Expires"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "3600"
        return response

    # ✅ ADD: Global OPTIONS handler BEFORE blueprint registration
    @app.before_request
    def handle_preflight():
        g._request_started_at = time.perf_counter()
        g.request_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Correlation-Id")
            or str(uuid.uuid4())
        )
        if request.method == "OPTIONS":
            response = make_response()
            response = _apply_cors_headers(response)
            return response, 200

    @app.after_request
    def ensure_cors_on_all_responses(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        started_at = getattr(g, "_request_started_at", None)
        if started_at is not None and app.config.get("API_ENABLE_TIMING_HEADERS", True):
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
            slow_ms = int(app.config.get("API_SLOW_REQUEST_MS", 120) or 120)
            if elapsed_ms >= slow_ms:
                app.logger.warning(
                    "slow_request request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
                    getattr(g, "request_id", "-"),
                    request.method,
                    request.path,
                    response.status_code,
                    elapsed_ms,
                )
        response.headers.setdefault(
            "Cache-Control",
            app.config.get("API_DEFAULT_CACHE_CONTROL", "no-store"),
        )
        return _apply_cors_headers(response)

    @app.before_request
    def handle_rbac_guard():
        return enforce_rbac_permissions()

    # Extensions
    db.init_app(app)
    Migrate(app, db)
    socketio.init_app(app, cors_allowed_origins=app.config.get("CORS_ALLOWED_ORIGINS", "*"))

    # Force model mapper registration order for relationship string references.
    from app.models.bookingSquadMember import BookingSquadMember  # noqa: F401

    # Import blueprints
    from .routes import dashboard_service
    from app.controllers.package_controller import bp_packages
    from app.controllers.subscription_controller import bp_subs
    from app.controllers.vendor_pc_controller import bp_vendor_pc
    from app.controllers.internal_ws_controller import bp_internal_ws
    from app.controllers.event_controller import bp_events
    from app.controllers.registration_controller import bp_regs
    from app.controllers.result_controller import bp_results
    from app.controllers.team_controller import bp_teams
    from app.controllers.review_controller import bp_reviews
    from app.controllers.vendor_games import vendor_games_bp
    from app.controllers.admin_games_controller import admin_games_bp
    from app.controllers.pricingController import pricing_blueprint
    from app.controllers.access_controller import bp_access
    from app.commands import register_commands

    # Register blueprints
    app.register_blueprint(dashboard_service, url_prefix="/api")
    app.register_blueprint(bp_packages, url_prefix='/api/packages')
    app.register_blueprint(bp_subs, url_prefix='/api/vendors/<int:vendor_id>/subscription')
    app.register_blueprint(bp_vendor_pc)
    app.register_blueprint(bp_internal_ws)
    app.register_blueprint(bp_events)
    app.register_blueprint(bp_regs)
    app.register_blueprint(bp_results)
    app.register_blueprint(bp_teams)
    app.register_blueprint(bp_reviews)
    app.register_blueprint(vendor_games_bp)
    app.register_blueprint(admin_games_bp)
    app.register_blueprint(pricing_blueprint, url_prefix="/api")
    app.register_blueprint(bp_access)
    register_commands(app)

    # Socket events
    register_dashboard_events()
    start_upstream_bridge(app)

    return app
