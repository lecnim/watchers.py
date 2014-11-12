from watchers import __version__
from distutils.core import setup

doc = '''

Simple script that monitors changes in the file system using polling.
Useful for small, platform independent projects.
No requirements, only Python 3.2, 3.3 or 3.4.
Supports Windows and Unix.

.. code:: python

    # Use a SimpleWatcher to run a function when there is a change in a directory.

    from watchers import SimpleWatcher

    def foo():
        print('Something has changed in directory!')
    # Watch a 'path/to/dir' location in 2 seconds intervals and run a foo() when
    # change is detected.
    x = SimpleWatcher(2, 'path/to/dir', foo)
    # Use start() to start watching.
    x.start()

    # You can stop Watcher using stop():
    x.stop()
    # Or use is_alive property if you want to know if watcher is still running:
    if x.is_alive:
        print('HE IS ALIVE AND HE IS WATCHING!')


    # Passing arguments to a function:

    def foo(a, what):
        print(a, what)
    SimpleWatcher(10, 'path/to/dir', foo, args=('Hello',), kwargs={'what': 'World'})


    # There is also a recursive mode:

    SimpleWatcher(0.25, 'path/to/dir', foo, recursive=True)


    # You can ignore specific files or directories using a filter argument:

    def shall_not_pass(path):
        """Ignore all paths which ends with '.html'"""
        if path.endswith('.html'):
            # Path will be ignored!
            return False
        return True

    SimpleWatcher(2, 'path/to/dir', foo, filter=shall_not_pass)



    # Use a Watcher class to have a better control over file system events.

    from watchers import Watcher

    class MyWatcher(Watcher):

        # Runs when a file or a directory is modified.
        def on_modified(self, item):

            # Argument item has some interesting properties like:

            item.path       # A path to created item.
            item.is_file    # Checks if an item is a file or a directory.
            item.stat       # An os.stat() result.

        # Runs when a file or a directory is created.
        def on_created(self, item):
            pass
        # Runs when a file or a directory is deleted.
        def on_deleted(self, item):
            pass

    # Checks 'path/to/dir' location every 10 seconds.
    w = MyWatcher(10, 'path/to/dir')
    w.start()

    # A Watcher class supports a filter, recursive and check_interval arguments
    # just like a SimpleWatcher class:

    Watcher(10, 'path/to/dir', recursive=True, filter=lambda x: True)



    # A Manager class can group watchers instances and checks each of it:

    from watchers import Manager

    manager = Manager()
    manager.add(Watcher(2, 'path/to/file'))
    manager.add(SimpleWatcher(0.1, 'path/to/file', foo))

    # Two watchers will start and look for changes:
    manager.start()


    # You can access grouped watchers using a Manager.watchers property:
    for i in manager.watchers:
        print(i)

    # There is no problem with adding or removing watchers when a manager
    # is running:
    w = Watcher(10, 'path/to/file')
    manager.add(w)
    manager.remove(w)

    # But remember that manager do not start added watcher...
    manager.add(w)
    w.start()
    # ... and do NOT stop during removing!
    manager.remove(w)
    w.stop()

    # Removing all watchers with one call:
    manager.clear()
    # Remember to stop manager!
    manager.stop()

'''

setup(
    name='watchers.py',
    version=__version__,
    author='Leknim',
    author_email='lecnim@gmail.com',
    py_modules=['watchers'],
    url='https://github.com/lecnim/watchers.py',
    license='LICENSE',
    description='A simple script that monitors changes in the file system using polling.',
    long_description=doc,
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Utilities'
    ]
)