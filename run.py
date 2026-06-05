import os
from app import create_app, socketio

config_name = os.getenv('FLASK_CONFIG', 'default')
app = create_app(config_name)

if __name__ == '__main__':
    # Run with adhoc SSL for HTTPS support
    # socketio.run(app, host='0.0.0.0', port=7550, debug=True, ssl_context='adhoc')
    socketio.run(app, host='0.0.0.0', port=7550, debug=True)
