documentation
=====================

here's a practical documentation, for source documentation please
see :doc:`clichain`

quickstart
----------------------------------------

to create a command line tool with `clichain` you need:

+ to create a factory: ::

    from clichain import cli
    tasks = cli.Tasks()

+ to implement task types using coroutine functions:

  .. seealso:: http://www.dabeaz.com/coroutines

  The easiest way of implementing a task type is to use the *task*
  decorator: ::
           
    from clichain import pipeline
    import logging
    import ast


    @pipeline.task
    def add_offset(ctrl, offset):
        logger = logging.getLogger(f'{__name__}.{ctrl.name}')
        logger.info(f'starting, offset = {offset}')

        with ctrl as push:
            while True:
                value = yield
                push(value + offset)

        logger.info('offset task finished, no more value')


    @pipeline.task
    def parse(ctrl):
        _parse = ast.literal_eval
        with ctrl as push:
            while True:
                push(_parse((yield)))

  .. seealso:: `clichain.pipeline.task`

+ to register task types into the factory:

  tasks are integrated into the command line tool using `click` commands
  
  The simplest way of registering a task type is to decorate it with the
  factory:

  ::

    import click


    @tasks
    @click.command(name='offset')
    @click.argument('offset')
    def offset_cli(offset):
        "add offset to value"
        offset = ast.literal_eval(offset)
        return add_offset(offset)


    @tasks
    @click.command(name='parse')
    def parse_cli():
        "parse input data with ast.literal_eval"
        return parse()

  .. seealso:: `click` documentation for more details about commands

  .. note:: it's up to you to determine where and how you want the
    tasks to be registered into the factory, one way of doing this is
    to make the factory a module attribute and use it into separate 
    scripts...
    

+ to start the main command from your main entry point:

  ::

    if __name__ == '__main__':
        cli.app(tasks)


If we combine all the previous code into a single script, we get this:

::

    #! /usr/bin/env python
    # -*- coding: utf-8 -*-
    from clichain import cli, pipeline
    import click
    import logging
    import ast
    
    
    tasks = cli.Tasks()
    
    
    # -------------------------------------------------------------------- #
    # implement tasks                                                      # 
    # -------------------------------------------------------------------- #
    @pipeline.task                                                              
    def add_offset(ctrl, offset):                                                   
        logger = logging.getLogger(f'{__name__}.{ctrl.name}')                   
        logger.info(f'starting, offset = {offset}')                             
                                                                                
        with ctrl as push:                                                      
            while True:                                                         
                value = yield                                                   
                push(value + offset)                                            
                                                                                
        logger.info('offset task finished, no more value')                      
                                                                                
    
    @pipeline.task                                                              
    def parse(ctrl):                                                            
        _parse = ast.literal_eval                                               
        with ctrl as push:                                                      
            while True:                                                         
                push(_parse((yield))) 
    
    
    # -------------------------------------------------------------------- #
    # register tasks                                                       #
    # -------------------------------------------------------------------- #
    @tasks                                                                      
    @click.command(name='offset')                                               
    @click.argument('offset')                                                   
    def offset_cli(offset):                                                     
        "add offset to value"
        offset = ast.literal_eval(offset)                                       
        return add_offset(offset)                                                   
                                                                                
                                                                                
    @tasks                                                                      
    @click.command(name='parse')                                                
    def parse_cli():                                                            
        "parse input data with ast.literal_eval"
        return parse() 
    
    
    # -------------------------------------------------------------------- #
    # run cli                                                              #
    # -------------------------------------------------------------------- #
    if __name__ == '__main__':
        cli.app(tasks)

if our script is called '**dummy.py**', we can use **\\--help** option to get
a full description: ::

    $ ./dummy.py --help
    Usage: dummy.py [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...
    
      create a pipeline of tasks, read text data from the standard input
      and send results to the standard output: ::
    
                  stdin(text) --> tasks... --> stdout(text)
    

    [...]
    
    
    Options:
      -l, --logfile PATH  use a logfile instead of stderr
      -v, --verbose       set the log level: None=WARNING, -v=INFO, -vv=DEBUG
      --help              Show this message and exit.
    
    Commands:
      offset  add offset to value
      parse   parse input data with ast.literal_eval
      [       begin fork
      ]       end fork
      ,       new branch
      {       begin debug name group
      }       end debug name group

we can see our two task types are availables, we can use **\\--help**
option as well on it: ::

    $ ./dummy.py offset --help
    Usage: dummy.py offset [OPTIONS] OFFSET
    
      add offset to value
    
    Options:
      --help  Show this message and exit.

.. seealso:: `click`

assuming we want to run this: ::

                             +--> +1 --+
                  +--> +10 --|         +-----+
                  |          +--> +2 --+     |
    inp >> parse--|                          +--> >> out
                  +--> +100 --> +1 ----------+

we can use our tool as followings (*sh*): ::

    $ PIPELINE="parse [ offset 10 [ offset 1 , offset 2 ] , offset 100 offset 1 ]"
    $ python -c 'print("\n".join("123456789"))' | ./dummy.py $PIPELINE
    12
    13
    102
    13
    14
    103
    14
    15
    104
    15
    16
    105
    16
    17
    106
    17
    18
    107
    18
    19
    108
    19
    20
    109
    20
    21
    110

.. note:: everything is run into a single process and thread

.. _factory:

creating a factory
----------------------------------------

Task types are integrated into the command line tool using `click`
commands.

In order to achieve this we register commands into a *factory* and then
use that factory when running the main command line interface.

    ::

        from clichain import cli
        tasks = cli.Tasks()

The created factory will register all the commands into a `dict`, which
can be accessed via the **commands** attribute.

.. seealso:: `clichain.cli.Tasks`

It's up to the user to define a strategy about where to create the
factory and how to access it from different parts of the program.

.. _implement_task:

implementing a task
----------------------------------------

Task types are implemented using coroutine functions:

.. seealso:: http://www.dabeaz.com/coroutines

Though you can implement a coroutine by yourself, the framework provides
two ways of implementing a coroutine as expected by the framework:

+ `clichain.pipeline.coroutine` decorator

  this is simply a trivial decorator which creates a coroutine function
  that will be *primed* when called, i.e advanced to the first *yield*.

  example: ::

    from clichain import pipeline

    @pipeline.coroutine
    def cr(*args, **kw):
        print('starting...')
        try:
            while True:
                item = yield
                print(f'processing: {item}')
        except GeneratorExit:
            print('ending...')


  When used in a pipeline, the coroutine function will be called with
  specific keyword arguments:

  .. seealso:: `clichain.pipeline.create` for more details

  + **context**: a `clichain.pipeline.Context` object shared by all the
    coroutines of the pipeline.
  
  + **targets**: an iterable containing the following coroutines
    in the pipeline (default is no targets).
  
  + **debug**: an optional name (used by `clichain.pipeline.task`, see
    below)
  
    .. note:: Default value is the coroutine's key in the
        pipeline definition (default will be used if value is
        `None` or an empty string).

+ `clichain.pipeline.task` decorator

  this is the easiest way of implementing a task type because the
  decorated function won't have to worry about the input args and
  `GeneratorExit` handling, in addition automatic exception handling
  will be performed if an exception occurs (see `clichain.pipeline.task`
  for details).

  The `clichain.pipeline.Control` object will provide a **push**
  function to directly send data to next stages of the pipeline, and
  a **name** attribute can be used to identify the coroutine instance
  (when logging for example). The name is optionally given when creating
  the pipeline object using `clichain.pipeline.create`.

  example: ::
           
    from clichain import pipeline

    @pipeline.task
    def add_offset(ctrl, offset):
        with ctrl as push:
            while True:
                value = yield
                push(value + offset)

registering a task
----------------------------------------

Task types are integrated into the command line tool using `click`
commands.

.. seealso:: `click` documentation for more details about commands

The factory (see :ref:`factory`) is a callable object meant to be used
as a decorator to register a new `click` command into its *commands*
dictionary.

::

    import click

    @tasks
    @click.command(name='offset')
    @click.argument('offset')
    def offset_cli(offset):
        "add offset to value"
        offset = ast.literal_eval(offset)
        return add_offset(offset)

The `click` command function is expected to return a coroutine function
that can be integrated into the created pipeline, see
:ref:`implement_task` section for details.

.. note:: in the previous example we can access the registered task
    through the *commands* attribute of the factory: ::

        assert tasks.commands['offset'] is offset_cli

    Note the *offset_cli* callback function is a decorated version of
    the original callback function (defined by the user).


running the command line tool
----------------------------------------

The main command is executed by `click` framework. Use the
`clichain.cli.app` function to run it with the factory, example: ::

    if __name__ == '__main__':
        cli.app(tasks)

.. note:: additional *args* and *kwargs* will be kept in the `click`
    context object, see `clichain.cli.app` for details.

testing
----------------------------------------

In order to perform automated tests you can run the `clichain.cli.test`
function, which will run the main command using `click.testing`
framework.

example: ::

    from clichain import cli
    
    tasks = cli.Tasks()

    # register the 'compute' task
    [...]

    # test
    args = ['compute', '--help']
    inputs = [1, 2, 3]
    result = cli.test(tasks, args, inputs=inputs)
    assert result.output == "foo"
    assert result.exit_code == 0
    assert not result.exception

.. note:: the test function supports additional arguments, see
    `clichain.cli.test` for details.

.. _logging_section:

logging
----------------------------------------

Automatic logging is performed for registered tasks by
`clichain.pipeline` framework when an unhandled exception occurs.

In this case the exception will be logged at **ERROR** level with
exception info (see `logging.error`), using the optional *name* of the
coroutine to determine the logger path.

.. todo:: custom kwargs cannot be passed to `clichain.pipeline.create`
    when using `clichain.cli` framework (`clichain.cli.app` or
    `clichain.cli.test`), such as custom root logger.

.. note:: when creating the pipeline the root logger to use can be
    specified, see `clichain.pipeline.create` for details. The default
    root logger will be `clichain.pipeline.logger`.

.. note:: an optional name can be given by the user (using a specific
    command defined in `clichain.cli`) to coroutines when creating the
    pipeline, see `clichain.pipeline.create` and :ref:`implement_task`
    for more details.

Using the optional name to perform logging in tasks implementation is
advised, example: ::
 
    from clichain import pipeline
    import logging

    logger = logging.getLogger(__name__)

    @pipeline.task
    def add_offset(ctrl, offset):
        log = logger.getChild(ctrl.name)
        log.info(f'starting, offset = {offset}')

        with ctrl as push:
            while True:
                value = yield
                push(value + offset)

        log.info('offset task finished, no more value')

exceptions handling
----------------------------------------

Exceptions in `click` commands should be handled using `click` exception
handling framework.

example: ::

    @tasks
    @click.command(name='offset')
    @click.argument('offset')
    def offset_cli(offset):
        "add offset to value"
        try:
            offset = ast.literal_eval(offset)
        except:
            raise click.BadParameter(f'wrong value: {offset}')

        return add_offset(offset)

If an unhandled exception occurs in a task when the pipeline is running,
then the exception will be logged (see :ref:`logging_section`) and the
main command will abort (using `click.Abort`) after all the coroutines
have been **closed**.

example: ::

    @pipeline.task
    def add_offset(ctrl, offset):
        with ctrl as push:
            while True:
                value = yield
                if value > 0:
                    push(value + offset)
                else:
                    raise NotImplementedError(value)

.. note:: In the above example, all the tasks after 'add_offset' in the
    pipeline will be terminated, all the tasks before 'add_offset' will
    fail. This behaviour is the native behaviour of coroutines, since
    coroutines following 'add_offset' will have no more values and
    coroutines before 'add_offset' will face a StopIteration.

Whatever the exit state of the process (fail or completed), all the
coroutines of the pipeline will be **closed** (i.e *coroutine.close()*
will be called), that means the following coroutine will close the file
**as soon as the pipeline stops** anyways: ::

    @coroutine
    def cr(*args, **kw):
        with open('foo/bar') as f:
            while True:
                data = yield
                [...]

.. seealso:: `clichain.pipeline.Pipeline`
