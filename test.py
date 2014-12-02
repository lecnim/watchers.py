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
import pytest

import watchers
from watchers import Watcher, Event, PYTHON32, DirectoryPolling, FilePolling, FileWatcher, SimpleWatcher, Manager, DELETED, CREATED, MODIFIED, ItemPoller, Directory, STATUS_CREATED, STATUS_DELETED, STATUS_MODIFIED

# For faster testing.
CHECK_INTERVAL = 0.25

SYSTEM_WINDOWS = True if platform.system().lower() == 'Windows' else False

# Shortcuts.

def create_file(path, data='hello world!'):
    """Creates a new file that contains given data."""

    with open(os.path.join(*path.split('/')), 'w') as f:
        f.write(data)


def create_dir(path):
    """Creates a new directory."""
    os.mkdir(os.path.join(*path.split('/')))


def delete_file(path):
    """Removes a file."""
    os.remove(os.path.join(*path.split('/')))


def delete_dir(path):
    """Removes a directory."""
    shutil.rmtree(os.path.join(*path.split('/')))


def modify_file(path, data='update'):
    """Modifies a file data - appends 'hello'."""
    with open(os.path.join(*path.split('/')), 'a') as file:
        file.write(data)





def absolute_paths(*paths):
    """Returns items_paths converted to absolute items_paths."""
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


# Fixtures

@pytest.fixture()
def tmp_dir(request):

    cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)

    def fin():
        os.chdir(cwd)
        shutil.rmtree(tmp)

    request.addfinalizer(fin)


@pytest.fixture()
def file_item(request):

    with open('dog.txt', 'w') as f:
        f.write('wow')
    return ItemPoller('dog.txt')


@pytest.fixture()
def dir_item(request):

    os.mkdir('dog')
    with open(os.path.join('dog', 'dog.txt'), 'w') as f:
        f.write('wow')
    os.mkdir(os.path.join('dog', 'dir'))

    return ItemPoller('dog')

@pytest.fixture(params=['file', 'dir'])
def item(request):

    with open('file', 'w') as f:
        f.write('wow')
    os.mkdir('dir')

    return ItemPoller(request.param)

@pytest.fixture()
def test_dir():

    # dog.txt
    # dir/cat.txt
    # dir/dog.txt
    # dir/dir/dog.txt

    # file
    # dir/file.txt
    # dir/file


    with open('dog.txt', 'w') as f:
        f.write('wow')

    os.mkdir('dir')
    os.mkdir(os.path.join('dir', 'dir'))

    with open(os.path.join('dir', 'cat.txt'), 'w') as f:
        f.write('meow')
    with open(os.path.join('dir', 'dog.txt'), 'w') as f:
        f.write('wow')
    with open(os.path.join('dir', 'dir', 'dog.txt'), 'w') as f:
        f.write('wow')

# Item tests:

@pytest.mark.usefixtures("tmp_dir")
class TestPathPolling:

    def test_repr(self, item):
        print(item)

    def test_path_not_found(self):

        if PYTHON32:
            e = OSError
        else:
            e = FileNotFoundError

        with pytest.raises(e):
            ItemPoller('not_found')

    def test_move(self, item):

        os.mkdir('x')
        shutil.move(item.path, 'x')

        assert item.poll().status == STATUS_DELETED

    def test_rename(self, item):
        """User renames an item and poll()"""

        os.rename(item.path, 'b')
        assert item.poll().status == STATUS_DELETED

        os.rename('b', item.path)
        assert item.poll().status == STATUS_CREATED

        os.rename(item.path, 'b')
        time.sleep(0.5)
        os.rename('b', item.path)
        assert item.poll() is None

    def test_cwd(self, item):
        """User modifies an item, change current working directory and poll()"""

        os.mkdir('new_dir')
        os.chmod(item.path, 0o777)
        os.chdir('new_dir')

        assert item.poll().status == STATUS_MODIFIED

    def test_permissions(self, item):
        """User changes an item permissions and poll()"""

        if SYSTEM_WINDOWS:
            # File with read-only attribute.
            os.chmod(item.path, stat.S_IREAD)
            assert item.poll().status == STATUS_MODIFIED
            # Prevent PermissionError!
            os.chmod(item.path, stat.S_IWRITE)

        else:
            os.chmod(item.path, 0o777)
            assert item.poll().status == STATUS_MODIFIED



@pytest.mark.usefixtures("tmp_dir")
class TestFilePathPolling:

    def test_poll_modify(self, file_item):

        with open(file_item.path, 'a') as f:
            f.write('edited')

        e = file_item.poll()

        assert isinstance(e, Event)
        assert e.status == STATUS_MODIFIED
        assert e.path == 'dog.txt'
        assert e.is_file is True
        assert file_item.poll() is None

    def test_poll_create(self, file_item):

        os.remove(file_item.path)
        file_item.poll()

        with open(file_item.path, 'w') as f:
            f.write('created')

        e = file_item.poll()

        assert isinstance(e, Event)
        assert e.status == STATUS_CREATED
        assert e.path == 'dog.txt'
        assert e.is_file is True
        assert file_item.poll() is None

    def test_poll_delete(self, file_item):

        os.remove(file_item.path)

        e = file_item.poll()

        assert isinstance(e, Event)
        assert e.status == STATUS_DELETED
        assert e.path == 'dog.txt'
        assert e.is_file is True
        assert file_item.poll() is None

    def test_recreate(self, file_item):

        # Recreating same file - mod time should be different.

        os.remove(file_item.path)
        time.sleep(0.5)
        with open(file_item.path, 'w') as f:
            f.write('wow')

        assert file_item.poll().status == STATUS_MODIFIED

        # Recreating same file with different content - size file is used.

        os.remove(file_item.path)
        with open(file_item.path, 'w') as f:
            f.write('meow')

        assert file_item.poll().status == STATUS_MODIFIED

    def test_swap_with_directory(self, file_item):

        os.remove(file_item.path)
        os.mkdir(file_item.path)

        assert file_item.poll().status == STATUS_DELETED

    # Events

    def test_on_create(self, file_item):

        def on_create(e):
            assert isinstance(e, Event)
            assert e == Event(STATUS_CREATED, file_item.path, is_file=True)
            file_item.called = True
        file_item.on_created = on_create

        os.remove(file_item.path)
        file_item.poll()
        with open(file_item.path, 'w') as f:
            f.write('created')
        file_item.poll()

        assert file_item.called

    def test_on_modify(self, file_item):

        def on_modify(e):
            assert isinstance(e, Event)
            assert e == Event(STATUS_MODIFIED, file_item.path, is_file=True)
            file_item.called = True
        file_item.on_modified = on_modify

        with open(file_item.path, 'a') as f:
            f.write('edited')
        file_item.poll()

        assert file_item.called

    def test_on_delete(self, file_item):

        def on_delete(e):
            assert isinstance(e, Event)
            assert e == Event(STATUS_DELETED, file_item.path, is_file=True)
            file_item.called = True
        file_item.on_deleted = on_delete

        os.remove(file_item.path)
        file_item.poll()

        assert file_item.called



@pytest.mark.usefixtures("tmp_dir")
class TestDirectoryPathPolling:

    def test_poll_create(self, dir_item):
        """User deletes a directory, recreates it and poll()"""

        shutil.rmtree(dir_item.path)
        dir_item.poll()
        os.mkdir(dir_item.path)

        e = dir_item.poll()

        assert isinstance(e, Event)
        assert e.status == STATUS_CREATED
        assert e.path == 'dog'
        assert e.is_file is False
        assert dir_item.poll() is None

    def test_poll_delete(self, dir_item):
        """User deletes a directory and poll()"""

        shutil.rmtree(dir_item.path)

        e = dir_item.poll()

        assert isinstance(e, Event)
        assert e.status == STATUS_DELETED
        assert e.path == 'dog'
        assert e.is_file is False
        assert dir_item.poll() is None

    def test_recreate(self, dir_item):
        """User deletes a directory and then creates it again but with
        different content and poll()"""

        # Recreating same directory but with different content.

        shutil.rmtree(dir_item.path)
        time.sleep(0.2)
        os.mkdir(dir_item.path)
        with open(os.path.join(dir_item.path, 'test.txt'), 'w'):
            pass

        e = dir_item.poll()
        assert e.status == STATUS_MODIFIED

        # Recreating with sames files - mod time should be different,
        # but files structure does not change.

        time.sleep(0.2)
        shutil.rmtree(dir_item.path)
        os.mkdir(dir_item.path)
        with open(os.path.join(dir_item.path, 'test.txt'), 'w'):
            pass

        assert dir_item.poll() is None

    def test_swap_with_file(self, dir_item):
        """User deletes a directory and creates a file instead and poll()"""

        shutil.rmtree(dir_item.path)
        open(os.path.join(dir_item.path), 'w').close()

        assert dir_item.poll().status is STATUS_DELETED

    # Changes in directory content.

    def test_create_directory_in_content(self, dir_item):
        """User creates a new directory in directory and poll()"""

        os.mkdir(os.path.join(dir_item.path, 'new_dir'))

        assert dir_item.poll().status == STATUS_MODIFIED
        assert dir_item.poll() is None

    def test_create_file_in_content(self, dir_item):
        """User creates a new file in directory and poll()"""

        with open(os.path.join(dir_item.path, 'cat.txt'), 'w'):
            pass

        assert dir_item.poll().status == STATUS_MODIFIED
        assert dir_item.poll() is None

    def test_modify_file_in_content(self, dir_item):
        """User modifies a file from directory and poll()"""

        time.sleep(0.2)
        with open(os.path.join(dir_item.path, 'dog.txt'), 'a') as f:
            f.write('update')
        assert dir_item.poll() is None

    def test_delete_file_from_content(self, dir_item):
        os.remove(os.path.join(dir_item.path, 'dog.txt'))

        assert dir_item.poll().status == STATUS_MODIFIED
        assert dir_item.poll() is None

    def test_delete_directory_from_content(self, dir_item):
        os.rmdir(os.path.join(dir_item.path, 'dir'))

        assert dir_item.poll().status == STATUS_MODIFIED
        assert dir_item.poll() is None

    def test_overwrite_file_in_content(self, dir_item):

        # Treat as a modify of file, so nothing changed.

        time.sleep(0.2)

        os.remove(os.path.join(dir_item.path, 'dog.txt'))
        with open(os.path.join(dir_item.path, 'dog.txt'), 'w') as f:
            f.write('wow wow wow')

        assert dir_item.poll() is None

    def test_overwrite_directory_in_content(self, dir_item):

        # Treat as modify of directory, so nothing changed.

        time.sleep(0.2)
        os.rmdir(os.path.join(dir_item.path, 'dir'))
        os.mkdir(os.path.join(dir_item.path, 'dir'))
        with open(os.path.join(dir_item.path, 'dir', 'dog.txt'), 'w') as f:
            f.write('wow')

        assert dir_item.poll() is None

    def test_rename_file_in_content(self, dir_item):

        os.rename(os.path.join(dir_item.path, 'dog.txt'), 'renamed_dog.txt')
        assert dir_item.poll().status == STATUS_MODIFIED

    def test_rename_directory_in_content(self, dir_item):

        os.rename(os.path.join(dir_item.path, 'dir'), 'renamed_dir')
        assert dir_item.poll().status == STATUS_MODIFIED

    def test_swap_content_items(self, dir_item):
        """Remove file from directory and create new directory instead"""

        os.remove(os.path.join(dir_item.path, 'dog.txt'))
        os.mkdir(os.path.join(dir_item.path, 'dog.txt'))

        assert dir_item.poll().status == STATUS_MODIFIED

    def test_symlink_to_directory(self, dir_item):

        p = os.path.abspath('new_dir')
        os.mkdir(p)

        os.chdir(dir_item.path)
        os.symlink(p, 'link')

        assert dir_item.poll().status == STATUS_MODIFIED

    def test_symlink_to_file(self, dir_item):

        p = os.path.abspath('new_file')
        with open(p, 'w') as f:
            f.write('test')

        os.chdir(dir_item.path)
        os.symlink(p, 'link')

        assert dir_item.poll().status == STATUS_MODIFIED

    # TODO:

    def test_delete_symlink_from_content(self):
        pass
        # TODO

    # TODO: Events




@pytest.mark.usefixtures("tmp_dir", "test_dir")
class TestDirectoryPolling:

    def test_repr(self):
        assert repr(DirectoryPolling('.'))

    def test_init(self):

        p = DirectoryPolling('.')
        paths = [i.path for i in p.items]

        assert '.' in paths
        assert os.path.join('.', 'dog.txt') in paths
        assert os.path.join('.', 'dir') in paths

    def test_filter(self):

        def ignore(path):
            if path.endswith('dog.txt'):
                return False
            return True

        p = DirectoryPolling('.', filter=ignore)
        paths = [i for i in p._walk()]

        assert not os.path.join('.', 'dog.txt') in paths
        assert os.path.join('.', 'dir') in paths
        assert os.path.join('.') in paths
        assert len(paths) == 2

    # Create

    def test_create_root(self):
        # TODO
        pass

    def test_create_items(self):

        p = DirectoryPolling('.')
        with open('new_file', 'w'):
            pass
        os.mkdir('new_dir')

        e = p.poll()
        assert len(e) == 3
        assert Event(STATUS_MODIFIED, '.',
                     is_file=False) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'new_file'),
                     is_file=True) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'new_dir'),
                     is_file=False) in e

        # TODO: idea?
        assert e == {
            Event(STATUS_MODIFIED, '.', is_file=False),
            Event(STATUS_CREATED, os.path.join('.', 'new_file'), is_file=True),
            Event(STATUS_CREATED, os.path.join('.', 'new_dir'), is_file=False)
        }

    def test_create_deep_items(self):

        p = DirectoryPolling('.')
        with open(os.path.join('dir', 'new_file'), 'w'):
            pass
        os.mkdir(os.path.join('dir', 'new_dir'))

        assert not p.poll()

    # Delete

    def test_delete_root(self):

        p = DirectoryPolling('dir')
        shutil.rmtree('dir')

        e = p.poll()

        assert Event(STATUS_DELETED, os.path.join('dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('dir', 'cat.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, 'dir', is_file=False) in e
        assert Event(STATUS_DELETED, 'dir', is_file=False) in e
        assert len(e) == 5

    def test_delete_items(self):

        p = DirectoryPolling('.')
        os.remove('dog.txt')
        shutil.rmtree('dir')

        e = p.poll()
        assert len(e) == 3
        assert Event(STATUS_MODIFIED, '.',
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir'),
                     is_file=False) in e

    def test_delete_deep_items(self):

        p = DirectoryPolling('.')
        os.remove(os.path.join('dir', 'dog.txt'))
        shutil.rmtree(os.path.join('dir', 'dir'))

        assert not p.poll()

    # Permissions

    def test_change_item_permissions(self):

        p = DirectoryPolling('.')

        os.chmod('dog.txt', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('dog.txt', 0o777)
        os.chmod('dir', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('dir', 0o777)

        e = p.poll()
        assert len(e) == 2
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir'),
                     is_file=False) in e

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('dog.txt', stat.S_IWRITE)
            os.chmod('dir', stat.S_IWRITE)

    def test_change_root_permissions(self):

        p = DirectoryPolling('.')
        os.chmod('.', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('.', 0o777)

        e = p.poll()
        assert len(e) == 1
        assert Event(STATUS_MODIFIED, '.', is_file=False) in e

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('.', stat.S_IWRITE)

    # Rename

    def test_rename_file(self):

        p = DirectoryPolling('.')
        os.rename('dog.txt', 'renamed')

        e = p.poll()
        assert len(e) == 3
        assert Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'renamed'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, '.', is_file=False) in e

    def test_rename_directory(self):

        p = DirectoryPolling('.')
        os.rename('dir', 'renamed')

        e = p.poll()
        assert len(e) == 3
        assert Event(STATUS_DELETED, os.path.join('.', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_CREATED,  os.path.join('.', 'renamed'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, '.', is_file=False) in e

    def test_rename_root(self):
        pass
        # TODO

    # Modify

    def test_modify_file(self):

        p = DirectoryPolling('.')
        with open('dog.txt', 'a') as f:
            f.write('update')

        e = p.poll()
        assert len(e) == 1
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dog.txt'),
                     is_file=True) in e

    def test_modify_deep_file(self):

        p = DirectoryPolling('.')
        with open(os.path.join('dir', 'dog.txt'), 'a') as f:
            f.write('update')

        assert not p.poll()

    # Events

    def test_on_create(self):

        def on_created(e):
            assert e == Event(STATUS_CREATED, os.path.join('.', 'dog.txt'),
                              is_file=True)
            p.called = True

        p = DirectoryPolling('.')
        p.on_created = on_created

        os.remove('dog.txt')
        p.poll()
        create_file('dog.txt')
        p.poll()

        assert p.called

    def test_on_modify(self):

        def on_modified(e):
            assert e == Event(STATUS_MODIFIED, os.path.join('.', 'dog.txt'),
                              is_file=True)
            p.called = True

        p = DirectoryPolling('.')
        p.on_modified = on_modified

        with open('dog.txt', 'a') as f:
            f.write('updated')
        p.poll()

        assert p.called

    def test_on_delete(self):

        def on_deleted(e):
            assert e == Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
                              is_file=True)
            p.called = True

        p = DirectoryPolling('.')
        p.on_deleted = on_deleted

        os.remove('dog.txt')
        p.poll()

        assert p.called


@pytest.mark.usefixtures("tmp_dir", "test_dir")
class TestRecursiveDirectoryPolling:


    # dog.txt
    # dir/cat.txt
    # dir/dog.txt
    # dir/dir/dog.txt

    def test_filter(self):

        def ignore(path):
            if path.endswith('dog.txt'):
                return True
            return False

        p = DirectoryPolling('.', filter=ignore, recursive=True)
        paths = [i for i in p._walk()]

        assert os.path.join('.', 'dog.txt') in paths
        assert os.path.join('.', 'dir', 'dog.txt') in paths
        assert os.path.join('.', 'dir', 'dir', 'dog.txt') in paths
        assert len(paths) == 3

    # Create

    def test_create_root(self):

        p = DirectoryPolling('dir', recursive=True)
        shutil.rmtree('dir')
        p.poll()

        os.mkdir('dir')
        create_file(os.path.join('dir', 'new_file'))

        e = p.poll()
        assert len(e) == 3

        assert Event(STATUS_CREATED, 'dir', is_file=False) in e
        assert Event(STATUS_CREATED, os.path.join('dir', 'new_file'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, 'dir', is_file=False) in e


    def test_create_items(self):

        p = DirectoryPolling('.', recursive=True)
        create_file('new_file')
        os.mkdir('new_dir')

        e = p.poll()
        assert len(e) == 3

        assert Event(STATUS_CREATED, os.path.join('.', 'new_file'),
                     is_file=True) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'new_dir'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, '.', is_file=False) in e

        assert not p.poll()

    def test_create_deep_items(self):

        p = DirectoryPolling('.', recursive=True)

        os.chdir('dir')
        create_file('new_file')
        os.mkdir('new_dir')
        create_file(os.path.join('new_dir', 'new_file'))

        e = p.poll()
        assert len(e) == 5

        assert Event(STATUS_CREATED, os.path.join('.', 'dir', 'new_file'),
                     is_file=True) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'dir', 'new_dir'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_CREATED, os.path.join('.', 'dir', 'new_dir', 'new_file'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir', 'new_dir'),
                     is_file=False) in e

    # Delete

    def test_delete_root(self):

        p = DirectoryPolling('dir', recursive=True)
        shutil.rmtree('dir')

        e = p.poll()
        assert len(e) == 7

        # dir/dir
        assert Event(STATUS_DELETED, os.path.join('dir', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('dir', 'dir'),
                     is_file=False) in e
        # dir
        assert Event(STATUS_DELETED, os.path.join('dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('dir', 'cat.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, 'dir', is_file=False) in e
        # root
        assert Event(STATUS_DELETED, 'dir', is_file=False) in e

    def test_delete_items(self):

        p = DirectoryPolling('.', recursive=True)
        os.remove('dog.txt')
        shutil.rmtree('dir')

        e = p.poll()
        assert len(e) == 9

        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'cat.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, '.', is_file=False) in e

    def test_delete_deep_items(self):

        p = DirectoryPolling('.', recursive=True)
        os.remove(os.path.join('dir', 'dog.txt'))
        shutil.rmtree(os.path.join('dir', 'dir'))

        e = p.poll()
        assert len(e) == 5

        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_DELETED, os.path.join('.', 'dir', 'dir'),
                     is_file=False) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir'),
                     is_file=False) in e







class BaseTest:
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

    # def test_polll(self):
    #
    #     x = self.class_(CHECK_INTERVAL, **self.kwargs)
    #
    #     create_file('new.txt')
    #
    #     result = [(i.status, i.path) for i in x.poll()]
    #
    #     self.assertIn((CREATED, os.path.abspath('new.txt')), result)
    #     self.assertIn((MODIFIED, '.'), result)
    #     self.assertFalse(1)


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
        """Can use a filter to ignore items_paths."""

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
        self.assertEqual(4, x.interval)

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


class TesWatcher:
    """A Watcher"""

    class_ = Watcher
    kwargs = {
        'path': '.'
    }

    # TODO:

    def test_poll(self):

        x = Watcher(CHECK_INTERVAL, '.', recursive=True)

        # File created.

        create_file('new.txt')

        i = x.poll()
        self.assertEqual(len(i), 1)
        self.assertEqual(CREATED, i[0].status)
        self.assertEqual(os.path.abspath('new.txt'), i[0].path)

        # File removed.

        delete_file('new.txt')

        i = x.poll()
        self.assertEqual(len(i), 1)
        self.assertEqual(DELETED, i[0].status)
        self.assertEqual(os.path.abspath('new.txt'), i[0].path)

        # File modified.

        modify_file('a.txt')

        i = x.poll()
        self.assertEqual(len(i), 1)
        self.assertEqual(MODIFIED, i[0].status)
        self.assertEqual(os.path.abspath('a.txt'), i[0].path)

        # Directory created.

        create_dir('new_dir')

        i = x.poll()
        self.assertEqual(len(i), 1)
        self.assertEqual(CREATED, i[0].status)
        self.assertEqual(os.path.abspath('new_dir'), i[0].path)

        # Directory deleted.

        delete_dir('new_dir')

        i = x.poll()
        self.assertEqual(len(i), 1)
        self.assertEqual(DELETED, i[0].status)
        self.assertEqual(os.path.abspath('new_dir'), i[0].path)


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

        i = False

        class CustomWatcher(Watcher):
            def on_created(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
        create_file('new.file')
        x.check()
        self.assertTrue(i)

    def test_on_file_deleted(self):
        """Should run an event if a file deleted."""

        i = False

        class CustomWatcher(Watcher):
            def on_deleted(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
        os.remove('a.py')
        x.check()
        self.assertTrue(i)

    def test_on_file_modified(self):
        """Should run an event if a file modified."""

        i = False

        class CustomWatcher(Watcher):
            def on_modified(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
        modify_file('a.txt')
        x.check()
        self.assertTrue(i)

    def test_on_dir_created(self):
        """Should run an event if a directory created."""

        i = False

        class CustomWatcher(Watcher):
            def on_created(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
        create_dir('new_dir')
        x.check()
        self.assertTrue(i)

    def test_on_dir_deleted(self):
        """Should run an event if a directory deleted."""

        i = False

        class CustomWatcher(Watcher):
            def on_deleted(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
        delete_dir('x')
        x.check()
        self.assertTrue(i)

    def test_on_dir_modified(self):
        """Should run an event if a directory was modified."""

        i = False

        class CustomWatcher(Watcher):
            def on_modified(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')

        # Windows supports read-only flag only!
        if platform.system() == 'Windows':
            os.chmod('x', stat.S_IREAD)
            x.check()
            # Prevent PermissionError!
            os.chmod('x', stat.S_IWRITE)
        else:
            os.chmod('x', 0o777)
            x.check()
        self.assertTrue(i)

    def test_thread(self):
        """Can start a new thread to check a file system changes."""

        i = False

        class CustomWatcher(Watcher):
            def on_created(self, item):
                nonlocal i
                i = True

        x = CustomWatcher(CHECK_INTERVAL, '.')
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


class TesSimpleWatcher:
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


class TesManager:
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

        class CustomWatcher(Watcher):
            def on_created(self, item):
                nonlocal i
                i = True

        m = Manager()
        a = CustomWatcher(CHECK_INTERVAL, '.')
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

def benchmark(times=1000):
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
