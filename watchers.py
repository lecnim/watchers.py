"""
watchers.py

Script that monitors changes in the file system using watchers instances.

TODO: Documentation
TODO: Better benchmark function

"""

import os
import sys
import threading
from stat import *
from collections import namedtuple

__version__ = '1.0.1-rc.1'

# Minimum python 3.2
if sys.hexversion < 0x030200F0:
    raise ImportError('Python < 3.2 not supported!')

# Python 3.2 do not support ns in os.stats!
PYTHON32 = True if sys.hexversion < 0x030300F0 else False


class BaseWatcher:
    """Base watcher class. All other watcher should inherit from this class."""

    def __init__(self, interval):

        self._is_alive = False
        self.lock = threading.Lock()
        self.check_thread = None
        # Amount of time (in seconds) between running polling methods.
        self.interval = interval

    @property
    def is_alive(self):
        if self._is_alive \
           or (self.check_thread and self.check_thread.is_alive()):
            return True
        return False

    def check(self):
        """This method should be override by children classes.
        Attribute self.interval sets how often it is executed."""
        pass

    def _prepare_check(self):
        """This method is run in the Timer thread and it triggers check() method."""

        self.check()
        self._start_timer_thread()

    def _start_timer_thread(self, check_interval=None):
        """Starts new Timer thread, it will run check after time interval."""

        # Lock pauses stop() method.
        # Check if the watcher is alive because stop() can kill it during
        # execution of this method.
        with self.lock:
            if self._is_alive:

                if check_interval is None:
                    check_interval = self.interval

                self.check_thread = threading.Timer(check_interval,
                                                    self._prepare_check)
                self.check_thread.name = repr(self)
                self.check_thread.daemon = True
                self.check_thread.start()

    def start(self):
        """Starts watching. Returns False if the watcher is already started."""

        if self._is_alive:
            return False

        self._is_alive = True
        self._start_timer_thread(0)
        return True

    def stop(self):
        """Stops watching. Returns False if the watcher is already stopped."""

        if self._is_alive:

            # Lock prevents starting new Timer threads.
            with self.lock:
                self._is_alive = False
                self.check_thread.cancel()

            # Timer thread canceled, wait for join it.
            if threading.current_thread() != self.check_thread:
                self.check_thread.join()
            return True

        # Watcher already stopped.
        else:
            return False


# Watchers.

class Item:
    """Represents a file or a directory."""

    def __init__(self, path):

        # Path can be deleted during creating an Item instance.
        self.path = path
        try:
            self.stat = os.stat(path)
        except (IOError, OSError):
            self.path = None

        if self.path:
            if S_ISDIR(self.stat.st_mode):
                self.is_file = False
            else:
                self.is_file = True

    def is_modified(self):
        """Returns True if a file/directory was modified."""

        # Path can be deleted before this method.
        try:
            stat = os.stat(self.path)
        except (IOError, OSError):
            return True

        if not self.is_file:
            # st_mode: File mode (permissions)
            # st_uid: Owner id.
            # st_gid: Group id.
            a = self.stat.st_mode, self.stat.st_uid, self.stat.st_gid
            b = stat.st_mode, stat.st_uid, stat.st_gid
            if a != b:
                self.stat = stat
                return True
            return False

        # Check if a file is modified.
        a = self.stat.st_mtime, self.stat.st_size, self.stat.st_mode, \
            self.stat.st_uid, self.stat.st_gid
        b = stat.st_mtime, stat.st_size, stat.st_mode, stat.st_uid, stat.st_gid
        if a != b:
            self.stat = stat
            return True
        return False


class Watcher(BaseWatcher):
    """Watcher with events."""

    def __init__(self, check_interval, path, recursive=False, filter=None):
        super().__init__(check_interval)

        # Path must be always absolute!
        self.path = os.path.abspath(path)
        self.is_recursive = recursive

        # Callable that checks ignored paths.
        self.filter = filter
        self._events = {}

        # List of watched files, key is a file path, value is an Item instance.
        self.watched_paths = {}

        for path in self._walk():
            self.watched_paths[path] = Item(path)

    def __repr__(self):
        args = self.__class__.__name__, self.path, self.is_recursive
        return "{}(path={!r}, recursive={!r})".format(*args)

    def _walk(self):
        """Yields watched paths (already filtered)."""

        for path, dirs, files in os.walk(self.path):
            for i in dirs + files:
                p = os.path.join(path, i)
                if self.filter and not self.filter(p):
                    continue
                yield p
            if not self.is_recursive:
                break

    def check(self):
        """Detects changes in a file system. Returns True if something changed."""

        result = False
        stack = {}

        for path in self._walk():
            if self._path_changed(path, stack):
                result = True

        # Deleted paths.
        if self.watched_paths:
            for path in self.watched_paths.values():
                self.on_deleted(path)
                result = True

        self.watched_paths = stack
        return result

    def _path_changed(self, path, stack):
        """Checks if a path was modified or created."""

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
        x = Item(path)
        if x.path:
            stack[path] = x
            self.on_created(x)
        return True

    # Events.
    # TODO: Is this events system useful? I mean calling  events methods like this:
    #       Watcher.on_created(foo)

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


class SimpleWatcher(BaseWatcher):
    """A Watcher that runs callable when file system has changed."""

    def __init__(self, interval, path, target, args=(), kwargs=None,
                 recursive=False, filter=None):
        super().__init__(interval)

        self.path = os.path.abspath(path)
        self.is_recursive = recursive
        self.filter = filter

        self.target = target
        self.args = args
        self.kwargs = {} if not kwargs else kwargs

        self.snapshot = self._get_snapshot()

    def __repr__(self):
        args = self.__class__.__name__, self.path, self.is_recursive
        return "{}(path={!r}, recursive={!r})".format(*args)

    def _filtered_paths(self, root, paths):
        """Yields filtered paths using self.filter and skips deleted ones."""

        for i in paths:
            if self.filter and not self.filter(os.path.join(root, i)):
                continue

            path = os.path.join(root, i)
            try:
                stats = os.stat(path)
            # A path could be deleted during execution of this method.
            except (IOError, OSError):
                pass
            else:
                yield path, stats

    def _get_snapshot(self):
        """Returns set with all paths in self.path location."""

        snapshot = set()

        for path, dirs, files in os.walk(self.path):

            # Files.
            for p, stats in self._filtered_paths(path, dirs):
                snapshot.add((
                    p, stats.st_mode, stats.st_uid, stats.st_gid
                ))

            # Directories.
            for p, stats in self._filtered_paths(path, files):
                snapshot.add((
                    p,
                    stats.st_mode, stats.st_uid, stats.st_gid,
                    stats.st_mtime if PYTHON32 else stats.st_mtime_ns,
                    stats.st_size
                ))

            if not self.is_recursive:
                break
        return snapshot

    def check(self):
        """Detects changes in a file system. Returns True if something changed."""

        s = self._get_snapshot()
        if self.snapshot != s:
            self.target(*self.args, **self.kwargs)
            self.snapshot = s
            return True
        return False


class Manager:
    """Manager, class that gather watcher instances in one place."""

    def __init__(self):
        self.watchers = set()
        self.watchers_lock = threading.Lock()

    def __repr__(self):
        args = self.__class__.__name__, len(self.watchers)
        return "{}(watchers={!r})".format(*args)

    def add(self, watcher):
        """Adds a watcher instance to this manager. Returns False if the manager
        already has this watcher."""

        if not watcher in self.watchers:

            # Adding to set is thread-safe?
            with self.watchers_lock:
                self.watchers.add(watcher)
            return True
        return False

    def remove(self, watcher):
        """Removes a watcher instance from this manager.
        Raises KeyError if a watcher is not available in the manager."""

        # Removing from set is thread-safe?
        with self.watchers_lock:
            try:
                self.watchers.remove(watcher)
            except KeyError:
                raise KeyError('Manager.remove(x): watcher x not in manager')
        return True

    def clear(self):
        """Removes all watchers instances from this manager. Remember that this
        method do not stops them."""

        with self.watchers_lock:
            self.watchers = set()

    def start(self):
        """Starts all watchers, skips already started ones."""

        # with self.watchers_lock:
        for i in self.watchers.copy():
            if not i.is_alive:
                i.start()

    def stop(self):
        """Stops all watchers."""

        # with self.watchers_lock:
        for i in self.watchers.copy():
            if i.is_alive:
                i.stop()

    def check(self):
        """Triggers check in each watcher instance."""

        with self.watchers_lock:
            x = self.watchers.copy()

        # With this lock threads cannot modify self.watcher.
        for i in x:
            i.check()
