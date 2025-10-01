from gevent import monkey
monkey.patch_all()

from app import create_app, socketio

app = create_app()  # your Flask app with routes + WebSocket setup

# For local dev/debug
if __name__ == "__main__":
    # This runs both HTTP endpoints and WebSocket server
    socketio.run(app, host="0.0.0.0", port=5054, debug=True)
