# updated_app.py
import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from tracking import tracking_bp, init_socket_events

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'geoadjust_secret_key_2026')

# Initialize SocketIO with production settings
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25
)

# Register Tracking Blueprint
app.register_blueprint(tracking_bp)

# Register socket event handlers
init_socket_events(socketio)

@app.route('/')
def index():
    return render_template('tracking.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'geoadjust-tracking'})

# For Render.com - THIS IS THE IMPORTANT PART
if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
