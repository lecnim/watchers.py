from watchers import __version__
from distutils.core import setup

doc = '''

watchers.py
===========

|Build Status|

A simple script that monitors changes in the file system using
polling. Useful for small, platform independent projects that don’t need
complex libraries like great `watchdog`_.

Facts or why you should take a good look at watchers.py:

-  No dependencies, only Python ``3.2``, ``3.3`` or ``3.4``
-  Supports **Windows** and **Unix**
-  Only one file, less than **12 KB**
-  Simple and minimalistic

Example
-------

A simple program that uses watchers.py to monitor specified directory
in 2 seconds interval. It prints the message on a change in a file
system.

.. code:: python


    from watchers import SimpleWatcher

    def foo():
        print('Something has changed in directory!')
    x = SimpleWatcher(2, 'path/to/dir', foo)
    x.start()
    
`More examples available at Github.`__

Why polling? WHY?!
------------------

Because it works everywhere and has no other dependencies than pure Python.

Installation
------------

Install from PyPI using pip

.. code:: bash

    pip install watchers.py

Or download a file ``watchers.py`` and use it in your project directly.

Performance
-----------

System:

::

    Intel(R) Core(TM)2 Duo CPU E8400 @ 3.00GHz
    Debian Linux 3.13-1-686 on USB flash drive

Checking 8000 files in 2000 directories took:

::

                    Total:    Checking one file:
    Watcher:        463 ms    0.058 ms
    SimpleWatcher:  379 ms    0.047 ms



.. _watchdog: https://github.com/gorakhargosh/watchdog

.. __: https://github.com/lecnim/watchers.py#more-examples

.. |Build Status| image:: https://travis-ci.org/lecnim/watchers.py.png?branch=master
   :target: https://travis-ci.org/lecnim/watchers.py

'''

setup(
    name='watchers.py',
    version=__version__,
    author='Leknim',
    author_email='lecnim@gmail.com',
    py_modules=['watchers'],
    url='https://github.com/lecnim/watchers.py',
    license='MIT',
    description='A simple script that monitors changes in the file system using polling.',
    long_description=doc,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Filesystems',
        'Topic :: System :: Monitoring',
        'Topic :: Utilities'
    ]
)
