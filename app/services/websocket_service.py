import time
import socketio
import json
import threading
from flask import Flask, current_app
import os 

from flask_socketio import SocketIO

socketio_client = socketio.Client()

def connect_to_5054(app):
    """ Connect to Flask-SocketIO server at 5054 with proper app context and wait until fully connected """
    with app.app_context():
        try:
            app.logger.info("Connecting to Flask-SocketIO ws://127.0.0.1:5054")
            socket_url=os.getenv("BOOKING_WS_URL", "wss://hfg-booking.onrender.com")
            socketio_client.connect(socket_url)  # Ensure correct address
            
            # ✅ Wait for connection
            timeout = 5  # Max wait time in seconds
            start_time = time.time()
            while not socketio_client.connected:
                if time.time() - start_time > timeout:
                    app.logger.error("❌ Connection timeout. Could not connect to WebSocket.")
                    return
                time.sleep(0.1)

            app.logger.info("✅ Connected to Flask-SocketIO at 5054")

        except Exception as e:
            app.logger.error(f"❌ Connection to 5054 failed: {e}")

def handle_message_with_app(app, data):
    """ Handle messages from 5054 inside app context """
    with app.app_context():
        app.logger.info(f"📥 Received from 5054: {data}")

        # Ensure data is a dictionary
        processed_data = data if isinstance(data, dict) else json.loads(data)
        
        app.logger.info(f"📤 Emitting processed data to 5056: {processed_data}")

        # ✅ Retry until the socket client is connected
        timeout = 5
        start_time = time.time()
        while not socketio_client.connected:
            if time.time() - start_time > timeout:
                app.logger.error("❌ SocketIO client is not connected after waiting. Cannot emit event.")
                return
            time.sleep(0.1)

        # ✅ Emit the processed message
        socketio_client.emit('message', {"data": "Sample to WebSocket server"})
        app.logger.info("✅ Emit the processed message")


@socketio_client.on("message")
def handle_message(data):
    """ Event handler for incoming messages """
    global flask_app

    if flask_app is None:
        raise RuntimeError("Flask app is not initialized")

    handle_message_with_app(flask_app, data)


def start_socket_client(app):
    """ Start Socket.IO Client in a separate thread with proper app reference """
    global flask_app
    flask_app = app  # Store app globally so it can be accessed inside event handlers

    def start_thread():
        connect_to_5054(app)

    thread = threading.Thread(target=start_thread, daemon=True)
    thread.start()


# Add WebSocket event handler for 'bookslot'
@socketio_client.on('slot_booked')
def handle_bookslot(data):
    """ Handle the booking status from 5054 """
    global flask_app

    if flask_app is None:
        raise RuntimeError("Flask app is not initialized")

    with flask_app.app_context():
        flask_app.logger.info(f"📥 Booking status received from 5054: {data}")

        # Log if data is undefined
        if not data:
            flask_app.logger.error("❌ Data is undefined or malformed.")

        # Process valid data
        if isinstance(data, dict):
            slot_id = data.get("slot_id")
            status = data.get("status")
            
            if slot_id and status:
                flask_app.logger.info(f"Slot {slot_id} booking status: {status}")
                # Emit a response or take appropriate action here
                socketio = current_app.extensions['socketio']
                socketio.emit('booking_status_received', {"slot_id": slot_id, "status": status})
            else:
                flask_app.logger.error("❌ Missing slot_id or status.")
        else:
            flask_app.logger.error(f"❌ Invalid data type received for bookslot event: {data}")


def register_socketio_events(socket: SocketIO):
    """
    Register WebSocket events with the given SocketIO instance.
    This will allow all controllers to access these events.
    """
    # Declare the socketio as a global variable
    socketio = socket  # Set the global socketio variable

    @socketio.on('slot_booked_demo')
    def handle_slot_booked(data):
        try:
            # Parse the JSON string into a dictionary
            data = json.loads(data)
            print(f"Slot {data['slot_id']} has been booked. Status: {data['status']}")
            socketio.emit('slot_booked', {'slot_id': data['slot_id'], 'status': 'booked'})
        except json.JSONDecodeError:
            print(f"Failed to decode JSON: {data}")
            
    @socketio.on('booking_updated_demo')
    def handle_booking_updated(data):
        print(f"Booking {data['booking_id']} updated. Status: {data['status']}")
        socketio.emit('booking_updated', data)