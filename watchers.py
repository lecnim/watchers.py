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


# Investigators

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

        self.is_recursive = recursive
        # Callable that checks ignored items_paths.
        self.filter = filter

        # List of PathPolling instances.
        self.items = [self.create_item(path) for path in self._walk()]

        self.directory_tree = {}
        self.update_tree()

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

    # def investigate(self):
    #
    #     events = []
    #
    #     for item in self.items:
    #         e = item.investigate()
    #         if e:
    #             events.append((item, e))
    #
    #     items = []
    #     for i in self._walk():
    #         item = self.create_item(i)
    #         items.append(item)
    #
    #         if not self.item_exists(item):
    #             events.append((item, Event(EVENT_TYPE_CREATED, item.path, item.is_file)))
    #
    #     events = self.sort_events(events)
    #     self.dispatch_events(events)
    #     self.items = items
    #
    #     return [i[1] for i in events]

    def poll(self):

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
        self.dispatch_events(events)
        self.items = items

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

    # TODO:
    # What to do with this?

    def walk_dirs(self, top_down=True):

        items = self.items if top_down else reversed(self.items)

        for i in items:
            if not i.is_file:
                yield i.path

    def walk_items(self, top_down=True, dirs_first=False):

        if top_down:
            yield self.items[0]

        for path in self.walk_dirs(top_down):
            items_order = [1, 0] if dirs_first else [0, 1]
            for x in items_order:
                for item in self.directory_tree[path][x]:
                    yield item

        if not top_down:
            yield self.items[0]

    def update_tree(self):

        self.directory_tree = {}

        for i in self.items:

            if not i.is_file:
                if not i.path in self.directory_tree:
                    # self.paths[i.path] = {'files': [], 'dirs': []}
                    # self.dirs.append(i.path)

                    self.directory_tree[i.path] = [], []

            if i.path != self.path:

                root = os.path.dirname(i.path)

                if i.is_file:
                    # self.paths[root]['files'].append(i)

                    self.directory_tree[root][0].append(i)
                else:
                    # self.paths[root]['dirs'].append(i)
                    self.directory_tree[root][1].append(i)


# GroupPolling
class BatchPolling:

    def __init__(self):
        self.pollers = []

    def add(self, x):
        self.pollers.append(x)

    def remove(self, x):
        self.pollers.remove(x)

    # def investigate(self):
    #     pass

    def poll(self):

        events = []

        for i in self.pollers:
            result = i.poll()
            if isinstance(result, Event):
                events.append(result)
            else:
                events.extend(result)

        return events



# Watcher classes.

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

    @property
    def is_active(self):
        return self.is_alive

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

    def join(self):

        # TODO: time.sleep? :(
        while self.is_alive:
            time.sleep(0.1)


class DirectoryWatcher(BaseWatcher, DirectoryPolling):
    def __init__(self, interval, path, recursive=False, filter=None):
        BaseWatcher.__init__(self, interval)
        DirectoryPolling.__init__(self, path, recursive, filter)

    def __repr__(self):
        return ("<{class_name}: interval={interval}, path={path}, "
                "is_recursive={is_recursive}>").format(
            class_name=self.__class__.__name__,
            interval=self.interval,
            path=self.path,
            is_recursive=self.is_recursive)

    def check(self):
        return True if self.poll() else False


class PathWatcher(BaseWatcher, PathPolling):
    def __init__(self, interval, path):
        BaseWatcher.__init__(self, interval)
        PathPolling.__init__(self, path)

    def __repr__(self):
        return ("<{class_name}: interval={interval}, path={path}, "
                "is_file={is_file}>").format(
            class_name=self.__class__.__name__,
            interval=self.interval,
            path=self.path,
            is_file=self.is_file)

    def check(self):
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
        """Yields filtered items_paths using self.filter and skips deleted ones."""

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
        """Returns set with all items_paths in self.path location."""

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
