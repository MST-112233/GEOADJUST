# gunicorn.conf.py
import os
import multiprocessing

# Get port from environment
port = os.environ.get('PORT', 5000)

# Bind to 0.0.0.0:$PORT
bind = f"0.0.0.0:{port}"

# Number of workers (1 for WebSocket support)
workers = 1

# Worker class for WebSocket support
worker_class = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'

# Timeout settings
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
