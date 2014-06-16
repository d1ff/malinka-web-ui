import serial
import logging
import sys
import threading
import time
from math import *

logger = logging.getLogger(__name__)
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

sign = lambda x : int(abs(x) / x)

class Robot(object):

    class Mode:
        SCANNING = 0
        MOVING = 1

    class Action:
        FORWARD = 1
        BACKWARD = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        STOP = 5
        STRAIGHT = 6
        START_SCAN = 1

    def __encode_command(self, mode, action, param):
        cmd = action << 2 | mode
        return bytearray((cmd, param, 0))

    def execute(self, command):
        try:
            self.commands[command]()
        except:
            logger.exception('Error occured')

    def parse_data(self):
        try:
            data_line = self.buf
            self.buf = str()
            duration, distance, angle = [int(x) for x in data_line.split(',')]
            logger.info('t=%s,d=%s,a=%s', duration, distance, angle)
            return duration, distance, angle
        except ValueError:
            return None

    def __send_command(self, mode, action, param=1):
        self.last_command = None
        cmd = self.__encode_command(mode, action, param)
        while not self.last_command:
            self.last_action = action
            self.serial.write(cmd)
            self.serial.flush()
            time.sleep(0.2)

    def stop(self):
        self.__send_command(Robot.Mode.MOVING, Robot.Action.STOP)

    def straight(self):
        self.__send_command(Robot.Mode.MOVING, Robot.Action.STRAIGHT)

    def backward(self, distance=0, moving_time=0, power=255):
        self.forward(distance, moving_time, power, reverse=True)

    def forward(self, distance=0, moving_time=0, power=255, reverse=False):
        if reverse:
            command = Robot.Action.BACKWARD
        else:
            command = Robot.Action.FORWARD
        if moving_time:
            self.__send_command(Robot.Mode.MOVING, command, power)
            time.sleep(moving_time)
            self.stop()
        elif distance:
            while self.distance is None:
                time.sleep(0.1)
            if reverse:
                target_dist = max(self.distance + distance, 10)
            else:
                target_dist = max(self.distance - distance, 10)
            self.__send_command(Robot.Mode.MOVING, command, power)
            while self.distance > target_dist and self.distance > 10:
                self.__send_command(Robot.Mode.MOVING, command, power)
                time.sleep(0.2)
            self.stop()
        else:
            self.__send_command(Robot.Mode.MOVING, command, power)
            time.sleep(0.2)

    def __recalc_coord(self, new_duration, new_distance, new_angle):
        if self.distance is None:
            return
        dt = 0.3
        ds = 3.3
        v = ds * 1.0 / dt
        length = 15
        steeringAngle = (new_angle - 90.0) * pi / 180
        if abs(ds) < 1e-5:
            new_x = self.x
            new_y = self.y
            new_heading = self.heading
        elif abs(new_angle) < 1e-5:
            new_x = self.x + ds * cos(self.heading)
            new_y = self.y + ds * sin(self.heading)
            new_heading = self.heading
        else:
            beta = (ds / length) * tan(steeringAngle)
            if beta < 1e-5:
                return
            R = ds / beta

            new_heading = ((self.heading * beta) % (2 * pi) + 2 * pi) % (2 * pi)
            new_x = self.x - R * sin(self.heading) + R * sin(new_heading)
            new_y = self.y + R * cos(self.heading) - R * cos(new_heading)
        self.x, self.y, self.heading = new_x, new_y, new_heading
        logger.info("x=%s, y=%s, heading=%s", self.x, self.y, self.heading * 180 / pi)
        #self.notify_xy_listeners()

    def __parse_line(self, buf):
        if buf.startswith("ok"):
            self.last_command = True
            return
        data = buf.split(',')
        try:
            new_d = [int(x) for x in data]
            logger.debug(new_d)
            self.__recalc_coord(*new_d)
            self.duration, self.distance, self.angle = new_d
            self.notify_sensor_listeners()
            logger.debug('t=%s,d=%s,a=%s', self.duration, self.distance, self.angle)
        except ValueError:
            pass

    def __byte_to_str(self, b):
        try:
            return b.decode('ascii')
        except UnicodeDecodeError:
            return '\x00'

    def __read_data(self):
        buf = []
        while self.running:
            if not self.serial.inWaiting():
                time.sleep(0.1)
            b = self.serial.read()
            buf.append(b)
            if b == b'\n':
                line = "".join([self.__byte_to_str(b) for b in buf])
                logger.info(line.strip())
                self.__parse_line(line)
                buf = []

    def scan(self):
        self.__send_command(Robot.Mode.SCANNING, Robot.Action.START_SCAN)

    def turn_left(self):
        self.__send_command(Robot.Mode.MOVING, Robot.Action.TURN_LEFT)

    def turn_right(self):
        self.__send_command(Robot.Mode.MOVING, Robot.Action.TURN_RIGHT)

    def __init__(self, dev, baudrate=115200):
        self.serial = serial.Serial(dev, baudrate=baudrate, timeout=0)
        self.buf = str()
        self.running = True
        self.reader = threading.Thread(target=self.__read_data)
        self.reader.start()

        self.distance = None
        self.last_command = None
        self.last_action = None
        self.x, self.y, self.heading = 0, 0, 0
        self.sensor_listeners = set()
        self.started = time.time()
        self.commands = {"forward": self.forward,
         "backward": self.backward,
         "turn_left": self.turn_left,
         "turn_right": self.turn_right,
         "straight": self.straight,
         "stop": self.stop,
         "scan": self.scan,
         "auto": self.auto}

    def auto(self):
        pass

    def add_sensor_listener(self, fun):
        self.sensor_listeners.add(fun)

    def remove_sensor_listener(self, fun):
        self.sensor_listeners.remove(fun)

    def notify_sensor_listeners(self):
        for listener in self.sensor_listeners:
            listener(time.time() - self.started, self.duration, self.distance, self.angle)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.running = False
        self.reader.join()
        self.serial.close()

if __name__ == '__main__':
    with Robot('/dev/tty.usbmodem24121') as r:
        for i in range(5):
            r.straight()
            time.sleep(2)
            r.turn_left()
            time.sleep(2)
            r.forward(moving_time=.5)
            r.scan()
            time.sleep(2)
