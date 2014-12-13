"""
watchers.py

Script that monitors changes in the file system using watchers instances.

TODO: Documentation
TODO: Better benchmark function

FAT32:
# 2 seconds for last modified time,
# 10 ms for creation time,
# 1 day for access date,
# 2 seconds for deletion time
"""

import os
import sys
import threading
import time
from collections import namedtuple

__version__ = '1.0.1-rc.1'

# Minimum python 3.2
if sys.hexversion < 0x030200F0:
    raise ImportError('Python < 3.2 not supported!')

# Python 3.2 do not support ns in os.stats!
PYTHON32 = True if sys.hexversion < 0x030300F0 else False

# Events types.
EVENT_TYPE_CREATED = 'created'
EVENT_TYPE_MODIFIED = 'modified'
EVENT_TYPE_DELETED = 'deleted'

Event = namedtuple('Event', ['type', 'path', 'is_file'])


# Useful functions.

def hours(x):
    return x * 3600
def minutes(x):
    return x * 60


# Investigators.

class Investigator:
    """Detects changes in a file system."""

    def update(self, item):
        pass
    def detect(self, item):
        pass


class ExistsInvestigator(Investigator):
    """Detects if a file or directory has been created or deleted."""

    def update(self, item):
        self.exists = item.exists()

    def detect(self, item):

        # Item was deleted.
        if not item.exists() and self.exists:
            return EVENT_TYPE_DELETED

        # Item was created.
        if item.exists() and not self.exists:
            return EVENT_TYPE_CREATED

        return None


class DirectoryContentInvestigator(Investigator):
    """Detects if the number of child items in directory has been changed."""

    def update(self, item):

        for path, dirs, files in os.walk(item.full_path):
            self.dirs = set(dirs)
            self.files = set(files)
            break

    def detect(self, item):

        for _, dirs, files in os.walk(item.full_path):
            if set(dirs) != self.dirs or set(files) != self.files:
                return EVENT_TYPE_MODIFIED
            break
        return None


class StatsInvestigator(Investigator):
    """Base class for investigating a file or directory stats."""

    def _get_stat(self, path):
        try:
            return os.stat(path)
        except (IOError, OSError):
            return None

    def update(self, item):
        self.stats = self._get_stat(item.full_path)


class PermissionsInvestigator(StatsInvestigator):
    """Detects if a file or directory permissions has been modified."""

    def detect(self, item):

        stat = self._get_stat(item.full_path)

        # Item not exists or just created.
        if None in (stat, self.stats):
            return None

        # st_mode: File mode (permissions)
        # st_uid: Owner id
        # st_gid: Group id
        stat_a = stat.st_mode, stat.st_uid, stat.st_gid
        stat_b = self.stats.st_mode, self.stats.st_uid, self.stats.st_gid
        return EVENT_TYPE_MODIFIED if stat_a != stat_b else None


class FileInvestigator(StatsInvestigator):
    """Detects if a file size or modification time has been modified."""

    def detect(self, item):

        stat = self._get_stat(item.full_path)

        # Item not exists or just created.
        if None in (stat, self.stats):
            return None

        stat_a = stat.st_mtime, stat.st_size
        stat_b = self.stats.st_mtime, self.stats.st_size
        return EVENT_TYPE_MODIFIED if stat_a != stat_b else None


# Polling classes.

class PathPolling:

    def __init__(self, path, root=None, investigators=None):

        self.path = path

        if root is None:
            self.full_path = os.path.abspath(path)
        else:
            self.full_path = os.path.normpath(os.path.join(root, path))

        # TODO: Better raising path not found
        os.stat(self.full_path)

        self.is_file = True if os.path.isfile(self.full_path) else False
        self.is_directory = not self.is_file
        self.investigators = investigators

        # Polling directory.

        if not self.is_file:
            if investigators is None:
                self.investigators = [ExistsInvestigator(),
                                      PermissionsInvestigator(),
                                      DirectoryContentInvestigator()]
        # Polling file.

        else:
            self.is_file = True
            if investigators is None:
                self.investigators = [ExistsInvestigator(),
                                      FileInvestigator(),
                                      PermissionsInvestigator()]

        self.update_investigators()

    def __repr__(self):
        return ("<{class_name}: path={path}, is_file={is_file}>").format(
            class_name=self.__class__.__name__,
            path=self.path,
            is_file=self.is_file)

    def exists(self):
        """Returns True if an item exists."""

        if self.is_file:
            return os.path.isfile(self.full_path)
        return os.path.isdir(self.full_path)

    def update_investigators(self):
        for i in self.investigators:
            i.update(self)

    def investigate(self):
        """Uses investigators to detect changes in the file system."""

        event = None

        for i in self.investigators:
            event_type = i.detect(self)
            if event_type:
                event = Event(event_type, self.path, self.is_file)
                break

        self.update_investigators()
        return event

    def poll(self):

        event = self.investigate()
        if event:
            self.dispatch_event(event)

        return event

    def dispatch_event(self, x):

        if x.type == EVENT_TYPE_CREATED:
            self.on_created()

        elif x.type == EVENT_TYPE_DELETED:
            self.on_deleted()

        elif x.type == EVENT_TYPE_MODIFIED:
            self.on_modified()

    # Events

    def on_created(self):
        pass

    def on_modified(self):
        pass

    def on_deleted(self):
        pass


class DirectoryPolling:
    """Watcher with events."""

    def __init__(self, path, recursive=False, filter=None):

        self.path = path
        self.root = os.getcwd()
        # root + path
        self.full_path = os.path.join(self.root, path)

        # TODO: Better raising path not found
        os.stat(self.full_path)

        self.is_recursive = recursive
        # Callable that checks ignored items_paths.
        self.filter = filter

        # List of PathPolling instances.
        self.items = [self.create_item(path) for path in self._walk()]

    def __repr__(self):
        return ("<{class_name}: path={path}, "
                "is_recursive={is_recursive}>").format(
            class_name=self.__class__.__name__,
            path=self.path,
            is_recursive=self.is_recursive)

    def item_exists(self, x):

        # TODO: Optimize this!
        if (x.is_file, x.path) in [(i.is_file, i.path) for i in self.items]:
            return True
        return False

    def create_item(self, path):

        if os.path.isfile(path):
            x = [ExistsInvestigator(),
                 FileInvestigator(),
                 PermissionsInvestigator()]
        else:
            if self.is_recursive or self.path == path:
                x = [ExistsInvestigator(),
                     DirectoryContentInvestigator(),
                     PermissionsInvestigator()]
            else:
                x = [ExistsInvestigator(),
                     PermissionsInvestigator()]

        # TODO: but when path not exists?
        return PathPolling(path, root=self.root, investigators=x)

    def _walk(self):
        """Yields watched paths, already filtered."""

        # Fixed: Also filter root directory!
        if os.path.isdir(self.full_path):
            if self.filter is None or self.filter(self.path):
                yield self.path

        for root, dirs, files in os.walk(self.full_path):
            for name in sorted(files) + sorted(dirs):

                # Path is generated using self.path attribute, to preserve
                # arguments during calling __init__.
                # For example: DirectoryPolling('.') => PathPolling('./filename)

                if root == self.full_path:
                    p = os.path.join(self.path, name)
                else:
                    p = os.path.join(self.path,
                                     os.path.relpath(root, self.full_path),
                                     name)

                if self.filter and not self.filter(p):
                    continue
                yield p

            if not self.is_recursive:
                break

    def _investigate_items(self):

        events = []

        for item in self.items:
            e = item.investigate()
            if e:
                events.append((item, e))

        items = []
        for i in self._walk():
            item = self.create_item(i)
            items.append(item)

            if not self.item_exists(item):
                events.append((item, Event(EVENT_TYPE_CREATED, item.path, item.is_file)))

        events = self.sort_events(events)
        self.items = items
        return events

    def investigate(self):
        return [i[1] for i in self._investigate_items()]

    def poll(self):

        events = self._investigate_items()
        self.dispatch_events(events)
        return [i[1] for i in events]

    def sort_events(self, x):
        return sorted(x, key=lambda x: x[1].type)

    def dispatch_events(self, x):

        for item, event in x:
            item.dispatch_event(event)

            if event.type == EVENT_TYPE_CREATED:
                self.on_created(event)

            if event.type == EVENT_TYPE_DELETED:
                self.on_deleted(event)

            if event.type == EVENT_TYPE_MODIFIED:
                self.on_modified(event)

    # Events

    def on_created(self, item):
        pass

    def on_modified(self, item):
        pass

    def on_deleted(self, item):
        pass


# Timer.

class Timer:
    """Repeats self.loop() method every interval."""

    def __init__(self):

        self._is_alive = False
        self.thread = None
        self.lock = threading.Lock()
        # Amount of time (in seconds) between running run() method.
        self.interval = None

    @property
    def is_alive(self):
        if self._is_alive \
           or (self.thread and self.thread.is_alive()):
            return True
        return False

    @property
    def is_active(self):
        return self.is_alive

    #

    def loop(self):
        pass

    def _start_loop(self, interval):
        """This method is run in the Timer thread and it triggers check()"""

        self.loop()
        self._start_timer(interval)

    def _start_timer(self, interval):
        """Starts new Timer thread, it will run check after time interval."""

        # Lock pauses stop() method.
        # Check if the watcher is alive because stop() can kill it during
        # execution of this method.
        with self.lock:
            if self._is_alive:
                self.thread = threading.Timer(
                    interval, self._start_loop, args=[interval])
                self.thread.name = repr(self)
                self.thread.daemon = True
                self.thread.start()

    #

    def start(self, interval):
        """Starts task. Returns False if the task has already started."""

        self.interval = interval

        if self._is_alive:
            return False

        self._is_alive = True
        self._start_loop(interval)
        return True

    def stop(self):
        """Stops watching. Returns False if the watcher has already stopped."""

        if self._is_alive:

            # Lock prevents starting new Timer threads.
            with self.lock:
                self._is_alive = False
                if self.thread:
                    self.thread.cancel()

            # Timer thread canceled, wait for join it.
            if self.thread and threading.current_thread() != self.thread:
                self.thread.join()

            self.interval = None
            return True

        # Watcher already stopped.
        return False

    def join(self):
        """Waits until the timer is stopped."""
        # TODO: time.sleep? :(
        while self.is_alive:
            time.sleep(0.1)


# Callback.

class Callback:

    def __init__(self, callback='on_callback'):

        if callable(callback) or isinstance(callback, str):
            self.callbacks = [callback]
        else:
            self.callbacks = callback

    def iter_callbacks(self):

        for x in self.callbacks:
            if isinstance(x, str):
                x = getattr(self, x)
            yield x

    def on_callback(self, event):
        pass


# Task classes.

class Task(Timer, Callback):
    """..."""

    def __init__(self, callback='on_callback'):
        Timer.__init__(self)
        Callback.__init__(self, callback)

    def loop(self):
        for x in self.run():
            for callback in self.iter_callbacks():
                callback(x)

    def run(self):
        yield


class PollPath(PathPolling, Task):
    def __init__(self, path, callback='on_callback'):
        PathPolling.__init__(self, path)
        Task.__init__(self, callback)

    def __repr__(self):
        return ("<{class_name}: interval={interval}, path={path}, "
                "is_file={is_file}>").format(
            class_name=self.__class__.__name__,
            interval=self.interval,
            path=self.path,
            is_file=self.is_file)

    def run(self):
        event = self.poll()
        if event:
            yield event


class Poll(DirectoryPolling, Task):
    def __init__(self, path, recursive=False, filter=None, callback='on_callback'):
        DirectoryPolling.__init__(self, path, recursive, filter)
        Task.__init__(self, callback)

    def __repr__(self):
        return ("<{class_name}: interval={interval}, path={path}, "
                "is_recursive={is_recursive}>").format(
            class_name=self.__class__.__name__,
            interval=self.interval,
            path=self.path,
            is_recursive=self.is_recursive)

    def run(self):
        for i in self.poll():
            yield i


# Watchers.

class Watcher(Callback):


    def __init__(self, default_task=Poll, callback='on_callback'):
        super().__init__(callback)

        self.default_task = default_task
        self.tasks = []
        self.is_active = False

    #

    def schedule(self, interval, *args, **kwargs):
        x = self.default_task(*args, **kwargs)
        self.schedule_task(interval, x)
        return x

    def schedule_task(self, interval, *tasks):

        if isinstance(interval, str):
            if 'hr' in interval:
                interval = float(interval.split('hr')[0]) * 3600
            elif 'min' in interval:
                interval = float(interval.split('min')[0]) * 60
            elif ':' in interval:
                h, m, s = interval.split(':')
                interval = int(h) * 3600 + int(m) * 60 + int(s)

        for x in tasks:
            self.tasks.append(x)
            x.interval = interval
            x.callbacks.append(self._task_callback)

            if self.is_active:
                x.start(interval)

    def _task_callback(self, event):
        for function in self.iter_callbacks():
            function(event)

    def unschedule(self, *tasks):
        for i in tasks:
            self.unschedule_task(i)

    def unschedule_task(self, x):
        x.stop()
        self.tasks.remove(x)

    def unschedule_all(self):
        for i in self.tasks:
            self.unschedule_task(i)

    #

    def start(self):

        if self.is_active:
            return False

        for i in self.tasks:
            i.start(i.interval)

        self.is_active = True
        return True

    def stop(self):

        if not self.is_active:
            return False

        for i in self.tasks:
            i.stop()

        self.is_active = False
        return True

    def join(self):
        # TODO: time.sleep :(
        while self.is_active:
            time.sleep(0.1)


# SimpleWatcher

class SimpleDirectoryWatcher(Poll):

    def __init__(self, interval, path, target, args=(), kwargs=None,
                 recursive=False, filter=None):

        Poll.__init__(self, path, recursive, filter)

        self.interval = interval
        self.target = target
        self.args = args
        self.kwargs = {} if not kwargs else kwargs

    def loop(self):
        """Detects changes in a file system. Returns True if something changed."""

        if self.poll():
            self.target(*self.args, **self.kwargs)
            return True
        return False

    def start(self):
        Poll.start(self, self.interval)







#
# class Event:
#     def __init__(self, status, path, is_file=None):
#         self.type = status
#         self.path = path
#         self.is_file = os.path.isfile(path) if is_file is None else is_file
#         self.is_directory = not self.is_file
#
#     def __repr__(self):
#         return ("<{class_name}: status={status}, "
#                 "path={path}, is_file={is_file}>").format(
#             class_name=self.__class__.__name__,
#             status=self.type,
#             path=self.path,
#             is_file=self.is_file)
#
#
#     def __eq__(self, other):
#         if (self.type == other.type,
#             self.path == other.path,
#             self.is_file == other.is_file):
#             return True
#         return False
#
#
#     def __hash__(self):
#         return hash((self.type, self.path, self.is_file))
