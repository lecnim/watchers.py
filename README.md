watchers.py
===========

[![Build Status](https://travis-ci.org/lecnim/watchers.py.png?branch=master)](https://travis-ci.org/lecnim/watchers.py)

Simple script that monitors changes in the file system using polling.
Useful for small, platform independent projects.

No requirements, only Python `3.2`, `3.3` or `3.4`.

Supports __Windows__ and __Unix__.

Installation
------------

Download file `watchers.py` and use it in your project. That's all!

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


Examples
--------

```python

# Use a SimpleWatcher to run a function when there is a change in a directory.

from watchers import SimpleWatcher

def foo():
    print('Something has changed in directory!')
x = SimpleWatcher('path/to/dir', foo)
# Use start() to start watching changes.
x.start()

# You can stop Watcher using stop():
x.stop()
# Or use is_alive property if you want to know if watcher is running:
if x.is_alive:
    print('HE IS ALIVE!')


# Passing arguments to a function:

def foo(a, what):
    print(a, what)
SimpleWatcher('path/to/dir', foo, args=('Hello',), kwargs={'what': 'World'})


# There is also a recursive mode:

SimpleWatcher('path/to/dir', foo, recursive=True)


# You can ignore specific files or directories using a filter argument:

def shall_not_pass(path):
    """Ignore all paths which ends with '.html'"""
    if path.endswith('.html'):
        # Path will be ignored!
        return False
    return True

SimpleWatcher('path/to/dir', foo, filter=shall_not_pass)


# Watcher use polling so it check for changes every x seconds. You can set
# the interval using check_interval.

# Check for changes every 4 seconds.
SimpleWatcher('path/to/dir', foo, check_interval=4)



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

w = MyWatcher('path/to/dir')
w.start()

# A Watcher class supports a filter, recursive and check_interval arguments
# just like a SimpleWatcher class:

Watcher('path/to/dir', recursive=True, filter=lambda x: True, check_interval=2)



# A Manager class can group watchers instances and check each of it:

from watchers import Manager

manager = Manager()
manager.add(Watcher('path/to/file'))
manager.add(SimpleWatcher('path/to/file'))

# Two watchers will start and look for changes:
manager.start()

# Just like a watcher, manager has is_alive property:
if manager.is_alive:

    # You can access grouped watchers using a Manager.watchers property:
    for i in manager.watchers:
        print(i)

# There is no problem with adding or removing watchers when a manager
# is running:
w = Watcher('path/to/file')
manager.add(w)
manager.remove(w)

# Or removing all watchers with one call:
manager.clear()

# Remember to stop manager!
manager.stop()

```
