#!/usr/bin/env python
import sys
import os
import time
import signal
import gobject
import threading
import curses

from machinekit import config
from pymachinetalk.dns_sd import ServiceDiscovery
from pymachinetalk.application import ApplicationStatus
from pymachinetalk.application import ApplicationCommand
from pymachinetalk.application import ApplicationError
from pymachinetalk.application import ApplicationFile
import pymachinetalk.application as application
import pymachinetalk.halremote as halremote

if sys.version_info >= (3, 0):
    import configparser
else:
    import ConfigParser as configparser


class TestClass():
    def __init__(self, uuid, use_curses):
        self.halrcmdReady = False
        self.halrcompReady = False

        halrcomp = halremote.component('test')
        halrcomp.newpin("coolant-iocontrol", halremote.HAL_BIT, halremote.HAL_IN)
        halrcomp.newpin("coolant", halremote.HAL_BIT, halremote.HAL_OUT)
        self.halrcomp = halrcomp

        halrcomp2 = halremote.RemoteComponent(name='test2')
        halrcomp2.newpin("coolant-iocontrol", halremote.HAL_BIT, halremote.HAL_IN)
        halrcomp2.newpin("coolant", halremote.HAL_BIT, halremote.HAL_OUT)
        self.halrcomp2 = halrcomp2

        self.status = ApplicationStatus()
        self.command = ApplicationCommand()
        self.error = ApplicationError()
        self.fileservice = ApplicationFile()
        self.fileservice.local_file_path = 'test.ngc'
        self.fileservice.local_path = './ngc/'
        self.fileservice.remote_path = '/home/xy/'
        self.fileservice.remote_file_path = '/home/xy/test.ngc'

        halrcmd_sd = ServiceDiscovery(service_type="_halrcmd._sub._machinekit._tcp", uuid=uuid)
        halrcmd_sd.on_discovered.append(self.halrcmd_discovered)
        halrcmd_sd.start()
        #halrcmd_sd.disappered_callback = disappeared
        self.halrcmd_sd = halrcmd_sd

        halrcomp_sd = ServiceDiscovery(service_type="_halrcomp._sub._machinekit._tcp", uuid=uuid)
        halrcomp_sd.on_discovered.append(self.halrcomp_discovered)
        halrcomp_sd.start()
        self.harcomp_sd = halrcomp_sd

        status_sd = ServiceDiscovery(service_type="_status._sub._machinekit._tcp", uuid=uuid)
        status_sd.on_discovered.append(self.status_discovered)
        status_sd.on_disappeared.append(self.status_disappeared)
        status_sd.start()
        self.status_sd = status_sd

        command_sd = ServiceDiscovery(service_type="_command._sub._machinekit._tcp", uuid=uuid)
        command_sd.on_discovered.append(self.command_discovered)
        command_sd.on_disappeared.append(self.command_disappeared)
        command_sd.start()

        error_sd = ServiceDiscovery(service_type="_error._sub._machinekit._tcp", uuid=uuid)
        error_sd.on_discovered.append(self.error_discovered)
        error_sd.on_disappeared.append(self.error_disappeared)
        error_sd.start()

        file_sd = ServiceDiscovery(service_type="_file._sub._machinekit._tcp", uuid=uuid)
        file_sd.on_discovered.append(self.file_discovered)
        file_sd.on_disappeared.append(self.file_disappeared)
        file_sd.start()

        self.timer = None

        self.use_curses = use_curses
        if not self.use_curses:
            return

        self.messages = []

        self.screen = curses.initscr()
        self.screen.keypad(True)
        self.dro_window = curses.newwin(10, 40, 1, 2)
        self.status_window = curses.newwin(10, 40, 1, 44)
        self.command_window = curses.newwin(10, 40, 1, 86)
        self.connection_window = curses.newwin(10, 80, 12, 2)
        self.error_window = curses.newwin(20, 120, 12, 84)
        self.file_window = curses.newwin(10, 80, 1, 108)
        curses.noecho()
        curses.cbreak()

    def start_halrcomp(self):
        print('connecting rcomp %s' % self.halrcomp.name)
        self.halrcomp.ready()
        self.halrcomp2.ready()
        #gevent.spawn(self.start_timer)

    def halrcmd_discovered(self, data):
        print("discovered %s %s" % (data.name, data.dsn))
        self.halrcomp.halrcmd_uri = data.dsn
        self.halrcomp2.halrcmd_uri = data.dsn
        self.halrcmdReady = True
        if self.halrcompReady:
            self.start_halrcomp()

    def halrcomp_discovered(self, data):
        print("discovered %s %s" % (data.name, data.dsn))
        self.halrcomp.halrcomp_uri = data.dsn
        self.halrcomp2.halrcomp_uri = data.dsn
        self.halrcompReady = True
        if self.halrcmdReady:
            self.start_halrcomp()

    def status_discovered(self, data):
        print('discovered %s %s' % (data.name, data.dsn))
        self.status.status_uri = data.dsn
        self.status.ready()
        self.timer = threading.Timer(0.1, self.status_timer)
        self.timer.start()

    def status_disappeared(self, data):
        print('%s disappeared' % data.name)
        self.status.stop()

    def command_discovered(self, data):
        print('discovered %s %s' % (data.name, data.dsn))
        self.command.command_uri = data.dsn
        self.command.ready()

    def command_disappeared(self, data):
        print('%s disappeared' % data.name)
        self.command.stop()

    def error_discovered(self, data):
        print('discovered %s %s' % (data.name, data.dsn))
        self.error.error_uri = data.dsn
        self.error.ready()

    def error_disappeared(self, data):
        print('%s disappeared' % data.name)
        self.error.stop()

    def file_discovered(self, data):
        print('discovered %s %s' % (data.name, data.dsn))
        self.fileservice.uri = data.dsn
        #self.fileservice.start_download()
        self.fileservice.refresh_files()
        self.fileservice.wait_completed()
        print(self.fileservice.file_list)
        self.fileservice.remove_file('test.ngc')
        self.fileservice.wait_completed()

    def file_disappeared(self, data):
        print('%s disappeared' % data.name)

    def start_timer(self):
        self.toggle_pin()
        timer = threading.Timer(1.0, self.start_timer)
        timer.start()
        #glib.timeout_add(1000, self.toggle_pin)

    def status_timer(self):
        #if self.status.synced:
        # print('flood %s' % self.status.io.flood)
        if self.use_curses:
            self.update_screen()
        self.timer = threading.Timer(0.05, self.status_timer)
        self.timer.start()

    def toggle_pin(self):
        self.halrcomp['coolant'] = not self.halrcomp['coolant']
        return True

    def update_screen(self):
        con = self.connection_window
        con.clear()
        con.border(0)
        con.addstr(1, 2, 'Connection')
        con.addstr(3, 4, 'Status: %s %s' % (str(self.status.synced), self.status.status_uri))
        con.addstr(4, 4, 'Command: %s %s' % (str(self.command.connected), self.command.command_uri))
        con.addstr(5, 4, 'Error: %s %s' % (str(self.error.connected), self.error.error_uri))
        con.refresh()

        if not self.status.synced or not self.command.connected:
            return

        dro = self.dro_window
        dro.clear()
        dro.border(0)
        dro.addstr(1, 2, "DRO")
        for i, n in enumerate(['x', 'y', 'z']):  # range(self.status.config.axes):
            pos = str(getattr(self.status.motion.position, n))
            dro.addstr(3 + i, 4, '%s: %s' % (n, pos))
        dro.refresh()

        status = self.status_window
        status.clear()
        status.border(0)
        status.addstr(1, 2, 'Status')
        status.addstr(3, 4, 'Estop: %s' % str(self.status.task.task_state == application.TASK_STATE_ESTOP))
        status.addstr(4, 4, 'Power: %s' % str(self.status.task.task_state == application.TASK_STATE_ON))
        status.refresh()

        cmd = self.command_window
        cmd.clear()
        cmd.border(0)
        cmd.addstr(1, 2, 'Command')
        cmd.addstr(3, 4, 'Estop - F1')
        cmd.addstr(4, 4, 'Power - F2')
        cmd.refresh()

        error = self.error_window
        error.clear()
        error.border(0)
        error.addstr(1, 2, 'Notifications')
        self.messages += self.error.get_messages()
        pos = 0
        for message in self.messages:
            # msg_type = str(message['type'])
            for note in message['notes']:
                error.addstr(3 + pos, 4, str(note))
                pos += 1
        error.refresh()

        win = self.file_window
        win.clear()
        win.border(0)
        win.addstr(1, 2, 'File')
        win.addstr(3, 4, 'Status: %s' % self.fileservice.transfer_state)
        win.addstr(4, 4, 'Progress: %f' % self.fileservice.progress)
        win.refresh()

        self.screen.nodelay(True)
        c = self.screen.getch()
        if c == curses.KEY_F1:
            if self.status.task.task_state == application.TASK_STATE_ESTOP:
                ticket = self.command.set_task_state(application.TASK_STATE_ESTOP_RESET)
                self.command.wait_completed(timeout=0.2)
            else:
                self.command.set_task_state(application.TASK_STATE_ESTOP)
                self.command.wait_completed()
        elif c == curses.KEY_F2:
            if self.status.task.task_state == application.TASK_STATE_ON:
                self.command.set_task_state(application.TASK_STATE_OFF)
            else:
                self.command.set_task_state(application.TASK_STATE_ON)
        elif c == curses.KEY_F3:
            self.fileservice.start_upload()

    def stop(self):
        if self.halrcomp is not None:
            self.halrcomp.stop()
        if self.halrcomp2 is not None:
            self.halrcomp2.stop()
        if self.status is not None:
            self.status.stop()
        if self.command is not None:
            self.command.stop()
        if self.error is not None:
            self.error.stop()

        if self.timer:
            self.timer.cancel()

        if self.use_curses:
            curses.endwin()


def main():
    mkconfig = config.Config()
    mkini = os.getenv("MACHINEKIT_INI")
    if mkini is None:
        mkini = mkconfig.MACHINEKIT_INI
    if not os.path.isfile(mkini):
        sys.stderr.write("MACHINEKIT_INI " + mkini + " does not exist\n")
        sys.exit(1)

    mki = configparser.ConfigParser()
    mki.read(mkini)
    uuid = mki.get("MACHINEKIT", "MKUUID")
    # remote = mki.getint("MACHINEKIT", "REMOTE")

    gobject.threads_init()  # important: initialize threads if gobject main loop is used
    test = TestClass(uuid=uuid, use_curses=True)
    loop = gobject.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()

    # while dns_sd.running and not check_exit():
    #     time.sleep(1)

    print("stopping threads")
    test.stop()

    # wait for all threads to terminate
    while threading.active_count() > 1:
        time.sleep(0.1)

    print("threads stopped")
    sys.exit(0)

if __name__ == "__main__":
    main()
