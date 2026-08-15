import csv
import io
import time
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, make_response
from flask_socketio import emit, join_room, leave_room

# Blueprint Definition
tracking_bp = Blueprint('tracking', __name__, template_folder='templates')

# In-memory data store for room sessions
# Format: { room_id: { "password": str, "chat": [list], "locations": [list], "members": {sid: role} } }
ROOMS = {}

def init_socket_events(socketio):
    """Register SocketIO handlers for real-time tracking and chat."""

    @socketio.on('join_room_event')
    def handle_join(data):
        room_id = data.get('room_id')
        password = data.get('password')
        role = data.get('role')
        username = data.get('username', 'Anonymous')

        if not room_id or not password or not role:
            emit('error_response', {'message': 'Room ID, Password, and Role are required.'})
            return

        # Initialize room if it doesn't exist
        if room_id not in ROOMS:
            ROOMS[room_id] = {
                'password': password,
                'chat': [],
                'locations': [],
                'members': {}
            }
        else:
            # Validate password for existing room
            if ROOMS[room_id]['password'] != password:
                emit('error_response', {'message': 'Incorrect room password.'})
                return

        join_room(room_id)
        ROOMS[room_id]['members'][request.sid] = {
            'username': username,
            'role': role
        }

        # Send historic chat and current active locations to newly joined user
        emit('join_success', {
            'room_id': room_id,
            'role': role,
            'chat_history': ROOMS[room_id]['chat'],
            'locations_history': ROOMS[room_id]['locations']
        })

        # Announce arrival in chat
        sys_msg = {
            'sender': 'System',
            'role': 'System',
            'message': f"{username} ({role}) joined the room.",
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }
        ROOMS[room_id]['chat'].append(sys_msg)
        emit('receive_message', sys_msg, to=room_id)

    @socketio.on('send_message')
    def handle_message(data):
        room_id = data.get('room_id')
        message = data.get('message')

        if room_id in ROOMS and request.sid in ROOMS[room_id]['members']:
            user_info = ROOMS[room_id]['members'][request.sid]
            msg_data = {
                'sender': user_info['username'],
                'role': user_info['role'],
                'message': message,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
            ROOMS[room_id]['chat'].append(msg_data)
            emit('receive_message', msg_data, to=room_id)

    @socketio.on('update_location')
    def handle_location(data):
        room_id = data.get('room_id')
        lat = data.get('lat')
        lng = data.get('lng')

        if room_id in ROOMS and request.sid in ROOMS[room_id]['members']:
            user_info = ROOMS[room_id]['members'][request.sid]
            
            # Only Site Surveyors push location records
            if user_info['role'] == 'Site Surveyor':
                location_entry = {
                    'sid': request.sid,
                    'username': user_info['username'],
                    'lat': lat,
                    'lng': lng,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                ROOMS[room_id]['locations'].append(location_entry)

                # Broadcast live position to all room subscribers
                emit('location_broadcast', location_entry, to=room_id)

    @socketio.on('disconnect')
    def handle_disconnect():
        for room_id, room_data in ROOMS.items():
            if request.sid in room_data['members']:
                user_info = room_data['members'].pop(request.sid)
                leave_room(room_id)
                
                disc_msg = {
                    'sender': 'System',
                    'role': 'System',
                    'message': f"{user_info['username']} disconnected.",
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                }
                room_data['chat'].append(disc_msg)
                emit('receive_message', disc_msg, to=room_id)
                emit('user_disconnected', {'sid': request.sid}, to=room_id)
                break


# HTTP Routes for Web Access & Downloads
@tracking_bp.route('/tracking')
def tracking_page():
    return render_template('tracking.html')


@tracking_bp.route('/download/locations/<room_id>', methods=['POST'])
def download_locations(room_id):
    req_password = request.form.get('password')
    role = request.form.get('role')

    # Security check: Only Control Center can download logs
    if role != 'Control Center':
        return jsonify({'error': 'Unauthorized access. Only Control Center can download records.'}), 403

    if room_id not in ROOMS or ROOMS[room_id]['password'] != req_password:
        return jsonify({'error': 'Invalid Room ID or Password.'}), 400

    locations = ROOMS[room_id]['locations']
    
    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'Surveyor Name', 'Latitude', 'Longitude'])

    for loc in locations:
        writer.writerow([loc['timestamp'], loc['username'], loc['lat'], loc['lng']])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=Tracking_Locations_{room_id}.csv"
    response.headers["Content-type"] = "text/csv"
    return response


@tracking_bp.route('/download/chat/<room_id>', methods=['POST'])
def download_chat(room_id):
    req_password = request.form.get('password')
    role = request.form.get('role')

    if role != 'Control Center':
        return jsonify({'error': 'Unauthorized access. Only Control Center can download records.'}), 403

    if room_id not in ROOMS or ROOMS[room_id]['password'] != req_password:
        return jsonify({'error': 'Invalid Room ID or Password.'}), 400

    chat_history = ROOMS[room_id]['chat']
    
    # Generate TXT in-memory
    output = io.StringIO()
    output.write(f"=== GEOADJUST CHAT LOGS FOR ROOM: {room_id} ===\n\n")

    for msg in chat_history:
        output.write(f"[{msg['timestamp']}] {msg['sender']} ({msg['role']}): {msg['message']}\n")

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=Tracking_Chat_{room_id}.txt"
    response.headers["Content-type"] = "text/plain"
    return response
