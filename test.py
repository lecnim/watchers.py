"""
Testing!
"""

import os
import os.path
import stat
import sys
import unittest
import shutil
import tempfile
import timeit
import time
import platform

import watchers
from watchers import Watcher, SimpleWatcher, Manager

# For faster testing.
CHECK_INTERVAL = 0.25

# Shortcuts.

def create_file(*path, data='hello world!'):
    """Creates a new file with a given data."""
    with open(os.path.join(*path), 'w') as file:
        file.write(data)


def create_dir(*path):
    """Creates a new directory."""
    os.mkdir(os.path.join(*path))


def delete_file(*path):
    """Removes a file."""
    os.remove(os.path.join(*path))


def delete_dir(*path):
    """Removes a directory."""
    shutil.rmtree(os.path.join(*path))


def modify_file(*path):
    """Modifies a file data - appends 'hello'."""
    with open(os.path.join(*path), 'a') as file:
        file.write('hello')


def absolute_paths(*paths):
    """Returns paths converted to absolute paths."""
    return [os.path.abspath(i) for i in paths]


def create_test_files():
    """Returns a path to a temporary directory with example files used during
    tests."""

    path = tempfile.mkdtemp()

    # ~temp/a.py
    # ~temp/b.py
    # ~temp/a.txt
    create_file(path, 'a.py')
    create_file(path, 'b.py')
    create_file(path, 'a.txt')

    # ~temp/x/foo.html
    # ~temp/x/foo.py
    # ~temp/x/y/foo.py
    create_dir(path, 'x')
    create_file(path, 'x', 'foo.html')
    create_file(path, 'x', 'foo.py')
    create_file(path, 'x', 'foo.txt')
    create_dir(path, 'x', 'y')
    create_file(path, 'x', 'y', 'foo.py')
    create_file(path, 'x', 'y', 'foo.txt')

    return path


# Tests.


class BaseTest(unittest.TestCase):
    """A base test class."""

    # Watcher class
    class_ = None
    # Class __init__ attributes
    kwargs = {}

    def setUp(self):

        # Create temporary directory with example files and change current
        # working directory to it.
        self.cwd = os.getcwd()
        self.temp_path = create_test_files()
        os.chdir(self.temp_path)

    def tearDown(self):

        # Go to previous working directory and clear temp files.
        os.chdir(self.cwd)
        shutil.rmtree(self.temp_path)

    def test_repr(self):
        print(self.class_(CHECK_INTERVAL, **self.kwargs))

    def test(self):
        """Should detects changes in a file system."""

        x = self.class_(CHECK_INTERVAL, **self.kwargs)

        # File created.

        create_file('new.txt')
        self.assertTrue(x.check())
        create_file('x', 'new.py')
        self.assertFalse(x.check())

        # File removed.

        delete_file('new.txt')
        self.assertTrue(x.check())
        delete_file('x', 'new.py')
        self.assertFalse(x.check())

        # File modified.

        modify_file('a.txt')
        self.assertTrue(x.check())
        modify_file('x', 'foo.py')
        self.assertFalse(x.check())

        # Directory created.

        create_dir('new_dir')
        self.assertTrue(x.check())
        create_dir('x', 'new_dir')
        self.assertFalse(x.check())

        # Directory removed.

        delete_dir('new_dir')
        self.assertTrue(x.check())
        delete_dir('x', 'new_dir')
        self.assertFalse(x.check())

    def test_recursive(self):
        """Should detects changes in a file system using recursive."""

        x = self.class_(CHECK_INTERVAL, recursive=True, **self.kwargs)

        # File created.

        create_file('new.txt')
        self.assertTrue(x.check())
        create_file('x', 'new.py')
        self.assertTrue(x.check())

        # File removed.

        delete_file('new.txt')
        self.assertTrue(x.check())
        delete_file('x', 'new.py')
        self.assertTrue(x.check())

        # File modified.

        modify_file('a.txt')
        self.assertTrue(x.check())
        modify_file('x', 'foo.py')
        self.assertTrue(x.check())

        # Directory created.

        create_dir('new_dir')
        self.assertTrue(x.check())
        create_dir('x', 'new_dir')
        self.assertTrue(x.check())

        # Directory removed.

        delete_dir('new_dir')
        self.assertTrue(x.check())
        delete_dir('x', 'new_dir')
        self.assertTrue(x.check())

    def test_filter(self):
        """Can use a filter to ignore paths."""

        x = self.class_(CHECK_INTERVAL, filter=lambda path: path.endswith('.txt'),
                        **self.kwargs)

        # File created.

        create_file('new.txt')
        self.assertTrue(x.check())
        create_file('new.file')
        self.assertFalse(x.check())
        create_file('x', 'new.txt')
        self.assertFalse(x.check())

        # File removed.

        delete_file('new.txt')
        self.assertTrue(x.check())
        delete_file('new.file')
        self.assertFalse(x.check())
        delete_file('x', 'new.txt')
        self.assertFalse(x.check())

        # File modified.

        modify_file('a.txt')
        self.assertTrue(x.check())
        modify_file('x', 'y', 'foo.txt')
        self.assertFalse(x.check())

        # Directory created.

        create_dir('new_dir')
        self.assertFalse(x.check())
        create_dir('new_dir.txt')
        self.assertTrue(x.check())
        create_dir('x', 'new_dir')
        self.assertFalse(x.check())
        create_dir('x', 'new_dir.txt')
        self.assertFalse(x.check())

        # Directory removed.

        delete_dir('new_dir')
        self.assertFalse(x.check())
        delete_dir('new_dir.txt')
        self.assertTrue(x.check())
        delete_dir('x', 'new_dir')
        self.assertFalse(x.check())
        delete_dir('x', 'new_dir.txt')
        self.assertFalse(x.check())

    def test_filter_and_recursive(self):
        """Can use a filter and recursive together."""

        x = self.class_(CHECK_INTERVAL, recursive=True,
                        filter=lambda path: path.endswith('.txt'),
                        **self.kwargs)

        # File created.

        create_file('new.txt')
        self.assertTrue(x.check())
        create_file('new.file')
        self.assertFalse(x.check())
        create_file('x', 'new.txt')
        self.assertTrue(x.check())

        # File removed.

        delete_file('new.txt')
        self.assertTrue(x.check())
        delete_file('new.file')
        self.assertFalse(x.check())
        delete_file('x', 'new.txt')
        self.assertTrue(x.check())

        # File modified.

        modify_file('a.txt')
        self.assertTrue(x.check())
        modify_file('x', 'y', 'foo.txt')
        self.assertTrue(x.check())

        # Directory created.

        create_dir('new_dir')
        self.assertFalse(x.check())
        create_dir('new_dir.txt')
        self.assertTrue(x.check())
        create_dir('x', 'new_dir.txt')
        self.assertTrue(x.check())
        create_dir('x', 'new_dir')
        self.assertFalse(x.check())

        # Directory removed.

        delete_dir('new_dir')
        self.assertFalse(x.check())
        delete_dir('new_dir.txt')
        self.assertTrue(x.check())
        delete_dir('x', 'new_dir.txt')
        self.assertTrue(x.check())
        delete_dir('x', 'new_dir')
        self.assertFalse(x.check())

    def test_permissions(self):
        """Should detects a file permission changes."""

        x = self.class_(CHECK_INTERVAL, **self.kwargs)

        # Windows supports read-only flag only!
        if platform.system() == 'Windows':

            # File with read-only attribute.
            os.chmod('a.txt', stat.S_IREAD)
            self.assertTrue(x.check())
            # Prevent PermissionError!
            os.chmod('a.txt', stat.S_IWRITE)

            # Directory with read-only attribute.
            os.chmod('x', stat.S_IREAD)
            self.assertTrue(x.check())
            # Prevent PermissionError!
            os.chmod('x', stat.S_IWRITE)

        else:

            # File permissions.

            os.chmod('a.txt', 0o777)
            self.assertTrue(x.check())

            # Directory permissions.

            os.chmod('x', 0o777)
            self.assertTrue(x.check())

    def test_recreate(self):
        """Should detects files and dirs recreations."""

        x = self.class_(CHECK_INTERVAL, **self.kwargs)
        y = self.class_(CHECK_INTERVAL, recursive=True, **self.kwargs)

        # Recreating same file - mod time should be different.
        delete_file('a.txt')
        time.sleep(0.5)
        create_file('a.txt')
        self.assertTrue(x.check())
        self.assertTrue(y.check())

        # Recreating same file with different content - size file is used.
        delete_file('a.txt')
        create_file('a.txt', data='hello')
        self.assertTrue(x.check())
        self.assertTrue(y.check())

        # Swapping file and directory.
        delete_file('a.txt')
        create_dir('a.txt')
        self.assertTrue(x.check())
        self.assertTrue(y.check())

        # Recreating same directory, but different content.
        delete_dir('x')
        time.sleep(0.5)
        create_dir('x')
        # Result is False, in not recursive mode it is not possible
        # to verify if directory was recreated or it content was change.
        # Because files on Linux has not "create time" attribute.
        self.assertFalse(x.check())
        self.assertTrue(y.check())

    @unittest.skipIf(platform.system() == 'Windows', 'Symlinks not supported!')
    def test_symlinks(self):
        """Should correctly use symlinks."""

        x = self.class_(CHECK_INTERVAL, **self.kwargs)
        # Symlink to file: file modified.

        os.symlink(os.path.join('x', 'foo.txt'), 'link_to_file')
        self.assertTrue(x.check())
        modify_file('x', 'foo.txt')
        self.assertTrue(x.check())

        # File modified in linked directory.

        os.symlink(os.path.join('x', 'y'), 'link_to_dir')
        self.assertTrue(x.check())
        modify_file('x', 'y', 'foo.txt')
        self.assertFalse(x.check())

    def test_check_interval(self):
        """Should correctly set a custom check interval."""

        x = self.class_(4, **self.kwargs)
        self.assertEqual(4, x.check_interval)

    def test_is_alive(self):
        """Should correctly set is_alive property."""

        x = self.class_(CHECK_INTERVAL, **self.kwargs)
        self.assertFalse(x.is_alive)

    def test_delete_during_check(self):
        """Should skip files deleted by a other process during check."""

        files = (self.temp_path, ['a.txt', 'b.txt'], [])

        def walk(*args, **kwargs):
            return [files]

        original_walk = os.walk
        os.walk = walk

        create_file('a.txt')
        create_file('b.txt')
        x = self.class_(CHECK_INTERVAL, **self.kwargs)
        x.check()
        delete_file('a.txt')

        try:
            self.assertTrue(x.check())
            files[1].remove('a.txt')
            self.assertFalse(x.check())
        except:
            raise
        finally:
            os.walk = original_walk


class TestWatcher(BaseTest):
    """A Watcher"""

    class_ = Watcher
    kwargs = {
        'path': '.'
    }

    def test_override_events(self):
        """Should run an overridden event methods with correct arguments."""

        created = None
        modified = None
        deleted = None

        class CustomWatcher(Watcher):
            def on_created(self, item):
                nonlocal created
                created = item

            def on_modified(self, item):
                nonlocal modified
                modified = item

            def on_deleted(self, item):
                nonlocal deleted
                deleted = item

        x = CustomWatcher(CHECK_INTERVAL, '.')

        # Created file.

        create_file('new.file')
        x.check()
        self.assertIsNotNone(created)
        self.assertTrue(created.is_file)
        self.assertEqual(created.path, os.path.abspath('new.file'))

        # Modified file.

        modify_file('new.file')
        x.check()
        self.assertIsNotNone(modified)
        self.assertTrue(modified.is_file)
        self.assertEqual(modified.path, os.path.abspath('new.file'))

        # Deleted file.

        delete_file('new.file')
        x.check()
        self.assertIsNotNone(deleted)
        self.assertTrue(deleted.is_file)
        self.assertEqual(deleted.path, os.path.abspath('new.file'))

    def test_on_file_created(self):
        """Should run an event if a file created."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_created(test, 1, b=1)
        create_file('new.file')
        x.check()
        self.assertEqual(2, i)

    def test_on_file_deleted(self):
        """Should run an event if a file deleted."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_deleted(test, 1, b=1)
        os.remove('a.py')
        x.check()
        self.assertEqual(2, i)

    def test_on_file_modified(self):
        """Should run an event if a file modified."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_modified(test, 1, b=1)
        modify_file('a.txt')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_created(self):
        """Should run an event if a directory created."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_created(test, 1, b=1)
        create_dir('new_dir')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_deleted(self):
        """Should run an event if a directory deleted."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_deleted(test, 1, b=1)
        delete_dir('x')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_modified(self):
        """Should run an event if a directory was modified."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher(CHECK_INTERVAL, '.')
        x.on_modified(test, 1, b=1)

        # Windows supports read-only flag only!
        if platform.system() == 'Windows':
            os.chmod('x', stat.S_IREAD)
            x.check()
            # Prevent PermissionError!
            os.chmod('x', stat.S_IWRITE)
        else:
            os.chmod('x', 0o777)
            x.check()
        self.assertEqual(2, i)

    def test_thread(self):
        """Can start a new thread to check a file system changes."""

        i = False
        def function():
            nonlocal i
            i = True

        x = self.class_(CHECK_INTERVAL, '.')
        x.on_created(function)
        # Watcher started correctly.
        self.assertTrue(x.start())
        # Watcher already started.
        self.assertFalse(x.start())

        create_file('new.file')

        # Wait for check!
        while not i:
            pass

        i = False
        create_file('new.file2')

        # Wait for another check!
        while not i:
            pass

        self.assertTrue(x.is_alive)
        # Watcher stopped correctly.
        self.assertTrue(x.stop())
        self.assertFalse(x.is_alive)
        # Watcher already stopped.
        self.assertFalse(x.stop())


class TestSimpleWatcher(BaseTest):
    """A SimpleWatcher"""

    class_ = SimpleWatcher
    kwargs = {
        'path': '.',
        'target': lambda: True
    }

    def test_callable(self):
        """Should run a callable when a file system changed."""

        i = 0
        def function(a, b):
            nonlocal i
            i = i + a + b

        x = self.class_(CHECK_INTERVAL, '.', function, [1], {'b': 1})
        create_file('new.file')
        x.check()
        self.assertEqual(2, i)

    def test_thread(self):
        """Can start a new thread to check a file system changes."""

        i = False
        def function():
            nonlocal i
            i = True

        x = self.class_(CHECK_INTERVAL, '.', function)
        # Watcher started correctly.
        self.assertTrue(x.start())
        create_file('new.file')
        # Watcher already started.
        self.assertFalse(x.start())

        # Wait for check!
        while not i:
            pass

        i = False
        create_file('new.file2')

        # Wait for another check!
        while not i:
            pass

        self.assertTrue(x.is_alive)
        # Watcher stopped correctly.
        thread = x.check_thread
        self.assertTrue(x.stop())
        self.assertFalse(thread.is_alive())
        self.assertFalse(x.is_alive)
        # Watcher already stopped.
        self.assertFalse(x.stop())

    def test_stop_in_check(self):
        """Can stop watcher from called function."""

        def function(x):
            # In this situation stop() cannot wait unit check thread will
            # be dead, because stop() is run by the check thread!
            x.stop()

        x = self.class_(CHECK_INTERVAL, '.', function)
        x.args = (x,)
        create_file('new.file')
        x.start()

        while x.is_alive:
            pass

        self.assertFalse(x.is_alive)

    def test_is_alive(self):
        """Should set a is_alive attribute to False only if all check threads are dead"""

        thread = None
        def function(x):
            nonlocal thread
            thread = x.check_thread
            x.stop()
            time.sleep(2)

        x = self.class_(CHECK_INTERVAL, '.', function)
        x.args = (x,)
        x.start()
        create_file('new.file')

        while x.is_alive:
            pass

        self.assertFalse(thread.is_alive())


class TestManager(unittest.TestCase):
    """A Manager"""

    def setUp(self):

        # Create temporary directory with example files and change current
        # working directory to it.
        self.cwd = os.getcwd()
        self.temp_path = create_test_files()
        os.chdir(self.temp_path)

    def tearDown(self):

        # Go to previous working directory and clear temp files.
        os.chdir(self.cwd)
        shutil.rmtree(self.temp_path)

    def test_repr(self):
        print(Manager())

    def test_start_stop(self):
        """Should start() all watchers and stop() all watchers."""

        m = Manager()
        a = Watcher(CHECK_INTERVAL, '.')
        b = Watcher(CHECK_INTERVAL, '.')

        self.assertFalse(a.is_alive)
        self.assertFalse(b.is_alive)
        m.add(a)
        m.add(b)

        m.start()
        self.assertTrue(a.is_alive)
        self.assertTrue(b.is_alive)
        m.stop()
        self.assertFalse(a.is_alive)
        self.assertFalse(b.is_alive)

    def test_add(self):
        """Can add watchers."""

        m = Manager()
        a = Watcher(CHECK_INTERVAL, '.')

        self.assertTrue(m.add(a))
        self.assertIn(a, m.watchers)
        self.assertFalse(a.is_alive)

        m.start()
        self.assertTrue(a.is_alive)

        # Adding watchers to started manager.
        b = Watcher(CHECK_INTERVAL, '.')
        m.add(b)
        self.assertIn(a, m.watchers)
        self.assertFalse(b.is_alive)
        m.stop()

    def test_remove(self):
        """Can remove watchers."""

        m = Manager()
        a = Watcher(CHECK_INTERVAL, '.')
        b = Watcher(CHECK_INTERVAL, '.')
        m.add(a)
        m.add(b)

        self.assertTrue(m.remove(a))
        self.assertNotIn(a, m.watchers)

        # Removing watcher from started manager.

        m.start()
        m.remove(b)
        self.assertNotIn(b, m.watchers)
        m.stop()

        # Exceptions.

        self.assertRaises(KeyError, m.remove, Watcher(CHECK_INTERVAL, '.'))

    def test_clear(self):
        """Can remove all watchers."""

        m = Manager()
        a = Watcher(CHECK_INTERVAL, '.')
        m.add(a)
        m.clear()

        self.assertFalse(m.watchers)

    def test_thread(self):
        """Can start a new thread to check each watcher."""

        i = False
        def function():
            nonlocal i
            i = True

        m = Manager()

        a = Watcher(CHECK_INTERVAL, '.')
        a.on_created(function)
        m.add(a)

        m.start()
        for k in range(10):
            m.add(Watcher(CHECK_INTERVAL, '.'))
        create_file('new.file')

        while not i:
            pass

        m.stop()
        self.assertEqual([], [i for i in m.watchers if i.is_alive])

    def test_change_watchers_in_check(self):
        """Should handle changing watchers set during check() method."""

        m = Manager()

        def function():
            m.add(Watcher(CHECK_INTERVAL, '.'))

        x = SimpleWatcher(CHECK_INTERVAL, '.', function)
        m.add(x)
        create_file('new.file')
        m.start()
        m.stop()


# Prevent testing base class.
del BaseTest


# Benchmark

def benchmark(times=10000):
    """Benchmarks each watcher."""

    # Prepare temp directory with example files.
    cwd = os.getcwd()
    path = create_test_files()
    os.chdir(path)

    msg = 'Watching {} files in {} directories.'.format(8 * times, 2 * times)
    print(msg)

    x = timeit.timeit('Watcher(1, ".", recursive=True).check()',
                      setup='from watchers import Watcher', number=times)

    sample = round(x / (8 * times) * 1000, 3)

    print('Watcher: \t{} s. one file: {} ms.'.format(round(x, 3), sample))

    x = timeit.timeit(
        'SimpleWatcher(1, ".", target=lambda: 1, recursive=True).check()',
        setup='from watchers import SimpleWatcher', number=times)

    sample = round(x / (8 * times) * 1000, 3)
    print('SimpleWatcher: \t{} s. one file: {} ms.'.format(round(x, 3), sample))

    # Cleaning!
    shutil.rmtree(path)
    os.chdir(cwd)


if __name__ == "__main__":

    if '-b' in sys.argv or '--benchmark' in sys.argv:
        benchmark()
    else:
        unittest.main()
