"""
Testing!
"""

import os
import stat
import sys
import shutil
import tempfile
import timeit
import time
import platform
import pytest
import threading
import contextlib

from watchers import *

# For faster testing.
CHECK_INTERVAL = 0.25
SYSTEM_WINDOWS = True if platform.system().lower() == 'windows' else False

# Shortcuts.

def create_file(path, data='hello world!'):
    """Creates a new file that contains given data."""
    with open(path, 'w') as f:
        f.write(data)

def modify_file(path, data='update'):
    with open(path, 'a') as f:
        f.write(data)

def delete(item):
    if os.path.isfile(item.path):
        os.remove(item.path)
    else:
        shutil.rmtree(item.path)

def create(item):
    if item.is_file:
        create_file(item.path, data='')
    else:
        os.mkdir(item.path)


# Fixtures

def pytest_generate_tests(metafunc):

    if metafunc.cls.__name__ == 'TestPathPolling':
        # Called once per each test function
        params = metafunc.cls.params.get(metafunc.function.__name__)
        if params:
            metafunc.parametrize(
                ['item', 'event'],
                argvalues=[(path, (path, result)) for path, result in params],
                ids=[path for path, result in params],
                indirect=True)

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
def sample_files():

    create_file('file', data='data')
    os.mkdir('dir')
    os.mkdir(os.path.join('dir', 'dir'))
    create_file(os.path.join('dir', 'file'), data='data')
    create_file(os.path.join('dir', 'dir', 'file'), data='data')

@pytest.fixture()
def item(request):
    return PathPolling(request.param)

@pytest.fixture()
def event(request):

    path, status = request.param

    if status is None:
        return None
    return Event(status, path, os.path.isfile(path))


# Tests

@pytest.mark.usefixtures("tmp_dir", "sample_files")
class TestPathPolling:

    def test_repr(self):
        assert repr(PathPolling('.')) == "<PathPolling: path=., is_file=False>"

    def test_path_not_found(self):

        if PYTHON32:
            e = OSError
        else:
            e = FileNotFoundError

        with pytest.raises(e):
            PathPolling('not_found')

    # Temporary directory tree:
    #   ./file
    #   ./dir
    #   ./dir/file
    #   ./dir/dir

    params = {

        # test_method:
        #   [(path to item, expected EVENT_TYPE)]

        'test_move':
            [('file', EVENT_TYPE_DELETED), ('dir', EVENT_TYPE_DELETED)],
        'test_rename':
            [('file', EVENT_TYPE_DELETED), ('dir', EVENT_TYPE_DELETED)],
        'test_cwd':
            [('file', EVENT_TYPE_MODIFIED), ('dir', EVENT_TYPE_MODIFIED)],
        'test_permissions':
            [('file', EVENT_TYPE_MODIFIED), ('dir', EVENT_TYPE_MODIFIED)],
        'test_modify_file':
            [('file', EVENT_TYPE_MODIFIED)],
        'test_create':
            [('file', EVENT_TYPE_CREATED), ('dir', EVENT_TYPE_CREATED)],
        'test_delete':
            [('file', EVENT_TYPE_DELETED), ('dir', EVENT_TYPE_DELETED)],
        'test_recreate_file':
            [('file', EVENT_TYPE_MODIFIED)],
        'test_swap_file_with_directory':
            [('file', EVENT_TYPE_DELETED)],
        'test_recreate_directory':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_swap_directory_with_file':
            [('dir', EVENT_TYPE_DELETED)],

        'test_on_created':
            [('file', EVENT_TYPE_CREATED), ('dir', EVENT_TYPE_CREATED)],
        'test_on_deleted':
            [('file', EVENT_TYPE_DELETED), ('dir', EVENT_TYPE_DELETED)],
        'test_on_modified':
            [('file', EVENT_TYPE_MODIFIED), ('dir', EVENT_TYPE_MODIFIED)],

        'test_create_file_in_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_create_directory_in_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_modify_file_in_content':
            [('dir', None)],
        'test_delete_file_from_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_delete_directory_from_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_overwrite_file_in_content':
            [('dir', None)],
        'test_overwrite_directory_in_content':
            [('dir', None)],
        'test_rename_file_in_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_rename_directory_in_content':
            [('dir', EVENT_TYPE_MODIFIED)],
        'test_swap_content_items':
            [('dir', EVENT_TYPE_MODIFIED)],
    }

    # Test detection of changes.

    def test_create(self, item, event):

        delete(item)
        item.poll()
        create(item)

        assert item.poll() == event

    def test_delete(self, item, event):

        delete(item)
        assert item.poll() == event

    def test_move(self, item, event):

        os.mkdir('x')
        shutil.move(item.path, 'x')

        assert item.poll() == event

    def test_modify_file(self, item, event):

        with open(item.path, 'a') as f:
            f.write('edited')
        assert item.poll() == event

    def test_recreate_file(self, item, event):

        # Recreating same file - mod time should be different.

        delete(item)
        time.sleep(0.2)
        create_file(item.path, data='data')

        assert item.poll() == event

        # Recreating same file with different content - size file is used.

        delete(item)
        create_file(item.path, data='different content')

        assert item.poll() == event

    def test_recreate_directory(self, item, event):
        """User deletes a directory and then creates it again but with
        different content and poll()"""

        # Recreating with sames files - mod time should be different,
        # but files structure does not change.

        delete(item)
        time.sleep(0.2)

        create(item)
        create_file(os.path.join(item.path, 'file'), data='data')
        os.mkdir(os.path.join(item.path, 'dir'))

        assert item.poll() is None

        # Recreating same directory but with different content.

        time.sleep(0.2)
        delete(item)
        create(item)

        assert item.poll() == event

    def test_swap_file_with_directory(self, item, event):

        delete(item)
        os.mkdir(item.path)

        assert item.poll() == event

    def test_swap_directory_with_file(self, item, event):
        """User deletes a directory and creates a file instead and poll()"""

        delete(item)
        create_file(item.path)

        assert item.poll() == event

    def test_rename(self, item, event):
        """User renames an item and poll()"""

        os.rename(item.path, 'b')
        assert item.poll() == event

        os.rename('b', item.path)
        item.poll()

        os.rename(item.path, 'b')
        time.sleep(0.5)
        os.rename('b', item.path)
        assert item.poll() is None

    def test_cwd(self, item, event):
        """User modifies an item, change current working directory and poll()"""

        os.chmod(item.path, stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod(item.path, 0o777)

        os.mkdir('new_dir')
        os.chdir('new_dir')

        assert item.poll() == event

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod(item.full_path, stat.S_IWRITE)

    def test_permissions(self, item, event):
        """User changes item permissions and poll()"""

        if SYSTEM_WINDOWS:
            # File with read-only attribute.
            os.chmod(item.path, stat.S_IREAD)
            assert item.poll() == event
            # Prevent PermissionError!
            os.chmod(item.path, stat.S_IWRITE)
        else:
            os.chmod(item.path, 0o777)
            assert item.poll() == event

    # Changes in directory content.

    def test_create_file_in_content(self, item, event):
        """User creates a new file in directory and poll()"""

        create_file(os.path.join(item.path, 'new_file'))
        assert item.poll() == event

    def test_create_directory_in_content(self, item, event):
        """User creates a new directory in directory and poll()"""

        os.mkdir(os.path.join(item.path, 'new_dir'))
        assert item.poll() == event

    def test_modify_file_in_content(self, item, event):
        """User modifies a file from directory and poll()"""

        time.sleep(0.2)
        modify_file(os.path.join(item.path, 'file'))

        assert item.poll() == event

    def test_delete_file_from_content(self, item, event):

        os.remove(os.path.join(item.path, 'file'))
        assert item.poll() == event

    def test_delete_directory_from_content(self, item, event):

        shutil.rmtree(os.path.join(item.path, 'dir'))
        assert item.poll() == event

    def test_overwrite_file_in_content(self, item, event):

        # Treat as a modify of file, so nothing changed.

        time.sleep(0.2)

        os.remove(os.path.join(item.path, 'file'))
        create_file(os.path.join(item.path, 'file'), data='wow wow wow')

        assert item.poll() == event

    def test_overwrite_directory_in_content(self, item, event):

        # Treat as modify of directory, so nothing changed.

        time.sleep(0.2)

        shutil.rmtree(os.path.join(item.path, 'dir'))
        os.mkdir(os.path.join(item.path, 'dir'))
        create_file(os.path.join(item.path, 'dir', 'new_file'))

        assert item.poll() == event

    def test_rename_file_in_content(self, item, event):

        os.rename(os.path.join(item.path, 'file'), 'renamed_file.txt')
        assert item.poll() == event

    def test_rename_directory_in_content(self, item, event):

        os.rename(os.path.join(item.path, 'dir'), 'renamed_dir')
        assert item.poll() == event

    def test_swap_content_items(self, item, event):
        """Remove file from directory and create new directory instead"""

        os.remove(os.path.join(item.path, 'file'))
        os.mkdir(os.path.join(item.path, 'file'))

        assert item.poll() == event

    # TODO: SYMLINKS

    # def test_symlink_not_found_in_content(self, item, event):
    #
    #     p = os.path.abspath('new_dir')
    #     os.mkdir(p)
    #     os.chdir(item.path)
    #     os.symlink(p, 'link')
    #
    #     item.poll()
    #     os.rmdir(p)
    #     assert item.poll() == event

    # def test_create_symlink_in_content(self, item, event):
    #
    #     p = os.path.abspath('new_dir')
    #     os.mkdir(p)
    #     os.chdir(item.path)
    #     os.symlink(p, 'link')
    #
    #     assert item.poll() == event
    #
    #     p = os.path.abspath('new_file')
    #     create_file(p)
    #     os.chdir(dir_item.path)
    #     os.symlink(p, 'link')

    # Events

    def test_on_created(self, item, event):

        def on_created():
            item.called = True
        item.on_created = on_created

        self.test_create(item, event)
        assert item.called

    def test_on_deleted(self, item, event):

        def on_deleted():
            item.called = True
        item.on_deleted = on_deleted

        self.test_delete(item, event)
        assert item.called

    def test_on_modified(self, item, event):

        def on_modified():
            item.called = True
        item.on_modified = on_modified

        if item.is_file:
            self.test_modify_file(item, event)
            assert item.called
        else:
            self.test_permissions(item, event)
            assert item.called


# DirectoryPolling

def create_events(*events):
    x = []
    for status, path, is_file in events:
        x.append(Event(status, path, is_file))
    return x

@pytest.mark.usefixtures("tmp_dir", "sample_files")
class TestDirectoryPolling:

    def test_repr(self):
        assert repr(DirectoryPolling('.')) == "<DirectoryPolling: path=., " \
                                              "is_recursive=False>"

    # TODO: during _walk items are deleted
    def test_walk_not_found(self):
        pass

    def test_path_not_found(self):

        if PYTHON32:
            e = OSError
        else:
            e = FileNotFoundError

        with pytest.raises(e):
            DirectoryPolling('not_found')

    # TODO: More filter tests
    # TODO: Filter directory, what about it content?
    def test_filter(self):

        def ignore(path):
            if path.endswith('file'):
                return False
            return True

        a = DirectoryPolling('.', filter=ignore)
        b = DirectoryPolling('.', recursive=True, filter=ignore)

        os.remove('file')
        os.remove(os.path.join('dir', 'file'))

        assert a.poll() == create_events(
            (EVENT_TYPE_MODIFIED, '.', False),
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_MODIFIED, '.', False),
            (EVENT_TYPE_MODIFIED, './dir', False)
        )

    # TODO: Test filter root dir

    # Swap

    def test_swap_items(self):

        a = DirectoryPolling('.')

        os.remove('file')
        os.mkdir('file')

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, './file', False),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )

    def test_swap_root(self):

        a = DirectoryPolling('dir')

        shutil.rmtree('dir')
        create_file('dir')

        assert a.poll() == create_events(
            (EVENT_TYPE_DELETED, 'dir', False),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False)
        )

    # Modify

    def test_modify_file(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        modify_file('file')
        modify_file('dir/dir/file')

        assert a.poll() == create_events(
            (EVENT_TYPE_MODIFIED, './file', True)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_MODIFIED, './file', True),
            (EVENT_TYPE_MODIFIED, './dir/dir/file', True)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_multiple_modify(self):

        a = DirectoryPolling('.')

        modify_file('file')
        os.chmod('file', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('file', 0o777)

        assert a.poll() == [Event(EVENT_TYPE_MODIFIED, './file', True)]

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('file', stat.S_IWRITE)

    # Create

    def test_create_root(self):

        a = DirectoryPolling('dir')
        b = DirectoryPolling('dir', recursive=True)

        shutil.rmtree('dir')
        os.mkdir('dir')
        os.chdir('dir')
        create_file('new_file')

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, 'dir/new_file', True),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False),
            (EVENT_TYPE_MODIFIED, 'dir', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, 'dir/new_file', True),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False),
            (EVENT_TYPE_DELETED, 'dir/dir/file', True),
            (EVENT_TYPE_MODIFIED, 'dir', False)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_create_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        create_file('new_file')
        os.mkdir('new_dir')
        create_file(os.path.join('new_dir', 'new_file'))

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_CREATED, './new_dir', False),
            (EVENT_TYPE_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_CREATED, './new_dir', False),
            (EVENT_TYPE_CREATED, './new_dir/new_file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_create_deep_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        os.chdir('dir')
        create_file('new_file')
        os.mkdir('new_dir')

        assert a.poll() == []
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, './dir/new_file', True),
            (EVENT_TYPE_CREATED, './dir/new_dir', False),
            (EVENT_TYPE_MODIFIED, './dir', False)
        )

    # Delete

    def test_delete_root(self):

        a = DirectoryPolling('dir')
        b = DirectoryPolling('dir', recursive=True)

        shutil.rmtree('dir')

        assert a.poll() == create_events(
            (EVENT_TYPE_DELETED, 'dir', False),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_DELETED, 'dir', False),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False),
            (EVENT_TYPE_DELETED, 'dir/dir/file', True)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_delete_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        os.remove('file')
        shutil.rmtree('dir')

        assert a.poll() == create_events(
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_DELETED, './dir', False),
            (EVENT_TYPE_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_DELETED, './dir', False),
            (EVENT_TYPE_DELETED, './dir/file', True),
            (EVENT_TYPE_DELETED, './dir/dir', False),
            (EVENT_TYPE_DELETED, './dir/dir/file', True),
            (EVENT_TYPE_MODIFIED, '.', False),
        )

        assert a.poll() == []
        assert b.poll() == []

    # Permissions

    def test_change_root_permissions(self):

        a = DirectoryPolling('.')
        os.chmod('.', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('.', 0o777)

        assert a.poll() == [Event(EVENT_TYPE_MODIFIED, '.', False)]
        assert a.poll() == []

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('.', stat.S_IWRITE)

    def test_change_item_permissions(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        if SYSTEM_WINDOWS:
            os.chmod('file', stat.S_IREAD)
            os.chmod(os.path.join('dir', 'file'), stat.S_IREAD)
        else:
            os.chmod('file', 0o777)
            os.chmod(os.path.join('dir', 'file'), 0o777)

        assert a.poll() == create_events(
            (EVENT_TYPE_MODIFIED, './file', True)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_MODIFIED, './file', True),
            (EVENT_TYPE_MODIFIED, './dir/file', True)
        )

        assert a.poll() == []
        assert b.poll() == []

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('file', stat.S_IWRITE)
            os.chmod('dir', stat.S_IWRITE)

    # Rename

    def test_rename_root(self):

        a = DirectoryPolling('dir')
        b = DirectoryPolling('dir', recursive=True)

        os.rename('dir', 'x')

        assert a.poll() == create_events(
            (EVENT_TYPE_DELETED, 'dir', False),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_DELETED, 'dir', False),
            (EVENT_TYPE_DELETED, 'dir/file', True),
            (EVENT_TYPE_DELETED, 'dir/dir', False),
            (EVENT_TYPE_DELETED, 'dir/dir/file', True)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_rename_file(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        os.rename('file', 'renamed_file')
        os.chdir('dir')
        os.rename('file', 'renamed_file')

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, './renamed_file', True),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, './renamed_file', True),
            (EVENT_TYPE_CREATED, './dir/renamed_file', True),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_DELETED, './dir/file', True),
            (EVENT_TYPE_MODIFIED, '.', False),
            (EVENT_TYPE_MODIFIED, './dir', False)
        )

        assert a.poll() == []
        assert b.poll() == []

    def test_rename_directory(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        os.rename('dir', 'renamed_dir')

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, './renamed_dir', False),
            (EVENT_TYPE_DELETED, './dir', False),
            (EVENT_TYPE_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, './renamed_dir', False),
            (EVENT_TYPE_CREATED, './renamed_dir/file', True),
            (EVENT_TYPE_CREATED, './renamed_dir/dir', False),
            (EVENT_TYPE_CREATED, './renamed_dir/dir/file', True),
            (EVENT_TYPE_DELETED, './dir', False),
            (EVENT_TYPE_DELETED, './dir/file', True),
            (EVENT_TYPE_DELETED, './dir/dir', False),
            (EVENT_TYPE_DELETED, './dir/dir/file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )

        assert a.poll() == []
        assert b.poll() == []

    # Multiple actions

    def test_multiple_events(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        create_file('new_file')
        os.remove('file')
        create_file(os.path.join('dir', 'new_file'))
        os.remove(os.path.join('dir', 'dir', 'file'))

        assert a.poll() == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_CREATED, './dir/new_file', True),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_DELETED, './dir/dir/file', True),
            (EVENT_TYPE_MODIFIED, '.', False),
            (EVENT_TYPE_MODIFIED, './dir', False),
            (EVENT_TYPE_MODIFIED, './dir/dir', False)
        )

    # Events

    def test_on_created(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        a_events = []
        b_events = []
        a.on_created = lambda x: a_events.append(x)
        b.on_created = lambda x: b_events.append(x)

        create_file('new_file')
        os.mkdir('new_dir')
        create_file(os.path.join('new_dir', 'new_file'))

        a.poll()
        assert a_events == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_CREATED, './new_dir', False),
        )

        b.poll()
        assert b_events == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_CREATED, './new_dir', False),
            (EVENT_TYPE_CREATED, './new_dir/new_file', True),
        )

    def test_on_modified(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        a_events = []
        b_events = []
        a.on_modified = lambda x: a_events.append(x)
        b.on_modified = lambda x: b_events.append(x)

        if SYSTEM_WINDOWS:
            os.chmod('file', stat.S_IREAD)
            os.chmod(os.path.join('dir', 'file'), stat.S_IREAD)
        else:
            os.chmod('file', 0o777)
            os.chmod(os.path.join('dir', 'file'), 0o777)

        a.poll()
        assert a_events == create_events(
            (EVENT_TYPE_MODIFIED, './file', True),
        )

        b.poll()
        assert b_events == create_events(
            (EVENT_TYPE_MODIFIED, './file', True),
            (EVENT_TYPE_MODIFIED, './dir/file', True),
        )

        if SYSTEM_WINDOWS:
            # Prevent PermissionError!
            os.chmod('file', stat.S_IWRITE)
            os.chmod(os.path.join('dir', 'file'), stat.S_IWRITE)

    def test_on_deleted(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        a_events = []
        b_events = []
        a.on_deleted = lambda x: a_events.append(x)
        b.on_deleted = lambda x: b_events.append(x)

        os.remove('file')
        os.remove(os.path.join('dir', 'file'))

        a.poll()
        assert a_events == create_events(
            (EVENT_TYPE_DELETED, './file', True),
        )

        b.poll()
        assert b_events == create_events(
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_DELETED, './dir/file', True),
        )

#

@contextlib.contextmanager
def start_watcher(x):
    x.start()
    yield
    x.join()


@pytest.mark.usefixtures("tmp_dir", "sample_files")
class TestWatcher:

    def test_repr(self):
        assert repr(Watcher()) == "<Watcher: is_active=False>"

    # Running

    def test_is_active(self):

        x = Watcher()
        assert x.is_active is False
        x.start()
        assert x.is_active is True
        x.stop()
        assert x.is_active is False

    def test_start(self):

        x = Watcher()
        assert x.start() is True
        assert x.start() is False
        x.stop()

    def test_stop(self):

        x = Watcher()
        x.start()
        assert x.stop() is True
        assert x.stop() is False

    # Callbacks

    def test_callback(self):

        x = Watcher(callback=lambda e: x.stop())
        x.schedule(1, '.')

        with start_watcher(x):
            create_file('new_file')

    def test_callback_events(self):

        events = []
        def on_callback(event):
            events.append(event)
            if len(events) == 3:
                x.stop()

        x = Watcher(callback=on_callback)
        x.schedule(0.1, '.')

        with start_watcher(x):
            os.remove('file')
            create_file('new_file')

        assert events == create_events(
            (EVENT_TYPE_CREATED, './new_file', True),
            (EVENT_TYPE_DELETED, './file', True),
            (EVENT_TYPE_MODIFIED, '.', False)
        )

    def test_on_callback(self):

        x = Watcher()
        x.on_callback = lambda e: x.stop()
        x.schedule(0.1, '.')

        with start_watcher(x):
            create_file('new_file')

    def test_custom_callback_method(self):

        x = Watcher(callback='foo')
        x.foo = lambda e: x.stop()
        x.schedule(0.1, '.')

        with start_watcher(x):
            create_file('new_file')

    # Tasks

    def test_schedule(self):

        x = Watcher()
        task = x.schedule(10, '.')

        assert task.interval == 10
        assert task.path == '.'
        assert task.is_active is False
        assert task in x.tasks

    def test_default_task(self):

        class MyTask(Task):
            def __init__(self, foo):
                super().__init__()
                self.foo = foo
            def run(self):
                yield self.foo

        def callback(event):
            x.stop()
            assert event == 'hello'

        x = Watcher(default_task=MyTask, callback=callback)
        x.schedule(1, 'hello')

        with start_watcher(x):
            pass

    def test_schedule_task(self):

        events = []
        def on_callback(event):
            events.append(event)
            if len(events) == 2:
                x.stop()

        x = Watcher(callback=on_callback)
        x.schedule_task(1, Poll('.'), Poll('.'))

        with start_watcher(x):
            modify_file('file')

        assert events == create_events(
            (EVENT_TYPE_MODIFIED, './file', True),
            (EVENT_TYPE_MODIFIED, './file', True)
        )

    def test_schedule_after_start(self):

        x = Watcher()
        x.start()
        task = x.schedule(1, '.')

        assert task.is_active is True

    def test_unschedule(self):

        x = Watcher()
        task = x.schedule(1, '.')
        x.start()

        assert task.is_active is True
        x.unschedule(task)
        assert task.is_active is False
        assert task not in x.tasks

    def test_unschedule_all(self):

        x = Watcher()
        task_a = x.schedule(1, '.')
        task_b = x.schedule(1, '.')
        x.start()

        x.unschedule_all()
        assert task_a not in x.tasks
        assert task_b not in x.tasks

    #

    def test_string_interval(self):

        x = Watcher()

        task = x.schedule('1hr', '.')
        assert task.interval == 3600

        task = x.schedule('0.5hr', '.')
        assert task.interval == 1800

        task = x.schedule('60min', '.')
        assert task.interval == 3600

        task = x.schedule('01:01:30', '.')
        assert task.interval == 3690

    def test_time_methods(self):

        x = Watcher()

        task = x.schedule(hours(1), '.')
        assert task.interval == 3600

        task = x.schedule(minutes(60), '.')
        assert task.interval == 3600


# TODO: Test Poll callback
# TODO: Test PathPoll callback


class TestSimpleWatcher:
    """A SimpleWatcher"""

    def test_repr(self):
        assert repr(SimpleWatcher(10, '.', lambda x: x)) == \
            "<SimpleWatcher: is_active=False>"

    def test_callable(self):
        """Should run a callable when a file system changed."""

        i = 0
        def function(a, b):
            nonlocal i
            i = i + a + b

        x = SimpleWatcher(CHECK_INTERVAL, '.', function, [1], {'b': 1})
        create_file('new.file')
        x.loop()
        assert i == 2

    def test_stop_in_check(self):
        """Can stop watcher from called function."""

        def function(x):
            # In this situation stop() cannot wait unit check thread will
            # be dead, because stop() is run by the check thread!
            x.stop()

        x = SimpleWatcher(CHECK_INTERVAL, '.', function)
        x.args = (x,)
        create_file('new.file')
        x.start()
        x.join()

        assert x.is_alive is False

    def test_is_alive(self):
        """Should set a is_alive attribute to False only if all check threads are dead"""

        def function(x):
            x.stop()
            time.sleep(2)

        x = SimpleWatcher(CHECK_INTERVAL, '.', function)
        x.args = (x,)
        x.start()
        create_file('new.file')
        x.join()

        assert x.is_alive is False





# Benchmark

# TODO: benchmark
# def benchmark(times=1000):
#     """Benchmarks each watcher."""
#
#     # Prepare temp directory with example files.
#     cwd = os.getcwd()
#     path = create_test_files()
#     os.chdir(path)
#
#     msg = 'Watching {} files in {} directories.'.format(8 * times, 2 * times)
#     print(msg)
#
#     x = timeit.timeit('DirectoryWatcher(1, ".", recursive=True).check()',
#                       setup='from watchers import DirectoryWatcher', number=times)
#
#     sample = round(x / (8 * times) * 1000, 3)
#
#     print('DirectoryWatcher: \t{} s. one file: {} ms.'.format(round(x, 3), sample))
#
#     x = timeit.timeit(
#         'SimpleWatcher(1, ".", target=lambda: 1, recursive=True).check()',
#         setup='from watchers import SimpleWatcher', number=times)
#
#     sample = round(x / (8 * times) * 1000, 3)
#     print('SimpleWatcher: \t{} s. one file: {} ms.'.format(round(x, 3), sample))
#
#     # Cleaning!
#     shutil.rmtree(path)
#     os.chdir(cwd)

#
# if __name__ == "__main__":
#
#     if '-b' in sys.argv or '--benchmark' in sys.argv:
#         benchmark()
#     else:
#         unittest.main()
