clichain
========  

|license| |python version| |build-status| |docs| |coverage| |pypi package|

.. |license| image:: https://img.shields.io/github/license/loicpw/clichain.svg
.. |build-status| image:: https://travis-ci.org/loicpw/clichain.svg?branch=master
    :target: https://travis-ci.org/loicpw/clichain
.. |docs| image:: https://readthedocs.org/projects/clichain/badge/?version=latest
    :target: http://clichain.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status
.. |coverage| image:: https://coveralls.io/repos/github/loicpw/clichain/badge.svg?branch=master
    :target: https://coveralls.io/github/loicpw/clichain?branch=master
.. |pypi package| image:: https://badge.fury.io/py/clichain.svg
    :target: https://badge.fury.io/py/clichain
.. |python version| image:: https://img.shields.io/pypi/pyversions/clichain.svg
   :target: https://pypi.python.org/pypi/clichain

Create a command line interface to chain tasks as a pipeline

**clichain** is a framework to easily define task types and chain them
from a command line interface.

The goal of this framework is to use `David Beazle's idea`_ to implement
task types as coroutines and use them to create and run a pipeline.

The goal is **not** to parallelize tasks but to be able to reuse task
types in different configurations without need for coding and in some
cases reuse a result from a long computational task for different
purposes without running it several times. 

install and test
=======================

install from pypi
********************

using pip:

.. code-block:: bash

    $ pip install clichain

install using requirements
****************************

There is a makefile in the project root directory:
    
.. code-block:: bash

    $ make install

Using pip, the above is equivalent to:

.. code-block:: bash

    $ pip install -r requirements.txt                                             
    $ pip install -e .

dev install
****************

There is a makefile in the project root directory:
    
.. code-block:: bash

    $ make dev

Using pip, the above is equivalent to:

.. code-block:: bash

    $ pip install -r requirements-dev.txt                                             
    $ pip install -e .

run the tests
******************

Use the makefile in the project root directory:

.. code-block:: bash

    $ make test

This runs the tests generating a coverage html report

build the doc
******************

The documentation is made with sphinx, you can use the makefile in the
project root directory to build html doc:

.. code-block:: bash

    $ make doc

Documentation
=======================

Documentation on `Read The Docs`_.

Meta
=======================

loicpw - peronloic.us@gmail.com

Distributed under the MIT license. See ``LICENSE.txt`` for more information.

https://github.com/loicpw


.. _Read The Docs: http://clichain.readthedocs.io/en/latest/
.. _David Beazle's idea: http://www.dabeaz.com/coroutines/
