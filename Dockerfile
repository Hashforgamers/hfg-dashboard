FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Gunicorn must point to the socketio-enabled app.
CMD ["sh", "-c", "exec gunicorn -k eventlet -w ${GUNICORN_WORKERS:-1} -b 0.0.0.0:${PORT:-5054} --timeout ${GUNICORN_TIMEOUT:-120} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} --keep-alive ${GUNICORN_KEEPALIVE:-5} --max-requests ${GUNICORN_MAX_REQUESTS:-1000} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} run:app"]

