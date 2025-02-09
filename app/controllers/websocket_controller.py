from flask import current_app
from flask_socketio import emit
from app.services.websocket_service import socketio

@socketio.on("processed_slot")
def handle_processed_slot(data):
    """ Handle the processed event and emit a final event """
    with current_app.app_context():
        current_app.logger.info("[🎯 WS Event] Received in Flask: %s", data)

    emit("final_event", data, broadcast=True)
