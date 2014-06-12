import serial
import logging
import sys
import threading
import time

logger = logging.getLogger(__name__)

MODE_SCANNING = 0
MODE_MOVING = 1

ACTION_MOVE_FORWARD = 1
ACTION_MOVE_BACKWARD = 2
ACTION_TURN_LEFT = 3
ACTION_TURN_RIGHT = 4
ACTION_STOP = 5
ACTION_STRAIGHT = 6
ACTION_START_SCANNING = 1

class Robot(object):

    def __encode_command(self, mode, action, param):
        cmd = action << 2 | mode
        return bytes((cmd, param, 0))

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
            self.serial.write(cmd)
            self.serial.flush()
            time.sleep(0.2)

    def stop(self):
        self.__send_command(MODE_MOVING, ACTION_STOP)

    def straight(self):
        self.__send_command(MODE_MOVING, ACTION_STRAIGHT)

    def forward(self, distance=0, moving_time=0, power=255):
        if moving_time:
            self.__send_command(MODE_MOVING, ACTION_MOVE_FORWARD, power)
            time.sleep(moving_time)
            self.stop()
        elif distance:
            while self.distance is None:
                time.sleep(0.1)
            target_dist = max(self.distance - distance, 10)
            self.__send_command(MODE_MOVING, ACTION_MOVE_FORWARD, power)
            while self.distance > target_dist and self.distance > 10:
                self.__send_command(MODE_MOVING, ACTION_MOVE_FORWARD, power)
                time.sleep(0.2)
            self.stop()

    def __parse_line(self, buf):
        if buf.startswith("ok"):
            self.last_command = True
            return
        data = buf.split(',')
        try:
            self.duration, self.distance, self.angle = [int(x) for x in data]
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
                self.__parse_line(line)
                buf = []

    def scan(self):
        self.__send_command(MODE_SCANNING, ACTION_START_SCANNING)

    def turn_left(self):
        self.__send_command(MODE_MOVING, ACTION_TURN_LEFT)

    def __init__(self, dev, baudrate=115200):
        self.serial = serial.Serial(dev, baudrate=baudrate, timeout=0)
        self.buf = str()
        self.running = True
        self.reader = threading.Thread(target=self.__read_data)
        self.reader.start()

        self.distance = None
        self.last_command = None
        self.x, self.y = 0, 0
        self.sensor_listeners = set()
        self.started = time.time()

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
    with Robot('/dev/tty.usbmodem26421') as r:
        for i in range(5):
            r.scan()
            time.sleep(10)
            r.straight()
            time.sleep(2)
            r.forward(5)
            time.sleep(2)
            r.turn_left()
            time.sleep(2)
            r.forward(moving_time=5)
            time.sleep(2)
