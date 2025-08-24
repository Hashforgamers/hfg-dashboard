# app/__init__.py
from gevent import monkey
monkey.patch_all()

import os
import logging

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from app.config import Config
from app.extension.extensions import db

# Dashboard Socket.IO server and event registration
from app.services.websocket_service import (
    socketio,                  # server-side Socket.IO instance
    register_dashboard_events, # registers local socket events, incl. dynamic vendor join
    start_upstream_bridge,     # starts single upstream client to booking service
)

# Flask blueprint(s)
from .routes import dashboard_service


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Logging baseline
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # CORS
    CORS(app)

    # DB and migrations
    db.init_app(app)
    Migrate(app, db)

    # Blueprints
    app.register_blueprint(dashboard_service, url_prefix="/api")

    # Initialize Socket.IO for dashboard clients
    # Note: If you need stricter CORS, replace "*" with your allowed origins list.
    socketio.init_app(app, cors_allowed_origins="*")

    # Register dashboard socket events:
    # - "dashboard_join_vendor" lets clients declare vendor_id
    # - joins local room vendor_{vendor_id}
    # - ensures upstream booking bridge is subscribed to that vendor
    register_dashboard_events()

    # Start the upstream bridge to the booking service once.
    # Vendors are joined dynamically when dashboard clients ask for them.
    start_upstream_bridge(app)

    return app
