from flask import Flask, render_template
from flask.ext.socketio import SocketIO, emit
from flask_robot import FlaskRobot
from time import sleep
import logging
import random
import sys

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
app.config['ROBOT_PORT'] = sys.argv[0]
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

xk = 0
K = 0.9
power = 255

@socketio.on('change k', namespace='/robot')
def change_k(message):
    global K
    K = float(message['data'])
    logger.info('Recieved new K = %s', K)
    emit('changed k', {'data': K}, namespace='/robot')

@socketio.on('command', namespace='/robot')
def process_command(message):
    command = message['data']
    logger.info('Recieved command %s', command)
    robot.instance.execute(command)

@socketio.on('change power', namespace='/robot')
def change_power(message):
    global power
    power = max(min(int(message['data']), 255), 0)
    logger.info('Recieved new power = %s', power)
    emit('changed power', {'data': power}, namespace='/robot')

def broadcast_sensor_data(time, duration, distance, angle):
    global xk, K
    xk = K * distance + (1 - K) * xk
    data = {
        'time': time,
        'distance': xk,
        'duration': duration,
        'angle': angle
    }
    socketio.emit('sensor', {'data': data}, namespace='/robot')

@socketio.on('connect', namespace='/robot')
def test_connect():
    logger.info('Client connected')
    robot.instance.add_sensor_listener(broadcast_sensor_data)
    #r = lambda : random.randint(0, 5) - 5
    #for i in xrange(150, 300, 20):
        #if i % 2 == 0:
            #start, stop, step = 45, 135, 5
        #else:
            #start, stop, step = 135, 45, -5
        #for j in xrange(start, stop, step):
            #broadcast_sensor_data(1, 1, i + r(), j)
            #broadcast_sensor_data(1, 1, i + r(), j)
            #broadcast_sensor_data(1, 1, i + r(), j)

@socketio.on('disconnect')
def test_disconnect():
    logger.info('Client disconnected')
    robot.instance.remove_sensor_listener(broadcast_sensor_data)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0')
