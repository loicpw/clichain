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

creating a factory
----------------------------------------

todo

implementing a task
----------------------------------------

todo

registering a task
----------------------------------------

todo

running the command line tool
----------------------------------------

todo

logging
----------------------------------------

todo

exceptions handling
----------------------------------------

todo

