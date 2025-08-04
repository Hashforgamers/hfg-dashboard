from gevent import monkey
monkey.patch_all()

from flask import Flask
from flask_socketio import SocketIO
from app.services.websocket_service import start_socket_client, register_socketio_events
from .config import Config

from flask_cors import CORS

from .routes import dashboard_service
from app.extension.extensions import db
from flask_migrate import Migrate


# Initialize socketio globally, but it will be initialized in create_app
socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.logger.setLevel("INFO")

    app.config.from_object(Config)

    db.init_app(app)
    migrate = Migrate(app, db)

    app.register_blueprint(dashboard_service, url_prefix='/api')

    # Initialize SocketIO with the app
    socketio.init_app(app)

    register_socketio_events(socketio)  # Pass socketio here to register events

    # Start the socket client
    start_socket_client(app)

    return app
