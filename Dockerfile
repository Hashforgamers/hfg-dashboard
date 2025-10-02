FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Gunicorn must point to the socketio object
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5054", "run:app"]


