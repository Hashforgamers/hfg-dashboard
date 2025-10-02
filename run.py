from gevent import monkey
monkey.patch_all()  # must be first

from app import create_app, socketio

app = create_app()

# Gunicorn needs to see a callable named 'app'
# SocketIO already wraps the Flask app
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5054)
