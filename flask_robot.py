from robot import Robot
from flask import current_app

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack

class FlaskRobot(object):

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if hasattr(app, 'teardown_appcontext'):
            app.teardown_appcontext(self.teardown)
        else:
            app.teardown_request(self.teardown)

    def teardown(self, exception):
        if exception is not None:
            if hasattr(self, 'robot'):
                self.robot.close()

    def new_robot(self):
        return Robot(current_app.config['ROBOT_PORT'])

    @property
    def instance(self):
        if not hasattr(self, 'robot'):
            self.robot = self.new_robot()
        return self.robot
