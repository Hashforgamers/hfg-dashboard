# app/__init__.py
import os
import logging

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from datetime import timedelta 

from app.config import Config
from app.extension.extensions import db
from .routes import dashboard_service
from app.controllers.package_controller import bp_packages
from app.controllers.subscription_controller import bp_subs
from app.controllers.vendor_pc_controller import bp_vendor_pc
from app.controllers.internal_ws_controller import bp_internal_ws
from app.controllers.event_controller import bp_events
from app.controllers.registration_controller import bp_regs
from app.controllers.result_controller import bp_results
from app.controllers.team_controller import bp_teams


from app.services.websocket_service import (
    socketio,
    register_dashboard_events,
    start_upstream_bridge,
)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    
    app.config.setdefault("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "change-me"))
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers"])   # or ["headers","cookies"]
    app.config.setdefault("JWT_HEADER_NAME", "Authorization")
    app.config.setdefault("JWT_HEADER_TYPE", "Bearer")
    app.config.setdefault("JWT_ALGORITHM", "HS256")
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=8))

    CORS(app)

    db.init_app(app)
    Migrate(app, db)   

    app.register_blueprint(dashboard_service, url_prefix='/api')
    app.register_blueprint(bp_packages)
    app.register_blueprint(bp_subs)
    app.register_blueprint(bp_vendor_pc)     
    app.register_blueprint(bp_internal_ws)     
    app.register_blueprint(bp_events)  
    app.register_blueprint(bp_regs)  
    app.register_blueprint(bp_results)  
    app.register_blueprint(bp_teams)  

    socketio.init_app(app, cors_allowed_origins="*")
    register_dashboard_events()

    # Start the upstream bridge to booking service (admin tap ensures ALL events)
    start_upstream_bridge(app)

    return app
