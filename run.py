from app import create_app, socketio

app = create_app()  # Flask app

# Expose a callable for Gunicorn
# Gunicorn will use this 'socketio' object with eventlet
application = socketio.WSGIApp(app)
