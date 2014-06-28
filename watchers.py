import os
import time
import fnmatch
from stat import *
from collections import namedtuple

import threading

import cProfile
# File monitoring:

# Watcher

# dirs
# files
# files_created
# files_modified
# files_deleted

# schedule
# start
# stop
# recursive


# is_recursive
#
#     Determines whether subdirectories are watched for the path.
#


# ignored
# excluded

# on_created
# file_patterns

# The following example program will monitor the current directory
# recursively for file system changes and simply log them to the console:

# Below we present a simple example that monitors the current directory
# recursively (which means, it will traverse any sub-directories) to detect
# changes. Here is what we will do with the API:

CHECK_INTERVAL = 2

class File:


    def __init__(self, path):

        self.path = path


        stats = os.stat(path)

        if S_ISDIR(stats.st_mode):
            self.is_file = False
        else:
            self.is_file = True

        if self.is_file:
            self.m_time = stats.st_mtime_ns
            self.size = stats.st_size

        # Permissions:

        self.c_time = stats.st_ctime_ns
        self.uid = stats.st_uid
        self.gid = stats.st_gid
        self.mode = stats.st_mode


    def is_modified(self):

        stats = os.stat(self.path)

        if not self.is_file:

            if self.mode != stats.st_mode \
               or self.uid != stats.st_uid \
               or self.gid != stats.st_gid:

                self.c_time = stats.st_ctime_ns
                self.mode = stats.st_mode
                self.uid = stats.st_uid
                self.gid = stats.st_gid
                return True
            return False

        if self.m_time != stats.st_mtime_ns \
           or self.size != stats.st_size \
           or self.mode != stats.st_mode \
           or self.uid != stats.st_uid \
           or self.gid != stats.st_gid:

            self.m_time = stats.st_mtime_ns
            self.mode = stats.st_mode
            self.size = stats.st_size
            self.gid = stats.st_gid
            self.uid = stats.st_uid

            return True
        return False

#
#
# class BasicWatcher:
#
#     def __init__(self, path, recursive=False, filter=None):

class Watcher:
    """Used by FileMonitor. Observe given path and runs function when
    something was changed.

    Properties:

    """

    def __init__(self, path, recursive=False, filter=None):

        # Path must be always absolute!
        self.path = os.path.abspath(path)
        self.is_recursive = recursive

        # Callable which checks ignored paths.
        self.filter = filter
        self._events = {}

        # List of watched files, key is file path, value is modification time.
        self.watched_paths = {}


        for path, dirs, files in os.walk(self.path):
            for i in dirs + files:
                self._watch_path(os.path.join(path, i))
            if not self.is_recursive:
                break

        # print(self.watched_paths.keys())


    def _watch_path(self, path):

        if self.filter and not self.filter(path):
            return False

        # Save file/dir modification time.
        self.watched_paths[path] = File(path)
        return True
    #
    #
    # def run_function(self):
    #     """Runs stored function."""
    #     return self.target(*self.args, **self.kwargs)

    def check(self):
        """Checks if files were modified. If modified => runs function."""

        result = False
        stack = {}

        for path, dirs, files in os.walk(self.path):
            for i in dirs + files:

                if self.filter and not self.filter(os.path.join(path, i)):
                    continue


                if self._path_changed(os.path.join(path, i), stack):
                    result = True
            if not self.is_recursive:
                break

        if self.watched_paths:
            for path in self.watched_paths.values():
                self.on_deleted(path)
                result = True

        self.watched_paths = stack
        return result

    def _path_changed(self, path, stack):
        """Checks if path was modified, or created.

        Returns:
            True if path was modified or now created, False if not.
        """

        # File exists and could be modified.
        if path in self.watched_paths:
            if self.watched_paths[path].is_file == os.path.isfile(path):

                x = self.watched_paths.pop(path)
                stack[path] = x

                if x.is_modified():
                    self.on_modified(x)
                    return True
                return False

        # Path was created.
        x = File(path)
        stack[path] = x
        self.on_created(x)
        return True


    # Events.

    def run_event(self, name):
        if name in self._events:
            event = self._events[name]
            event.callable(*event.args, **event.kwargs)

    def _add_event(self, name, callable, args, kwargs):
        Event = namedtuple('Event', 'callable args kwargs')
        self._events[name] = Event(callable, args, kwargs)


    def on_created(self, item, *args, **kwargs):
        if callable(item):
            self._add_event('on_created', item, args, kwargs)
        else:
            self.run_event('on_created')

    def on_modified(self, item, *args, **kwargs):
        if callable(item):
            self._add_event('on_modified', item, args, kwargs)
        else:
            self.run_event('on_modified')

    def on_deleted(self, item, *args, **kwargs):
        if callable(item):
            self._add_event('on_deleted', item, args, kwargs)
        else:
            self.run_event('on_deleted')



class SimpleWatcher:

    def __init__(self, path, target, args=(), kwargs={}, recursive=False,
                 filter=None):

        self.path = os.path.abspath(path)
        self.is_recursive = recursive
        self.filter = filter

        self.check_thread = None
        self.check_interval = CHECK_INTERVAL

        self.target = target
        self.args = args
        self.kwargs = kwargs

        self.snapshot = self._get_snapshot()

    def __repr__(self):
        return "SimpleWatcher(path={!r})".format(self.path)

    @property
    def is_stopped(self):
        return True if self.check_thread is None else False

    def _get_snapshot(self):

        snapshot = set()

        for path, dirs, files in os.walk(self.path):
            for i in dirs + files:

                if self.filter and not self.filter(os.path.join(path, i)):
                    continue

                p = os.path.join(path, i)
                stats = os.stat(p)

                # Path points to directory.

                if S_ISDIR(stats.st_mode):
                    snapshot.add((
                        p,
                        stats.st_mode,
                        stats.st_uid,
                        stats.st_gid
                    ))

                # Path points to file.
                else:
                    snapshot.add((
                        p,
                        stats.st_mode,
                        stats.st_uid,
                        stats.st_gid,
                        stats.st_mtime_ns,
                        stats.st_size
                    ))

            if not self.is_recursive:
                break

        return snapshot

    def check(self):
        s = self._get_snapshot()
        if self.snapshot != s:
            self.target(*self.args, **self.kwargs)
            self.snapshot = s
            return True
        return False

    def start(self):

        if not self.is_stopped:
            return False

        self.check()

        self.check_thread = threading.Timer(self.check_interval, self.check)
        self.check_thread.name = repr(self)
        self.check_thread.daemon = True
        self.check_thread.start()
        return True

    def stop(self):

        if self.check_thread:
            self.check_thread.cancel()

            while self.check_thread.is_alive():
                pass

            self.check_thread = None
            return True
        return False




class FileMonitor:
    """Watch for changes in files.

    Use watch() method to watch path (and everything inside it) and run given
    function when something changes.

    """

    def __init__(self):

        # Next check is run after this amount of time.
        self.interval = config.watch_interval

        self.observers = []
        self._enabled = False

        self.lock = threading.Lock()
        self.monitor = None             # Thread used for running self.check()

    @property
    def is_enabled(self):
        if (self.monitor and self.monitor.is_alive()) or self._enabled:
            return True
        return False

    def watch(self, path, exclude, function, *args, **kwargs):
        """Watches given path and run function when something changed."""

        observer = Watcher(path, function, args, kwargs, ignored_paths=exclude)
        self.observers.append(observer)
        return observer

    def _check(self):
        """Checks each observer. Runs by self.monitor thread."""

        with self.lock:
            if self._enabled:
                for i in self.observers[:]:
                    if i.check():
                        i.run_function()

                self.monitor = threading.Timer(self.interval, self._check)
                self.monitor.name = 'Watcher: ' + str(len(self.observers))
                self.monitor.daemon = True
                self.monitor.start()

    def disable(self):
        """Stops watching. Important: it do not clear observers, you can always
        use enable() to start watching again."""

        if self.monitor:
            self.monitor.cancel()
        self._enabled = False

    def enable(self):
        """Starts watching using observers."""

        self._enabled = True
        self._check()

    def clear(self):
        """Removes all observers."""

        self.observers = []
        if self.monitor:
            self.monitor.cancel()


