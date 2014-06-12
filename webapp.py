from flask import Flask, render_template
from flask.ext.socketio import SocketIO, emit
from flask_robot import FlaskRobot
import logging

# create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['ROBOT_PORT'] = '/dev/tty.usbmodem26421'
socketio = SocketIO(app)
robot = FlaskRobot(app)

class WebSocketsHandler(logging.Handler):

    def __init__(self, socketio, namespace):
        super(WebSocketsHandler, self).__init__()
        self.socketio = socketio
        self.ws_namespace = namespace

    def emit(self, record):
        message = self.format(record)
        self.socketio.emit('log', {'data': message}, namespace=self.ws_namespace)

wsh = WebSocketsHandler(socketio, '/robot')
wsh.setLevel(logging.INFO)
wsh.setFormatter(formatter)
logger.addHandler(wsh)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def send_foo(filename):
    return send_from_directory('./static', filename)

@socketio.on('my event', namespace='/robot')
def test_message(message):
    emit('my response', {'data': message['data']}, namespace='/robot')

def broadcast_sensor_data(time, duration, distance, angle):
    data = {
        'time': time,
        'distance': distance,
        'duration': duration,
        'angle': angle
    }
    socketio.emit('sensor', {'data': data}, namespace='/robot')

@socketio.on('connect', namespace='/robot')
def test_connect():
    logger.info('Client connected')
    robot.instance.add_sensor_listener(broadcast_sensor_data)

@socketio.on('disconnect')
def test_disconnect():
    logger.info('Client disconnected')
    robot.instance.remove_sensor_listener(broadcast_sensor_data)

if __name__ == '__main__':
    socketio.run(app)
