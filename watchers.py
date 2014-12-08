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




CREATED = 'created'
MODIFIED = 'modified'
DELETED = 'deleted'

STATUS_CREATED = 'created'
STATUS_MODIFIED = 'modified'
STATUS_DELETED = 'deleted'


Event = namedtuple('Event', ['status', 'path', 'is_file'])

#
# class Event:
#     def __init__(self, status, path, is_file=None):
#         self.status = status
#         self.path = path
#         self.is_file = os.path.isfile(path) if is_file is None else is_file
#         self.is_directory = not self.is_file
#
#     def __repr__(self):
#         return ("<{class_name}: status={status}, "
#                 "path={path}, is_file={is_file}>").format(
#             class_name=self.__class__.__name__,
#             status=self.status,
#             path=self.path,
#             is_file=self.is_file)
#
#
#     def __eq__(self, other):
#         if (self.status == other.status,
#             self.path == other.path,
#             self.is_file == other.is_file):
#             return True
#         return False
#
#
#     def __hash__(self):
#         return hash((self.status, self.path, self.is_file))


# Investigators

class Investigator:
    """Detects if a file system item has been modified."""

    def on_create_item(self, item):
        pass
    def on_delete_item(self, item):
        pass
    def is_modified(self, item):
        pass

class PermissionsInvestigator(Investigator):
    """Detects if an item permissions has been modified."""

    def __init__(self, item):
        self.stats = item.stat

    def on_create_item(self, item):
        self.stats = item.stat

    def is_modified(self, item):

        # st_mode: File mode (permissions)
        # st_uid: Owner id
        # st_gid: Group id
        stat_a = item.stat.st_mode, item.stat.st_uid, item.stat.st_gid
        stat_b = self.stats.st_mode, self.stats.st_uid, self.stats.st_gid

        self.stats = item.stat
        return True if stat_a != stat_b else False

class FileInvestigator(Investigator):
    """Detects if an item size or modification time has been modified."""

    def __init__(self, item):
        self.stats = item.stat

    def on_create_item(self, item):
        self.stats = item.stat

    def is_modified(self, item):

        stat_a = item.stat.st_mtime, item.stat.st_size
        stat_b = self.stats.st_mtime, self.stats.st_size

        self.stats = item.stat
        return True if stat_a != stat_b else False

class ChildrenItemsInvestigator(Investigator):
    """Detects if a number of child items in directory has been changed."""

    def __init__(self, item):

        self.dirs = None
        self.files = None
        self.on_create_item(item)

    def on_create_item(self, item):

        for path, dirs, files in os.walk(item.full_path):
            self.dirs = set(dirs)
            self.files = set(files)
            break

    def is_modified(self, item):

        for _, dirs, files in os.walk(item.full_path):
            if set(dirs) != self.dirs or set(files) != self.files:
                self.dirs = set(dirs)
                self.files = set(files)
                return True
            break
        return False


# Polling classes.

class ItemPoller:

    def __init__(self, path, root=None, investigators=None):

        self.path = path

        if root is None:
            self.full_path = os.path.abspath(path)
        else:
            self.full_path = os.path.normpath(os.path.join(root, path))

        self.stat = os.stat(self.full_path)
        self.status = None
        self.is_file = None

        self.investigators = [i(self) for i in investigators] if investigators else None

        # Polling directory.

        if S_ISDIR(self.stat.st_mode):
            self.is_file = False
            if investigators is None:
                self.investigators = [PermissionsInvestigator(self),
                                      ChildrenItemsInvestigator(self)]

        # Polling file.

        else:
            self.is_file = True
            if investigators is None:
                self.investigators = [FileInvestigator(self),
                                      PermissionsInvestigator(self)]

    def __repr__(self):
        return ("<{class_name}: path={path}>").format(
            class_name=self.__class__.__name__,
            path=self.path)

    def exists(self):

        if self.is_file:
            return os.path.isfile(self.full_path)
        return os.path.isdir(self.full_path)

    def poll(self):

        try:
            stat = os.stat(self.full_path)
        except (IOError, OSError):
            return self.dispatch_event(STATUS_DELETED)

        # Path found.

        # Swapped file and directory.
        if S_ISDIR(stat.st_mode) and self.is_file or \
           not S_ISDIR(stat.st_mode) and not self.is_file:
            return self.dispatch_event(STATUS_DELETED)

        self.stat = stat

        # Item was deleted, but it lives again!
        if self.status == STATUS_DELETED:
            return self.dispatch_event(STATUS_CREATED)

        if True in [i.is_modified(self) for i in self.investigators]:
            return self.dispatch_event(STATUS_MODIFIED)

        # Nothing changed.
        self.status = None
        return None

    def dispatch_event(self, event_type):

        if event_type == STATUS_DELETED:

            for i in self.investigators:
                i.on_delete_item(self)

            self.stat = None

            if self.status == STATUS_DELETED:
                return None
            else:
                e = Event(STATUS_DELETED, self.path, self.is_file)

                self.status = STATUS_DELETED
                self.on_deleted(e)
                return e

        elif event_type == STATUS_CREATED:

            for i in self.investigators:
                i.on_create_item(self)

            e = Event(STATUS_CREATED, self.path, self.is_file)

            self.status = STATUS_CREATED
            self.on_created(e)
            return e

        elif event_type == STATUS_MODIFIED:

            e = Event(STATUS_MODIFIED, self.path, self.is_file)

            self.status = STATUS_MODIFIED
            self.on_modified(e)
            return e

    # Events

    def on_created(self, event):
        pass

    def on_modified(self, event):
        pass

    def on_deleted(self, event):
        pass

PathPolling = ItemPoller


class Directory:
    """Watcher with events."""

    def __init__(self, path, recursive=False, filter=None):

        # Path must be always absolute!

        self.path = path
        self.root = os.getcwd()
        # root + path
        self.full_path = os.path.join(self.root, path)

        self.is_recursive = recursive
        # Callable that checks ignored items_paths.
        self.filter = filter

        # List of PathPolling instances.
        self.items = [self.new_item(path) for path in self._walk()]

        self.paths = {}
        self.dirs = []
        for i in self.items:

            if not i.is_file:
                if not i.path in self.paths:
                    self.paths[i.path] = {'files': [], 'dirs': []}
                    self.dirs.append(i.path)

            if i.path != self.path:

                root = os.path.dirname(i.path)

                if i.is_file:
                    self.paths[root]['files'].append(i)
                else:
                    self.paths[root]['dirs'].append(i)


        print(self.dirs)



    def __repr__(self):

        return ("<{class_name}: path={path}, "
                "is_recursive={is_recursive}>").format(
            class_name=self.__class__.__name__,
            path=self.path,
            is_recursive=self.is_recursive)

    @property
    def items_paths(self):
        return [i.path for i in self.items]

    def new_item(self, path):

        if os.path.isdir(path):
            x = [ChildrenItemsInvestigator, PermissionsInvestigator]
        else:
            x = [FileInvestigator, PermissionsInvestigator]

        return ItemPoller(path, root=self.root, investigators=x)

    def _walk(self):
        """Yields watched paths, already filtered."""

        # Fixed: Also filter root directory!
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

    def _iter_created_items(self):

        for path in self._walk():
            if path not in self.items_paths:

                try:
                    yield self.new_item(path)
                # Path could be deleted during this method.
                except (IOError, OSError):
                    continue

    def _get_parent_item(self, item):

        root = os.path.dirname(item.path)

        for i in self.items:
            if i.path == root:
                return i

    def _dispatch_event(self, event_status, item):

        event = item.dispatch_event(event_status)

        if event_status is STATUS_CREATED:
            self.on_created(event)
        elif event_status is STATUS_DELETED:
            self.on_deleted(event)
        elif event_status is STATUS_MODIFIED:
            self.on_modified(event)

        return event

    def _poll_item(self, item):

        event = item.poll()
        if event:
            if event.status == STATUS_MODIFIED:
                self.on_modified(event)
                yield event

            elif event.status == STATUS_DELETED:

                parent = self._get_parent_item(item)
                if parent:
                    yield self._dispatch_event(STATUS_MODIFIED, parent)

                self.on_deleted(event)
                yield event

    def walk_items(self, top_down=True, dirs_first=False):

        dirs = self.dirs if top_down else reversed(self.dirs)

        if top_down:
            yield self.items[0]

        for path in dirs:
            items_order = ['dirs', 'files'] if dirs_first else ['files', 'dirs']
            for x in items_order:
                for item in self.paths[path][x]:
                    yield item

        if not top_down:
            yield self.items[0]

    def poll(self):

        events = []


        index = 0


        # CREATE
        # Add to items using path order
        # MODIFY
        # Each item if not status = CREATED => poll()

        for path in self._walk():
            print(path)
            # Create

            if path not in self.items_paths:

                try:
                    item = self.new_item(path)
                # Path could be deleted during this method.
                except (IOError, OSError):
                    continue

                print(index)
                # self.items.append(item)

                self.items.insert(index+1, item)
                index = index + 1


                root = os.path.dirname(item.path)
                if not root in self.paths:
                    self.paths[root] = {'files': [], 'dirs': []}

                if i.is_file:
                    self.paths[root]['files'].append(i)
                else:
                    self.paths[root]['dirs'].append(i)


                events.append(self._dispatch_event(STATUS_CREATED, item))
                # parent = self._get_parent_item(item)
                # if parent:
                #     events.append(self._dispatch_event(STATUS_MODIFIED, parent))

            else:

                for i in self.items:
                    if i.path == path:
                        index = self.items.index(i)
            # HERE

            # else:
            #
            #     for item in self.items:
            #         if item.path == path:
            #
            #             print(item)
            #
            #             event = item.poll()
            #             if event:
            #                 if event.status == STATUS_MODIFIED:
            #                     self.on_modified(event)
            #                     events.append(event)
            #
            #                 elif event.status == STATUS_DELETED:
            #
            #
            #
            #                     self.on_deleted(event)
            #
            #
            #                     parent = self._get_parent_item(item)
            #                     if parent:
            #                         deleted_events.insert(0, self._dispatch_event(STATUS_MODIFIED, parent))
            #
            #                     deleted_events.insert(event)
            #                     deleted_items.append(item)


        deleted = []
        for item in self.walk_items(top_down=False):

            if not item.exists():
                e = item.dispatch_event(STATUS_DELETED)
                events.append(e)
                self.on_deleted(e)
                deleted.append(item)

        self.items = [i for i in self.items if i not in deleted]

            # event = item.poll()
            # if event:
            #
            #     if event.status == STATUS_DELETED:
            #         events.append(event)
            #         self.on_deleted(event)
            #         deleted_items.append(item)
            #
            #     elif event.status == STATUS_MODIFIED:
            #         events_mod.append(event)

        for item in self.walk_items():

            event = item.poll()

            if item.status == STATUS_MODIFIED:
                self.on_modified(event)
                events.append(event)


        # deleted_items = []
        # for item in reversed(self.items):
        #
        #
        #     event = item.poll()
        #     if event:
        #         if event.status == STATUS_MODIFIED:
        #             self.on_modified(event)
        #             events.append(event)
        #
        #         elif event.status == STATUS_DELETED:
        #
        #             events.append(event)
        #
        #             parent = self._get_parent_item(item)
        #             if parent:
        #                 events.append(self._dispatch_event(STATUS_MODIFIED, parent))
        #
        #             self.on_deleted(event)
        #
        #             deleted_items.append(item)



        # deleted_items = []
        # for item in reversed(self.items):
        #     for event in self._poll_item(item):
        #         events.append(event)
        #         if event.status is STATUS_DELETED:
        #             deleted_items.append(item)

        # Subtract deleted items.
        # self.items = [i for i in self.items if i not in deleted]

        print(self.items)
        return events

    # Events

    def on_created(self, item):
        pass

    def on_modified(self, item):
        pass

    def on_deleted(self, item):
        pass

DirectoryPolling = Directory



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





class FilePolling(ItemPoller):
    def __init__(self, path):
        ItemPoller.__init__(self, path,
                      investigators=[FileInvestigator, PermissionsInvestigator])



class FileWatcher(BaseWatcher, ItemPoller):
    def __init__(self, interval, path):
        BaseWatcher.__init__(self, interval)
        ItemPoller.__init__(self, path,
                      investigators=[FilePoller(self), PermissionsPoller(self)])



class DirectoryWatcher():
    pass

class ItemWatcher(BaseWatcher, ItemPoller):
    """TODO"""

    def __init__(self, interval, path):
        BaseWatcher.__init__(self, interval)
        ItemPoller.__init__(self, path)

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
