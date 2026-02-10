from flask import Flask, request, make_response
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os
import logging

from app.config import Config
from app.extension.extensions import db
from app.services.websocket_service import socketio, register_dashboard_events, start_upstream_bridge

jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # JWT config
    app.config.setdefault("JWT_SECRET_KEY", "Hash@2025")
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers"])
    app.config.setdefault("JWT_HEADER_NAME", "Authorization")
    app.config.setdefault("JWT_HEADER_TYPE", "Bearer")
    app.config.setdefault("JWT_ALGORITHM", "HS256")
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=8))
    jwt.init_app(app)

    # ✅ CORS - Allow all origins for development
    CORS(app, 
     origins="*",
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     supports_credentials=False
    )


    # ✅ ADD: Global OPTIONS handler BEFORE blueprint registration
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Requested-With")
            response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
            response.headers.add("Access-Control-Max-Age", "3600")
            return response, 200

    # Extensions
    db.init_app(app)
    Migrate(app, db)
    socketio.init_app(app, cors_allowed_origins="*")

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
    from app.controllers.vendor_games import vendor_games_bp
    from app.controllers.admin_games_controller import admin_games_bp
    from app.controllers.pricingController import pricing_blueprint
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
    app.register_blueprint(vendor_games_bp)
    app.register_blueprint(admin_games_bp)
    app.register_blueprint(pricing_blueprint, url_prefix="/api")
    register_commands(app)

    # Socket events
    register_dashboard_events()
    start_upstream_bridge(app)

    return app
