"""
Testing!
"""

import os
import sys
import unittest
import shutil
import tempfile
import timeit
import time
import platform

from watchers import Watcher, SimpleWatcher


# Shortcuts.

def create_file(*path, data='hello world!'):
    """Creates new file with given data."""
    with open(os.path.join(*path), 'w') as file:
        file.write(data)


def create_dir(*path):
    """Creates new directory."""
    os.mkdir(os.path.join(*path))


def delete_file(*path):
    """Removes file."""
    os.remove(os.path.join(*path))


def delete_dir(*path):
    """Removes directory."""
    shutil.rmtree(os.path.join(*path))


def modify_file(*path):
    """Modifies file data - appends 'hello'."""
    with open(os.path.join(*path), 'a') as file:
        file.write('hello')


def absolute_paths(*paths):
    """Returns paths converted to absolute paths."""
    return [os.path.abspath(i) for i in paths]


def create_test_files():
    """Returns path to temporary directory with example files used during
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
    """Base test class."""

    class_ = None
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

    def test(self):
        """Should detects changes in a file system."""

        x = self.class_(**self.kwargs)

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

        x = self.class_(recursive=True, **self.kwargs)

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

        x = self.class_(filter=lambda path: path.endswith('.txt'),
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

        x = self.class_(recursive=True,
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

        x = self.class_(**self.kwargs)

        # File permissions.

        os.chmod('a.txt', 0o777)
        self.assertTrue(x.check())

        # Directory permissions.

        os.chmod('x', 0o777)
        self.assertTrue(x.check())

    def test_recreate(self):
        """Should detects files and dirs recreations."""

        x = self.class_(**self.kwargs)
        y = self.class_(recursive=True, **self.kwargs)

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

        x = self.class_(**self.kwargs)
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


class TestWatcher(BaseTest):
    """A Watcher"""

    class_ = Watcher
    kwargs = {
        'path': '.'
    }

    def test_override_events(self):
        """Should run overridden event methods with correct arguments."""

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

        x = CustomWatcher('.')

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
        """Should run event if file created."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_created(test, 1, b=1)
        create_file('new.file')
        x.check()
        self.assertEqual(2, i)

    def test_on_file_deleted(self):
        """Should run event if file deleted."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_deleted(test, 1, b=1)
        os.remove('a.py')
        x.check()
        self.assertEqual(2, i)

    def test_on_file_modified(self):
        """Should run event if file modified."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_modified(test, 1, b=1)
        modify_file('a.txt')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_created(self):
        """Should run event if directory created."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_created(test, 1, b=1)
        create_dir('new_dir')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_deleted(self):
        """Should run event if directory deleted."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_deleted(test, 1, b=1)
        delete_dir('x')
        x.check()
        self.assertEqual(2, i)

    def test_on_dir_modified(self):
        """Should run event if directory modified."""

        i = 0
        def test(a, b):
            nonlocal i
            i = a + b

        x = Watcher('.')
        x.on_modified(test, 1, b=1)
        os.chmod('x', 0o777)
        x.check()
        self.assertEqual(2, i)


class TestSimpleWatcher(BaseTest):
    """A SimpleWatcher"""

    class_ = SimpleWatcher
    kwargs = {
        'path': '.',
        'target': lambda: True
    }

    def test_callable(self):
        """should run callable when file system changed."""

        i = 0
        def function(a, b):
            nonlocal i
            i = i + a + b

        x = self.class_('.', function, [1], {'b': 1})
        create_file('new.file')
        x.check()
        self.assertEqual(2, i)

    def test_thread(self):

        i = False
        def function():
            nonlocal i
            i = True

        x = self.class_('.', function)
        # Watcher started correctly.
        self.assertTrue(x.start())
        create_file('new.file')
        # Watcher already started.
        self.assertFalse(x.start())

        # Wait for check!
        while not i:
            pass

        self.assertFalse(x.is_stopped)
        # Watcher stopped correctly.
        self.assertTrue(x.stop())
        self.assertTrue(x.is_stopped)
        # Watcher already stopped.
        self.assertFalse(x.stop())

# Prevent testing base class.
del BaseTest


# Benchmark

def benchmark(times=1000):
    """Benchmarks each watcher."""

    # Prepare temp directory with example files.
    cwd = os.getcwd()
    path = create_test_files()
    os.chdir(path)

    msg = 'Watching {} files in {} directories.'.format(8 * times, 2 * times)
    print(msg)

    x = timeit.timeit('Watcher(".", recursive=True).check()',
                      setup='from basicwatcher import Watcher', number=times)
    print('Watcher: \t\t{} s.'.format(round(x, 4)))

    x = timeit.timeit(
        'SimpleWatcher(".", target=lambda: 1, recursive=True).check()',
        setup='from basicwatcher import SimpleWatcher', number=times)
    print('SimpleWatcher: \t{} s.'.format(round(x, 4)))

    # Cleaning!
    shutil.rmtree(path)
    os.chdir(cwd)


if __name__ == "__main__":
    if '-b' in sys.argv or '--benchmark' in sys.argv:
        benchmark()