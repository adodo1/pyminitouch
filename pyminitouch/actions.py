import time
from contextlib import contextmanager

from pyminitouch.logger import logger
from pyminitouch.connection import MNTConnection, MNTServer, safe_connection
from pyminitouch import config
from pyminitouch.utils import restart_adb


class CommandBuilder(object):
    """Build command str for minitouch.

    You can use this, to custom actions as you wish::

        with safe_connection(_DEVICE_ID) as connection:
            builder = CommandBuilder()
            builder.down(0, 400, 400, 50)
            builder.commit()
            builder.move(0, 500, 500, 50)
            builder.commit()
            builder.move(0, 800, 400, 50)
            builder.commit()
            builder.up(0)
            builder.commit()
            builder.publish(connection)

    use `d.connection` to get `connection` from device
    """

    # TODO (x, y) can not beyond the screen size
    def __init__(self):
        self._content = ''

    def append(self, new_content):
        self._content += new_content + '\n'

    def commit(self):
        """ add minitouch command: 'c\n' """
        self.append('c')

    def wait(self, ms):
        """ add minitouch command: 'w <ms>\n' """
        self.append('w {}'.format(ms))

    def up(self, contact_id):
        """ add minitouch command: 'u <contact_id>\n' """
        self.append('u {}'.format(contact_id))

    def down(self, contact_id, x, y, pressure):
        """ add minitouch command: 'd <contact_id> <x> <y> <pressure>\n' """
        self.append('d {} {} {} {}'.format(contact_id, x, y, pressure))

    def move(self, contact_id, x, y, pressure):
        """ add minitouch command: 'm <contact_id> <x> <y> <pressure>\n' """
        self.append('m {} {} {} {}'.format(contact_id, x, y, pressure))

    def publish(self, connection):
        """ apply current commands (_content), to your device """
        self.commit()
        final_content = self._content
        logger.info('send operation: {}'.format(final_content.replace('\n', '\\n')))
        time.sleep(config.DEFAULT_DELAY)
        connection.send(final_content)
        self.reset()

    def reset(self):
        """ clear current commands (_content) """
        self._content = ''


class MNTDevice(object):
    """ minitouch device object

    Sample::

        device = MNTDevice(_DEVICE_ID)

        # It's also very important to note that the maximum X and Y coordinates may, but usually do not, match the display size.
        # so you need to calculate position by yourself, and you can get maximum X and Y by this way:
        print('max x: ', device.connection.max_x)
        print('max y: ', device.connection.max_y)

        # single-tap
        device.tap([(400, 600)])
        # multi-tap
        device.tap([(400, 400), (600, 600)])
        # set the pressure, default == 100
        device.tap([(400, 600)], pressure=50)

        # long-time-tap
        # for long-click, you should control time delay by yourself
        # because minitouch return nothing when actions done
        # we will never know the time when it finished
        device.tap([(400, 600)], duration=1000)
        time.sleep(1)

        # swipe
        device.swipe([(100, 100), (500, 500)])
        # of course, with duration and pressure
        device.swipe([(100, 100), (400, 400), (200, 400)], duration=500, pressure=50)

        # extra functions ( their names start with 'ext_' )
        device.ext_smooth_swipe([(100, 100), (400, 400), (200, 400)], duration=500, pressure=50, part=20)

        # stop minitouch
        # when it was stopped, minitouch can do nothing for device, including release.
        device.stop()
    """
    def __init__(self, device_id):
        self.device_id = device_id

        # prepare for connection
        server = MNTServer(device_id)
        # real connection
        connection = MNTConnection(server.port)

        self.server = server
        self.connection = connection

    def stop(self):
        self.connection.disconnect()
        self.server.stop()

    def tap(self, points, pressure=100, duration=None):
        """
        tap on screen, with pressure/duration

        :param points: list, looks like [(x1, y1), (x2, y2)]
        :param pressure: default == 100
        :param duration:
        :return:
        """
        _builder = CommandBuilder()
        for point_id, each_point in enumerate(points):
            x, y = each_point
            _builder.append('d {} {} {} {}'.format(point_id, x, y, pressure))
        _builder.commit()
        # apply duration
        if duration:
            _builder.wait(duration)
            _builder.commit()
        # release
        for each_id in range(len(points)):
            _builder.up(each_id)
        _builder.publish(self.connection)

    def swipe(self, points, pressure=100, duration=None):
        """
        swipe between points, one by one

        :param points: [(400, 500), (500, 500)]
        :param pressure: default == 100
        :param duration:
        :return:
        """
        _builder = CommandBuilder()
        point_id = 0
        # tap the first point
        x, y = points.pop(0)
        _builder.append('d {} {} {} {}'.format(point_id, x, y, pressure))
        _builder.commit()
        _builder.publish(self.connection)

        # start swiping
        for each_point in points:
            if duration:
                time.sleep(duration / 1000)
            x, y = each_point
            _builder.append('m {} {} {} {}'.format(point_id, x, y, pressure))
            _builder.commit()
            _builder.publish(self.connection)
        # release
        _builder.up(point_id)

    # extra functions' name starts with 'ext_'
    def ext_smooth_swipe(self, points, pressure=100, duration=None, part=10):
        """
        smoothly swipe between points, one by one
        it will split distance between points into pieces

        before::

            points == [(100, 100), (500, 500)]
            part == 8

        after::

            points == [(100, 100), (150, 150), (200, 200), ... , (500, 500)]

        :param points:
        :param pressure:
        :param duration:
        :param part: default to 10
        :return:
        """
        for each_index in range(len(points) - 1):
            cur_point = points[each_index]
            next_point = points[each_index + 1]

            offset = (int((next_point[0] - cur_point[0]) / part),
                      int((next_point[1] - cur_point[1]) / part))
            new_points = [(cur_point[0] + i * offset[0], cur_point[1] + i * offset[1]) for i in range(part)]
            new_points.append(points[-1])
            self.swipe(new_points, pressure=pressure, duration=duration)


@contextmanager
def safe_device(device_id):
    """ use MNTDevice safely """
    _device = MNTDevice(device_id)
    yield _device
    time.sleep(config.DEFAULT_DELAY)
    _device.stop()


if __name__ == '__main__':
    restart_adb()

    _DEVICE_ID = '4df189487c7b6fef'

    with safe_connection(_DEVICE_ID) as d:
        builder = CommandBuilder()
        builder.down(0, 400, 400, 50)
        builder.commit()
        builder.move(0, 500, 500, 50)
        builder.commit()
        builder.move(0, 800, 400, 50)
        builder.commit()
        builder.up(0)
        builder.commit()
        builder.publish(d)

    with safe_device(_DEVICE_ID) as d:
        builder = CommandBuilder()
        builder.down(0, 400, 400, 50)
        builder.commit()
        builder.move(0, 500, 500, 50)
        builder.commit()
        builder.move(0, 800, 400, 50)
        builder.commit()
        builder.up(0)
        builder.commit()
        builder.publish(d.connection)

    # option1:
    device = MNTDevice(_DEVICE_ID)
    device.tap([(400, 500), (500, 500)], duration=1000)

    # you should control time delay by yourself
    # otherwise when connection lost, action will never stop.
    time.sleep(1)

    device.stop()

    # option2:
    with safe_device(_DEVICE_ID) as device:
        device.tap([(400, 500), (500, 500)])
        device.swipe([(400, 500), (500, 500)], duration=500)
        time.sleep(0.5)
