from flask import Flask, render_template
from flask_socketio import SocketIO
from tracking import tracking_bp, init_socket_events

app = Flask(__name__)
app.config['SECRET_KEY'] = 'geoadjust_secret_key_2026'

# Initialize SocketIO with cross-network support (CORS)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Register Tracking Blueprint
app.register_blueprint(tracking_bp)

# Register socket event handlers
init_socket_events(socketio)

@app.route('/')
def index():
    return render_template('index.html')

# Note: The run logic is now in run.py
