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
import threading

import watchers
from watchers import Watcher, PathPolling, Event, PYTHON32, DirectoryPolling, FilePolling, FileWatcher, SimpleWatcher, Manager, DELETED, CREATED, MODIFIED, ItemPoller, Directory, STATUS_CREATED, STATUS_DELETED, STATUS_MODIFIED

# For faster testing.
CHECK_INTERVAL = 0.25

SYSTEM_WINDOWS = True if platform.system().lower() == 'Windows' else False

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

    elif metafunc.cls.__name__ == 'TestDirectoryPolling':

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
        assert repr(PathPolling('.')) == "<ItemPoller: path=.>"

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
            [('file', STATUS_DELETED), ('dir', STATUS_DELETED)],
        'test_rename':
            [('file', STATUS_DELETED), ('dir', STATUS_DELETED)],
        'test_cwd':
            [('file', STATUS_MODIFIED), ('dir', STATUS_MODIFIED)],
        'test_permissions':
            [('file', STATUS_MODIFIED), ('dir', STATUS_MODIFIED)],
        'test_modify_file':
            [('file', STATUS_MODIFIED)],
        'test_create':
            [('file', STATUS_CREATED), ('dir', STATUS_CREATED)],
        'test_delete':
            [('file', STATUS_DELETED), ('dir', STATUS_DELETED)],
        'test_recreate_file':
            [('file', STATUS_MODIFIED)],
        'test_swap_file_with_directory':
            [('file', STATUS_DELETED)],
        'test_recreate_directory':
            [('dir', STATUS_MODIFIED)],
        'test_swap_directory_with_file':
            [('dir', STATUS_DELETED)],

        'test_on_created':
            [('file', STATUS_CREATED), ('dir', STATUS_CREATED)],
        'test_on_deleted':
            [('file', STATUS_DELETED), ('dir', STATUS_DELETED)],
        'test_on_modified':
            [('file', STATUS_MODIFIED), ('dir', STATUS_MODIFIED)],

        'test_create_file_in_content':
            [('dir', STATUS_MODIFIED)],
        'test_create_directory_in_content':
            [('dir', STATUS_MODIFIED)],
        'test_modify_file_in_content':
            [('dir', None)],
        'test_delete_file_from_content':
            [('dir', STATUS_MODIFIED)],
        'test_delete_directory_from_content':
            [('dir', STATUS_MODIFIED)],
        'test_overwrite_file_in_content':
            [('dir', None)],
        'test_overwrite_directory_in_content':
            [('dir', None)],
        'test_rename_file_in_content':
            [('dir', STATUS_MODIFIED)],
        'test_rename_directory_in_content':
            [('dir', STATUS_MODIFIED)],
        'test_swap_content_items':
            [('dir', STATUS_MODIFIED)],
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

        os.rmdir(os.path.join(item.path, 'dir'))
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

        os.rmdir(os.path.join(item.path, 'dir'))
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

        def on_created(e):
            assert e == event
            item.called = True
        item.on_created = on_created

        self.test_create(item, event)
        assert item.called

    def test_on_deleted(self, item, event):

        def on_deleted(e):
            assert e == event
            item.called = True
        item.on_deleted = on_deleted

        self.test_delete(item, event)
        assert item.called

    def test_on_modified(self, item, event):

        def on_modified(e):
            assert e == event
            item.called = True
        item.on_modified = on_modified

        if item.is_file:
            self.test_modify_file(item, event)
            assert item.called
        else:
            self.test_permissions(item, event)
            assert item.called




@pytest.fixture()
def test_dir():

    # dog.txt
    # dir/cat.txt
    # dir/dog.txt
    # dir/dir/dog.txt

    # file
    # dir/file
    # dir/file.txt
    # dir/dir/file

    # with open('dog.txt', 'w') as f:
    #     f.write('wow')

    os.mkdir('dir')
    os.mkdir(os.path.join('dir', 'dir'))
    #
    # with open(os.path.join('dir', 'cat.txt'), 'w') as f:
    #     f.write('meow')
    # with open(os.path.join('dir', 'dog.txt'), 'w') as f:
    #     f.write('wow')
    # with open(os.path.join('dir', 'dir', 'dog.txt'), 'w') as f:
    #     f.write('wow')

    create_file('file', data='data')
    # os.mkdir('dir')
    # os.mkdir(os.path.join('dir', 'dir'))
    create_file(os.path.join('dir', 'file'), data='data')
    # create_file(os.path.join('dir', 'file.txt'), data='data')
    create_file(os.path.join('dir', 'dir', 'file'), data='data')


def create_events(*events):

    x = []
    for status, path, is_file in events:
        x.append(Event(status, path, is_file))

    return x

@pytest.mark.usefixtures("tmp_dir", "test_dir")
class TestDirectoryPolling:
    params = {}

    # file
    # dir/file
    # dir/dir/file


    def test_walk_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        assert [i.path for i in a.walk_items()] == \
               ['.',
                os.path.join('.', 'file'),
                os.path.join('.', 'dir')]
        assert [i.path for i in b.walk_items()] == \
               ['.',
                os.path.join('.', 'file'),
                os.path.join('.', 'dir'),
                os.path.join('.', 'dir', 'file'),
                os.path.join('.', 'dir', 'dir'),
                os.path.join('.', 'dir', 'dir', 'file')]

        # Reversed walk.

        assert [i.path for i in a.walk_items(top_down=False)] == \
               [os.path.join('.', 'file'),
                os.path.join('.', 'dir'),
                '.']
        assert [i.path for i in b.walk_items(top_down=False)] == \
               [os.path.join('.', 'dir', 'dir', 'file'),
                os.path.join('.', 'dir', 'file'),
                os.path.join('.', 'dir', 'dir'),
                os.path.join('.', 'file'),
                os.path.join('.', 'dir'),
                '.']

        # First directories, then files.

        assert [i.path for i in a.walk_items(dirs_first=True)] == \
               ['.',
                os.path.join('.', 'dir'),
                os.path.join('.', 'file')]
        assert [i.path for i in b.walk_items(dirs_first=True)] == \
               ['.',
                os.path.join('.', 'dir'),
                os.path.join('.', 'file'),
                os.path.join('.', 'dir', 'dir'),
                os.path.join('.', 'dir', 'file'),
                os.path.join('.', 'dir', 'dir', 'file')]





        # test_method:
        # [(path to item, expected EVENT_TYPE)]

        # 'test_create_items': [
        #
        #     (dict(path='.'), {
        #         Event(STATUS_MODIFIED,
        #               '.',
        #               is_file=False),
        #         Event(STATUS_CREATED,
        #               os.path.join('.', 'new_file'),
        #               is_file=True),
        #         Event(STATUS_CREATED,
        #               os.path.join('.', 'new_dir'),
        #               is_file=False)}),
        #
        #     (dict(path='.', recursive=False), {
        #         Event(STATUS_MODIFIED,
        #               '.',
        #               is_file=False),
        #         Event(STATUS_CREATED,
        #               os.path.join('.', 'new_file'),
        #               is_file=True),
        #         Event(STATUS_CREATED,
        #               os.path.join('.', 'new_dir'),
        #               is_file=False)})
        # ]}

    # def test_repr(self):
    #     assert repr(DirectoryPolling('.'))
    #
    # def test_init(self):
    #
    #     p = DirectoryPolling('.')
    #     paths = [i.path for i in p.items]
    #
    #     assert '.' in paths
    #     assert os.path.join('.', 'dog.txt') in paths
    #     assert os.path.join('.', 'dir') in paths
    #
    # def test_filter(self):
    #
    #     def ignore(path):
    #         if path.endswith('dog.txt'):
    #             return False
    #         return True
    #
    #     p = DirectoryPolling('.', filter=ignore)
    #     paths = [i for i in p._walk()]
    #
    #     assert not os.path.join('.', 'dog.txt') in paths
    #     assert os.path.join('.', 'dir') in paths
    #     assert os.path.join('.') in paths
    #     assert len(paths) == 2

    # Create

    def test_create_root(self):
        # TODO
        pass

    # @pytest.mark.parametrize("args, events", [
    #
    #     (dict(path='.'), {
    #         Event(STATUS_MODIFIED,
    #               '.'),
    #         Event(STATUS_CREATED,
    #               os.path.join('.', 'new_file'),
    #               is_file=True),
    #         Event(STATUS_CREATED,
    #               os.path.join('.', 'new_dir'),
    #               is_file=False)}),
    #
    #     (dict(path='.', recursive=True), {
    #         Event(STATUS_MODIFIED,
    #               '.',
    #               is_file=False),
    #         Event(STATUS_CREATED,
    #               os.path.join('.', 'new_file'),
    #               is_file=True),
    #         Event(STATUS_CREATED,
    #               os.path.join('.', 'new_dir'),
    #               is_file=False),
    #         Event(STATUS_MODIFIED,
    #               os.path.join('.', 'new_dir'),
    #               is_file=False),
    #         Event(STATUS_CREATED,
    #               os.path.join('.', 'new_dir', 'new_file'),
    #               is_file=True), }),
    # ])
    # def test_create_items(self, args, events):
    #
    #     p = DirectoryPolling(**args)
    #     create_file('new_file')
    #     os.mkdir('new_dir')
    #     create_file(os.path.join('new_dir', 'new_file'))
    #
    #     assert p.poll() == events


    # file
    # dir/file
    # dir/file.txt
    # dir/dir/file



    # Modify

    def test_modify_file(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        modify_file('file')
        modify_file('dir/dir/file')

        assert a.poll() == create_events(
            (STATUS_MODIFIED, './file', True)
        )
        assert b.poll() == create_events(
            (STATUS_MODIFIED, './file', True),
            (STATUS_MODIFIED, './dir/dir/file', True)
        )

    # Rename
    #
    # @pytest.mark.parametrize("args, events", [
    #     (dict(path='.'), [
    #         (STATUS_MODIFIED, '.', False),
    #         (STATUS_DELETED, './file', True),
    #         (STATUS_CREATED, './renamed', True),
    #     ]),
    #     (dict(path='.', recursive=True), [
    #         (STATUS_MODIFIED, '.', False),
    #         (STATUS_DELETED, './file', True),
    #         (STATUS_CREATED, './renamed', True),
    #         (STATUS_MODIFIED, './dir', False),
    #         (STATUS_DELETED, './dir/file', True),
    #         (STATUS_CREATED, './dir/renamed', True),
    #     ]),
    # ])
    # def test_rename_file(self, args, events):
    #
    #     p = DirectoryPolling(**args)
    #     os.rename('file', 'renamed')
    #     os.rename(os.path.join('dir', 'file'), os.path.join('dir', 'renamed'))
    #     assert p.poll() == create_events(events)
    #
    #
    # @pytest.mark.parametrize("args, events", [
    #     (dict(path='.'), [
    #         (STATUS_MODIFIED, '.', False),
    #         (STATUS_DELETED, './dir', False),
    #         (STATUS_CREATED, './renamed', False),
    #     ]),
    #     (dict(path='.', recursive=True), [
    #         (STATUS_MODIFIED, '.', False),
    #         (STATUS_DELETED, './dir', False),
    #         (STATUS_CREATED, './renamed', False),
    #         (STATUS_MODIFIED, './dir', False),
    #         (STATUS_DELETED, './dir/file', True),
    #         (STATUS_CREATED, './dir/renamed', True),
    #     ]),
    # ])
    # def test_rename_directory(self, args, events):
    #
    #     p = DirectoryPolling(**args)
    #     os.rename('dir', 'renamed')
    #     os.rename(os.path.join('dir', 'dir'), os.path.join('dir', 'renamed'))
    #     assert p.poll() == create_events(events)


    # def test_rename_directory(self):
    #
    #     p = DirectoryPolling('.')
    #     os.rename('dir', 'renamed')
    #
    #     e = p.poll()
    #     assert len(e) == 3
    #     assert Event(STATUS_DELETED, os.path.join('.', 'dir'),
    #                  is_file=False) in e
    #     assert Event(STATUS_CREATED,  os.path.join('.', 'renamed'),
    #                  is_file=False) in e
    #     assert Event(STATUS_MODIFIED, '.', is_file=False) in e

    # Create

    def test_create_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        create_file('new_file')
        os.mkdir('new_dir')
        create_file(os.path.join('new_dir', 'new_file'))

        assert a.poll() == create_events(
            (STATUS_CREATED, './new_file', True),
            (STATUS_CREATED, './new_dir', False),
            (STATUS_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (STATUS_CREATED, './new_file', True),
            (STATUS_CREATED, './new_dir', False),
            (STATUS_CREATED, './new_dir/new_file', True),
            (STATUS_MODIFIED, '.', False)
        )

    def test_delete_items(self):

        a = DirectoryPolling('.')
        b = DirectoryPolling('.', recursive=True)

        os.remove('file')
        shutil.rmtree('dir')

        assert a.poll() == create_events(
            (STATUS_DELETED, './file', True),
            (STATUS_DELETED, './dir', False),
            (STATUS_MODIFIED, '.', False)
        )
        assert b.poll() == create_events(
            (STATUS_DELETED, './dir/dir/file', True),
            (STATUS_DELETED, './dir/file', True),
            (STATUS_DELETED, './dir/dir', False),
            (STATUS_DELETED, './file', True),
            (STATUS_DELETED, './dir', False),
            (STATUS_MODIFIED, '.', False),
        )



    # Delete

    # def test_delete_root(self):
    #
    #     p = DirectoryPolling('dir')
    #     shutil.rmtree('dir')
    #
    #     e = p.poll()
    #
    #     assert Event(STATUS_DELETED, os.path.join('dir', 'dir'),
    #                  is_file=False) in e
    #     assert Event(STATUS_DELETED, os.path.join('dir', 'dog.txt'),
    #                  is_file=True) in e
    #     assert Event(STATUS_DELETED, os.path.join('dir', 'cat.txt'),
    #                  is_file=True) in e
    #     assert Event(STATUS_MODIFIED, 'dir', is_file=False) in e
    #     assert Event(STATUS_DELETED, 'dir', is_file=False) in e
    #     assert len(e) == 5



    # Permissions

    # def test_change_item_permissions(self):
    #
    #     p = DirectoryPolling('.')
    #
    #     os.chmod('dog.txt', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('dog.txt', 0o777)
    #     os.chmod('dir', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('dir', 0o777)
    #
    #     e = p.poll()
    #     assert len(e) == 2
    #     assert Event(STATUS_MODIFIED, os.path.join('.', 'dog.txt'),
    #                  is_file=True) in e
    #     assert Event(STATUS_MODIFIED, os.path.join('.', 'dir'),
    #                  is_file=False) in e
    #
    #     if SYSTEM_WINDOWS:
    #         # Prevent PermissionError!
    #         os.chmod('dog.txt', stat.S_IWRITE)
    #         os.chmod('dir', stat.S_IWRITE)
    #
    # def test_change_root_permissions(self):
    #
    #     p = DirectoryPolling('.')
    #     os.chmod('.', stat.S_IREAD) if SYSTEM_WINDOWS else os.chmod('.', 0o777)
    #
    #     e = p.poll()
    #     assert len(e) == 1
    #     assert Event(STATUS_MODIFIED, '.', is_file=False) in e
    #
    #     if SYSTEM_WINDOWS:
    #         # Prevent PermissionError!
    #         os.chmod('.', stat.S_IWRITE)

    # Rename

    # def test_rename_file(self):
    #
    #     p = DirectoryPolling('.')
    #     os.rename('dog.txt', 'renamed')
    #
    #     e = p.poll()
    #     assert len(e) == 3
    #     assert Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
    #                  is_file=True) in e
    #     assert Event(STATUS_CREATED, os.path.join('.', 'renamed'),
    #                  is_file=True) in e
    #     assert Event(STATUS_MODIFIED, '.', is_file=False) in e
    #
    # def test_rename_directory(self):
    #
    #     p = DirectoryPolling('.')
    #     os.rename('dir', 'renamed')
    #
    #     e = p.poll()
    #     assert len(e) == 3
    #     assert Event(STATUS_DELETED, os.path.join('.', 'dir'),
    #                  is_file=False) in e
    #     assert Event(STATUS_CREATED,  os.path.join('.', 'renamed'),
    #                  is_file=False) in e
    #     assert Event(STATUS_MODIFIED, '.', is_file=False) in e

    def test_rename_root(self):
        pass
        # TODO

    # Modify



    # Events

    # def test_on_create(self):
    #
    #     def on_created(e):
    #         assert e == Event(STATUS_CREATED, os.path.join('.', 'dog.txt'),
    #                           is_file=True)
    #         p.called = True
    #
    #     p = DirectoryPolling('.')
    #     p.on_created = on_created
    #
    #     os.remove('dog.txt')
    #     p.poll()
    #     create_file('dog.txt')
    #     p.poll()
    #
    #     assert p.called
    #
    # def test_on_modify(self):
    #
    #     def on_modified(e):
    #         assert e == Event(STATUS_MODIFIED, os.path.join('.', 'dog.txt'),
    #                           is_file=True)
    #         p.called = True
    #
    #     p = DirectoryPolling('.')
    #     p.on_modified = on_modified
    #
    #     with open('dog.txt', 'a') as f:
    #         f.write('updated')
    #     p.poll()
    #
    #     assert p.called
    #
    # def test_on_delete(self):
    #
    #     def on_deleted(e):
    #         assert e == Event(STATUS_DELETED, os.path.join('.', 'dog.txt'),
    #                           is_file=True)
    #         p.called = True
    #
    #     p = DirectoryPolling('.')
    #     p.on_deleted = on_deleted
    #
    #     os.remove('dog.txt')
    #     p.poll()
    #
    #     assert p.called

@pytest.mark.skipif(True, reason=':(')
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

    # Modify

    def test_modify_files(self):

        p = DirectoryPolling('.', recursive=True)

        with open(os.path.join('dir', 'dog.txt'), 'a') as f:
            f.write('update')
        with open(os.path.join('dir', 'dir', 'dog.txt'), 'a') as f:
            f.write('update')

        e = p.poll()

        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert Event(STATUS_MODIFIED, os.path.join('.', 'dir', 'dir', 'dog.txt'),
                     is_file=True) in e
        assert len(e) == 2





class BaseTest:
    """A base test class."""

    # Watcher class
    class_ = None
    # Class __init__ attributes
    kwargs = {}




    def test_interval(self):
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

    def test_on_created(self, watcher):

        def on_created(event):
            watcher.stop()
            watcher.called = True
        watcher.on_created = on_created

        threading.Thread(target=watcher.start).start()
        create_file('new_file')
        watcher.join()

        assert watcher.called

    def test_on_modified(self):
        pass

    def test_on_deleted(self):
        pass


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
