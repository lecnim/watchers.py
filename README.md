watchers.py
===========

[![Build Status](https://travis-ci.org/lecnim/watchers.py.png?branch=master)](https://travis-ci.org/lecnim/watchers.py)

A simple script that monitors changes in the file system using polling.
Useful for small, platform independent projects which don't need complex
libraries like great [watchdog](https://github.com/gorakhargosh/watchdog).

### Facts or why you should take a good look at watchers.py:

- No dependencies, only Python `3.2`, `3.3` or `3.4`
- Supports __Windows__ and __Unix__
- Only one file, less than __20 KB__
- Simple and minimalistic


Example
-------

A simple program that uses watchers.py to monitor specified directory in 
2 seconds interval. It prints the message on a change in a file system.

```python

from watchers import Watcher

def log(event):
    print(event)

x = Watcher(callback=log)
x.schedule(2, 'path/to/directory')
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

# Generally Task classes generates Events instances when there is a change
# in the file system. All this events are later send to callback method, one
# by one.

# Here there is a Poll task which monitors changes in a given directory and
# sends events to the foo() method.

def foo(event):

    # There a three types of default Event.
    if event.type == 'created':
        # Path was created.
        pass
    if event.type == 'modified':
        # Path was modified.
        pass
    if event.type == 'deleted':
        # Path was deleted.
        pass

    event.path      # Event source, for example: 'path/to/file'
    event.is_file   # Detects if path is a file or directory.

task = Poll('my/documents', callback=foo)

# When you start a task you must set time interval used for repeating.
# In this situation task will be repeated after 10 seconds again and again.
task.start(10)

# Use is_active property to detects if task is running.
if task.is_active:
    print('IT IS ALIVE!')

# join() method waits until task is stopped. Obviously you can stop task
# using stop() method.
task.join()
task.stop()

# When an argument callback is missing, a task will use the on_callback()
# method instead.

class MyTask(Poll):
    def on_callback(self, event):
        print(event)
task = MyTask('path/to/directory')

# You can monitor a directory including all subdirectories using recursive argument.
Poll('my/documents', recursive=True, callback=foo)

# Use filter argument to skip paths that you do not want to monitor.

def shall_not_pass(path):
    return False if path.endswith('.html') else True
Poll('my/documents', filter=shall_not_pass, callback=foo)


# PathPoll task is used to monitor only one given path. For example you can
# monitor one specific file or one specific directory.

task = PathPoll('path/to/file', callback=foo)
task.start(12)



# Watcher class collects many tasks in one place.
watcher = Watcher()

# You can add task to Watcher using the schedule_task() method. Notice that 
# time intervals are set when tasks are scheduled.
task = Poll('my/documents')
watcher.schedule_task(12, task)

# When Watcher starts it also starts all collected tasks.
watcher.start()
watcher.is_active # True

# Task is started immediately when added to already running watcher.
watcher.start()
task = Poll('images')
watcher.schedule_task(10, task)
task.is_active # True

# stop() and join() methods are also supported.
watcher.join()
watcher.stop()

# You can remove task from watcher using unschedule() method.
# Unscheduled task is stopped immediately.
watcher.unschedule(task)
# Or use unschedule_all() to remove all collected tasks.
watcher.unschedule_all()


# By default the schedule() method is a shortcut for scheduling Poll tasks.
watcher.schedule(10, 'my/documents', callback=foo)

# You can change default schedule() task using default_task argument.
# Here schedule() will use a PathPoll task instead of a default Poll task.
watcher = Watcher(default_task=PathPoll)
watcher.schedule(10, 'my/file', callback=foo)

# The schedule() method always returns a Task instance, so for example you can
# unschedule this task later.
task = watcher.schedule(6, 'my/file')
watcher.unschedule(task)


# Watcher supports callback method just like tasks. In this situation event is
# send to the task callback first and then to the watcher callback.

def foo(event):
    print('Task callback', event)
def bar(event):
    print('Watchers callback', event)

watcher = Watcher(callback=bar)
watcher.schedule(10, 'my/documents', callback=foo)

```
