# run.py - Main entry point for both Streamlit and Flask
import subprocess
import sys
import os
import threading
import time
import webbrowser

def run_flask():
    """Run the Flask/SocketIO server for tracking."""
    from updated_app import app, socketio
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def run_streamlit():
    """Run the Streamlit app."""
    os.system("streamlit run app.py --server.port 8501")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting GEOADJUST - Geodetic Network Adjustment & Spatial Toolkit")
    print("=" * 60)
    print("\n📊 Streamlit App: http://localhost:8501")
    print("📍 Tracking Server: http://localhost:5000")
    print("📡 Tracking Web Interface: http://localhost:5000/tracking")
    print("\nPress Ctrl+C to stop all services")
    print("=" * 60)
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Give Flask time to start
    time.sleep(2)
    
    # Open browser to Streamlit
    webbrowser.open("http://localhost:8501")
    
    # Run Streamlit (blocking)
    run_streamlit()
