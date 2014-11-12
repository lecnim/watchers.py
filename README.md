watchers.py
===========

[![Build Status](https://travis-ci.org/lecnim/watchers.py.png?branch=master)](https://travis-ci.org/lecnim/watchers.py)

A simple script that monitors changes in the file system using polling.
Useful for small, platform independent projects that don't need complex
libraries like great [watchdog](https://github.com/gorakhargosh/watchdog).

### Facts or why you should take a good look at watchers.py:

- No dependencies, only Python `3.2`, `3.3` or `3.4`
- Supports __Windows__ and __Unix__
- Only one file, less than __12 KB__
- Simple and minimalistic


Example
-------

A simple program that uses watchers.py to monitor specified directory in 
2 seconds interval. It prints the message on a change in a file system.

```python

from watchers import SimpleWatcher

def foo():
    print('Something has changed in directory!')
x = SimpleWatcher(2, 'path/to/dir', foo)
x.start()
```


Why polling? WHY?!
------------------

Because it works everywhere and has no other dependencies than pure Python.


Installation
------------

Install from PyPI using pip::

```
pip install watchers.py
```

Or download a file `watchers.py` and use it in your project directly.


Performance
-----------

System:

```
Intel(R) Core(TM)2 Duo CPU E8400 @ 3.00GHz
Debian Linux 3.13-1-686 on USB flash drive
```

Checking 8000 files in 2000 directories took:

```
                Total:    Checking one file:
Watcher:        463 ms    0.058 ms
SimpleWatcher:  379 ms    0.047 ms
```


More Examples
-------------

```python

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

```
