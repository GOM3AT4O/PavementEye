from flask import Flask, request  # Add request import
import os
from flask_socketio import SocketIO, emit
import traceback
import threading  # Add this import

# Upload endpoints functions
from endpoints.upload_image import detect_endpoint
from endpoints.test import test

# init flask api for normal backend endpoints
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# init websocket server for streaming endpoints
socketio = SocketIO(app, cors_allowed_origins="*")

# Just to test the backend is running ------------------------------------------------------
@app.route('/', methods=['GET'])
def root():
    return test()

## ----------------- websocket for streaming -------------------------------------------
# Global error handler
@socketio.on_error_default
def default_error_handler(e):
    print('❌ WebSocket error:', str(e))
    traceback.print_exc()

@socketio.on("connect")
def handle_connect():
    try:
        print('✅ Client connected!')
        emit('connection_status', {'status': 'connected'})
    except Exception as e:
        print('❌ Connect error:', e)
        traceback.print_exc()

@socketio.on("disconnect")
def handle_disconnect():
    print('❌ Client disconnected!')

def process_in_background(data, sid):
    """Process image in background thread (keeps your detect_endpoint unchanged)"""
    try:
        # Call your EXACT same detect_endpoint function
        res = detect_endpoint(data)
        
        # Use socketio.emit (thread-safe) to send response
        socketio.emit("response", res, room=sid)
        
    except Exception as e:
        print(f"❌ Background processing error: {e}")
        socketio.emit('response', {
            'status': 'error',
            'error': str(e)
        }, room=sid)

# connection between the flutter app
@socketio.on("stream_image")
def stream(data):
    try:
        # Get client session ID
        sid = request.sid
        
        # Create a background thread for processing
        thread = threading.Thread(
            target=process_in_background,
            args=(data, sid),
            daemon=True  # Thread won't block app shutdown
        )
        thread.start()
        
        # Optional: Send immediate acknowledgement
        emit("ack", {"status": "processing"})
        
    except Exception as e:
        print(f"❌ Stream error: {e}")
        emit('response', {
            'status': 'error',
            'error': str(e)
        })

# ---------------------------------------------------------------------------------------------
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)