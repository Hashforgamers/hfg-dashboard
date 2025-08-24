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
from .routes import dashboard_service

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

    CORS(app)

    db.init_app(app)
    Migrate(app, db)

    app.register_blueprint(dashboard_service, url_prefix='/api')

    socketio.init_app(app, cors_allowed_origins="*")
    register_dashboard_events()

    # Start the upstream bridge to booking service (admin tap ensures ALL events)
    start_upstream_bridge(app)

    return app
