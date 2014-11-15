"""
watchers.py

Script that monitors changes in the file system using watchers instances.

TODO: Documentation
TODO: Better benchmark function

"""

# 2 seconds for last modified time,
# 10 ms for creation time,
# 1 day for access date,
# 2 seconds for deletion time

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


Status = namedtuple('Status', ['type', 'path'])

CREATED = 1
MODIFIED = 2
DELETED = 3


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

# class BaseItem:
#
#     def __init__(self, path):
#
#         self.status = None
#         self.path = os.path.abspath(path)
#         self.is_file = None
#         self.stat = os.stat(path)
#
#         # Path can be deleted during creating an Item instance.
#
#         try:
#             self.stat = os.stat(path)
#         except (IOError, OSError):
#             self.path = None
#             self.status = DELETED
#
#         if self.path:
#             if S_ISDIR(self.stat.st_mode):
#                 self.is_file = False
#             else:
#                 self.is_file = True
#
#     def __repr__(self):
#         args = self.__class__.__name__, self.path, self.status
#         return "{}(path={!r}, status={!r})".format(*args)
#
#     def poll(self):
#
#         try:
#             stat = os.stat(self.path)
#         except (IOError, OSError):
#             stat = None
#
#
#
#
#         # Path not found.
#         if not stat:
#             if self.status == DELETED:
#                 return None
#             else:
#                 self.status = DELETED
#                 self.stat = None
#                 self.on_deleted()
#                 return DELETED
#
#         # Path found.
#         else:
#
#             if S_ISDIR(stat.st_mode) and self.is_file or \
#                not S_ISDIR(stat.st_mode) and not self.is_file:
#                 self.status = DELETED
#                 self.stat = None
#                 self.on_deleted()
#                 return DELETED
#
#             if self.status == DELETED:
#                 self.stat = stat
#                 self.status = CREATED
#                 self.on_created()
#                 return CREATED
#
#             else:
#
#                 if not self.is_file:
#                     # st_mode: File mode (permissions)
#                     # st_uid: Owner id.
#                     # st_gid: Group id.
#                     a = self.stat.st_mode, self.stat.st_uid, self.stat.st_gid, self.stat.st_mtime, self.stat.st_ctime
#                     b = stat.st_mode, stat.st_uid, stat.st_gid, stat.st_mtime, stat.st_ctime
#
#                     if a != b:
#                         self.stat = stat
#                         self.status = MODIFIED
#                         self.on_modified()
#                         return MODIFIED
#                     return None
#
#                 # Check if a file is modified.
#                 a = self.stat.st_mtime, self.stat.st_size, self.stat.st_mode, \
#                     self.stat.st_uid, self.stat.st_gid
#                 b = stat.st_mtime, stat.st_size, stat.st_mode, stat.st_uid, stat.st_gid
#                 if a != b:
#                     self.stat = stat
#                     self.status = MODIFIED
#
#                     self.on_modified()
#                     return MODIFIED
#                 return None
#
#     def on_created(self):
#         pass
#
#     def on_modified(self):
#         pass
#
#     def on_deleted(self):
#         pass
#
# #
#
# class DirectoryPoller(BaseItem):
#
#     def __init__(self):
#
#




class BasePoller:

    def __init__(self, path, is_file):
        self.path = path
        self.is_file = is_file

    def compare(self, stat, item):
        pass

    def poll(self, item):

        try:
            stat = os.stat(item.path)
        except (IOError, OSError):
            if item.status == DELETED:
                return None, None
            else:
                return DELETED, None

        # Path found.

        # Swapped file and directory.
        if S_ISDIR(stat.st_mode) and item.is_file or \
           not S_ISDIR(stat.st_mode) and not item.is_file:

            if item.status == DELETED:
                return None, None
            else:
                return DELETED, None

        # Item was deleted, but it lives again!
        if item.status == DELETED:
            self.on_create()
            return CREATED, stat

        if self.compare(stat, item):
            return MODIFIED, stat
        else:
            return None, stat

    def on_create(self):
        return True


class FilePoller(BasePoller):

    def compare(self, stat, item):

        # Check if a file is modified.
        a = item.stat.st_mtime, item.stat.st_size, item.stat.st_mode, \
            item.stat.st_uid, item.stat.st_gid
        b = stat.st_mtime, stat.st_size, stat.st_mode, stat.st_uid, stat.st_gid

        if a != b:
            return True
        else:
            return False

class DirectoryPollerSkippinh(BasePoller):

    def compare(self, stat, item):

        # st_mode: File mode (permissions)
        # st_uid: Owner id.
        # st_gid: Group id.
        a = item.stat.st_mode, item.stat.st_uid, item.stat.st_gid
        b = stat.st_mode, stat.st_uid, stat.st_gid

        if a != b:
            return True
        return False


class DirectoryPoller(DirectoryPollerSkippinh):

    def __init__(self, path, is_file):

        super().__init__(path, is_file)

        for _, dirs, files in os.walk(self.path):
            self.dirs = set(dirs)
            self.files = set(files)
            break

    def on_create(self):

        for path, dirs, files in os.walk(self.path):
            self.dirs = set(dirs)
            self.files = set(files)
            break

    def compare(self, stat, item):
        for path, dirs, files in os.walk(self.path):
            if set(dirs) != self.dirs or set(files) != self.files:
                self.dirs = set(dirs)
                self.files = set(files)
                return True
            break

        return DirectoryPollerSkippinh.compare(self, stat, item)




class Item:

    def __init__(self, path, poller=DirectoryPoller):

        self.path = os.path.abspath(path)
        self.stat = os.stat(path)

        self.status = None
        self.is_file = None
        # self.poller = poller

        self.children = True


        if S_ISDIR(self.stat.st_mode):
            self.is_file = False
            self.poller = poller(self.path, self.is_file)
        else:
            self.is_file = True
            # if poller is None:
            self.poller = FilePoller(self.path, self.is_file)

    def poll(self):
        status, stat = self.poller.poll(self)

        if self.status == DELETED and status is None:
            self.status = DELETED
        else:
            self.status = status

        self.stat = stat
        return status





class Directory:
    """Watcher with events."""

    def __init__(self, path, recursive=False, filter=None):

        # Path must be always absolute!
        self.path = os.path.abspath(path)
        self.is_recursive = recursive

        # Callable that checks ignored paths.
        self.filter = filter
        self._events = {}

        # List of watched files, key is a file path, value is an Item instance.
        self.watched_paths = {}

        for path in self._walk():
            i = Item(path, poller=DirectoryPollerSkippinh)
            self.watched_paths[path] = i

    def __repr__(self):
        args = self.__class__.__name__, self.path, self.is_recursive
        return "{}(path={!r}, recursive={!r})".format(*args)

    def _walk(self):
        """Yields watched paths (already filtered)."""

        # yield self.path

        for path, dirs, files in os.walk(self.path):
            for i in dirs + files:
                p = os.path.join(path, i)
                if self.filter and not self.filter(p):
                    continue
                yield p
            if not self.is_recursive:
                break


    def poll(self):

        events = []

        for i in self.watched_paths.copy().values():

            status = i.poll()
            print(i, status)



            if status == MODIFIED:

                # if not self.is_recursive:
                #     if not i.is_file:
                #         continue

                self.on_modified(i)
                events.append(i)

            elif status == DELETED:
                self.on_deleted(i)
                self.watched_paths.pop(i.path)
                events.append(i)

        for path in self._walk():
            if path not in self.watched_paths:
                try:
                    x = Item(path)
                except (IOError, OSError):
                    continue
                x.status = CREATED
                if x.path:
                    self.watched_paths[path] = x
                    self.on_created(x)
                    events.append(x)

        return events


    def on_created(self, item):
        pass

    def on_modified(self, item):
        pass

    def on_deleted(self, item):
        pass



class ItemWatcher(BaseWatcher, Item):
    """TODO"""

    def __init__(self, interval, path):
        BaseWatcher.__init__(self, interval)
        Item.__init__(self, path)

    def __repr__(self):
        args = self.__class__.__name__, self.path
        return "{}(path={!r})".format(*args)

    def check(self):

        return True if self.poll() else False





class Watcher(BaseWatcher, Directory):
    """Watcher with events."""

    def __init__(self, interval, path, recursive=False, filter=None):
        BaseWatcher.__init__(self, interval)
        Directory.__init__(self, path, recursive, filter)



    def __repr__(self):
        args = self.__class__.__name__, self.path, self.is_recursive
        return "{}(path={!r}, recursive={!r})".format(*args)


    def check(self):
        """Detects changes in a file system. Returns True if something changed."""

        return True if self.poll() else False







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
