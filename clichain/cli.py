#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" `cli` focuses on the command line tool aspect using `click`

    .. seealso:: `Tasks`, `usage`, `clichain.pipeline`
"""

import click
import logging
import collections
from functools import wraps
import sys

from . import pipeline


logger = logging.getLogger(__name__)


class Tasks:
    """ Defines a factory to register tasks types.

        `Tasks` provides a factory to register and hold implemented
        tasks so they get available to the user.

        Tasks are implemented by coroutines.

        .. seealso:: `clichain.pipeline`

        The command line interface is implemented using `click`.
        In order to make a task usable from the command line interface,
        you need to define a `click` command (for most cases using
        `click.command` decorator).  example: ::

            @click.command(name='compute')
            @click.option('--approximate', '-a',
                          help='compute with approximation')
            @click.argument('x')
            def my_compute_task(approximate, x):
                " the task doc that will appear as help "
                # process inputs parameters and options...

        .. seealso:: `click` for details on how to implements commands

        The command is expected to return a coroutine function such as
        `clichain.pipeline.coroutine`, see `clichain.pipeline.create`
        for details.

        full example: ::

            from clichain import pipeline, cli
            import ast

            # creates the factory here but should be
            # common to all task types...
            tasks = cli.Tasks()

            @pipeline.task
            def divide(ctrl, den):
                print(f'{ctrl.name} is starting')

                with ctrl as push:
                    while True:
                        value = yield
                        push(value / den)

                print(f'{ctrl.name} has finished with no error')


            # the task will be made available as 'compute' in the
            # command line interface

            @tasks
            @click.command(name='compute')
            @click.option('--approximate', '-a',
                          help='compute with approximation')
            @click.argument('den')
            def compute_task_cli(approximate, den):
                " the task doc that will appear as help "
                if den == 0:
                    raise click.BadParameter("can't devide by 0")
                if approximate:
                    den = round(den)
                return devide(den)

            @pipeline.task
            def parse(ctrl):
                _parse = ast.literal_eval
                with ctrl as push:
                    while True:
                        try:
                            push(_parse((yield)))
                        except (SyntaxError, ValueError):
                            pass

            @tasks
            @click.command(name='parse')
            def parse_cli():
                " performs literal_eval on data "
                return parse()

        .. seealso:: `usage`
    """
    def __init__(self, commands=None):
        """ initializes new factory with `commands`

            `commands` is a dict containing all registered commands, and
            will be set to a new empty dict if None.

            `context` is the current click context, it's set to None
            until the main command is called (see `app`), which will
            set `context` to the current context value.
        """
        self.commands = {}
        self.context = None

    def __call__(self, cmd):
        """ wraps and register a `click.command` object into the factory

            `Tasks` object is intended to be used as a decorator: ::

                tasks = cli.Tasks()

                # register 'compute' command into 'tasks'
                @tasks
                @click.command(name='compute')
                [...]

            The command is expected to return a coroutine function such
            as `clichain.pipeline.coroutine`, see
            `clichain.pipeline.create` for details.

            .. note:: a log message will be emitted to indicate this
                task is created every time the command is called
        """
        cmdname = cmd.name
        self.commands[cmdname] = self._prepare_cmd(cmd)
        return cmd

    def _prepare_cmd(self, cmd):
        """ wraps the `click.command` callback function and replace it

            the wrapper function will:

            + log a 'create' message (using `logger.info`)

            + use the callback function result to create the next
              coroutine in the pipeline. The coroutine function created
              by the callback function is stored in the current `click`
              context. A stack is used to process pipeline's branches.

                .. seealso:: `clichain.pipeline` for details on how the
                    pipeline is specified

            The wrapper function does not return anything

            .. seealso:: this method is called by `Tasks.__call__`
        """
        f = cmd.callback

        @wraps(f)
        def callback(*args, **kw):
            logger.info(f'create: {cmd.name}')
            # NOTE: click.get_current_context() only works in the main
            #       thread, unless the current thread is run within
            #       the context called as a context manager.
            # XXX ctx = click.get_current_context().obj
            ctx = self.context.obj
            branch = ctx['branch']

            # create branch if first task in the branch
            if branch is None:
                branch = {'sequence': [], 'input': ctx['output']}
                ctx['branch'] = branch
                ctx['output'] = [ctx['index']]

            # add coroutine to current branch
            sequence = branch['sequence']
            coroutine = {
                'task': f(*args, **kw),
            }

            # set 'debug' name if required for the current branch
            if ctx['debug_name'] is not None:
                coroutine['debug'] = ctx['debug_name']

            sequence.append(coroutine)
            return None  # TODO should we return anything ?

        cmd.callback = callback
        return cmd


class Cli(click.MultiCommand):
    """ Implements root command using `click.MultiCommand`

        .. seealso:: `click`

        `Cli` provides implementation for the root command by extending
        `click.MultiCommand` (Then the click command is created
        specifying `Cli` as "cls" parameter in the `click.command`
        decorator.

        .. seealso:: `app`, `Tasks`
    """
    def list_commands(self, ctx):
        tasks = ctx.obj['tasks']
        rv = list(tasks.commands.keys())
        rv.append(_begin_fork.name)
        rv.append(_end_fork.name)
        rv.append(_new_branch.name)
        rv.append(_begin_debug_name.name)
        rv.append(_end_debug_name.name)
        return rv

    def get_command(self, ctx, name):
        tasks = ctx.obj['tasks']
        if name == _begin_fork.name:
            return _begin_fork
        elif name == _end_fork.name:
            return _end_fork
        elif name == _new_branch.name:
            return _new_branch
        if name == _begin_debug_name.name:
            return _begin_debug_name
        if name == _end_debug_name.name:
            return _end_debug_name
        try:
            return tasks.commands[name]
        except KeyError:
            raise click.UsageError(f'No such command "{name}"')


# NOTE: "\b" to prevent click from rewrapping examples paragraphs
def usage():
    """ create a pipeline of tasks, read text data from the
        standard input and send results to the standard output: ::

            stdin(text) --> tasks... --> stdout(text)

        The overall principle is to run a data stream processor by
        chaining different kinds of tasks (available tasks depending
        on the implementation, see list below).

        you can create a single branch pipeline as a sequence of
        tasks, for instance: ::

            inp >>> A -> B -> C >>> out

        or you can create a more complex pipeline defining multiple
        branches, for instance: ::

                       +--> B --> C --+
            inp >>> A--|              +--> F >>> out
                       +--> D --> E --+

        tasks are implemented by *coroutines* functions as described by
        David Beazle (see http://www.dabeaz.com/coroutines/ for details).



        + Specifying pipeline workflow:

          basic syntax allows you to specify the worflow of the pipeline.

          A single sequence of tasks as the following: ::

              inp >>> A -> B -> C >>> out

          is specified as: ::

              A B C

          .. note:: plus parameters and options of the tasks themselves,
              i.e: ::

                  A -x -y arg1 B -z ...

          Creating branches requires 'workflow commands', for instance
          the following example: ::

                         +--> B --> C --+
              inp >>> A--|              +--> F >>> out
                         +--> D --> E --+

          would be specified as: ::

              A [ B C , D E ] F

          the same way we can define sub branches, for instance: ::

                                  +--> C1 --+
                         +--> B --|         +-----+
                         |        +--> C2 --+     |
              inp >>> A--|                        +--> F >>> out
                         +--> D --> E ------------+

          would be specified as: ::

              A [ B [ C1 , C2 ] , D E ] F



        + Execution order:

          When *parallel* branches are defined (as 'C1' and 'C2' in the
          previous example) they are processed in the same order as they
          are defined in the command line arguments, that means in this
          example: ::

              A [ B [ C1 , C2 ] , D E ] F

          If the input data is: ::

              1
              2
              [...]

          Then the workflow will be such as: ::

              # data will go through C1 then C2
              1 -> A -> B -> C1 -> F
              1 -> A -> B -> C2 -> F
              2 -> A -> B -> C1 -> F
              2 -> A -> B -> C2 -> F
              [...]

          And the order is reproducible



        + Attaching a name to branches or tasks:

          You can attach a name to coroutines when defining the pipeline,
          which will be used as a suffix to get the logger if an
          exception occurs in the coroutne, i.e: ::

              base_logger.getChild(<name>)

          .. note:: This is useful in particular if you're using the
              same task type in several branches. The name could be used
              as well in the coroutine, depending on its implementation
              (see `clichain.pipeline.create` for more details).

          example: ::

                         +--> B --> C --+
              inp >>> A--|              +--> B >>> out
                         +--> B --> D --+

          you could specify the name of the branches (i.e all the
          coroutines of those branches) with: ::

              A [ { 'b1' B C } , { 'b2' B D } ] { 'b3' B )

          .. note:: the name specification is valid for every coroutine
              whose definition starts within the parenthesis,
              for example: ::

                  A { 'b1' [ B C , B D ] } B

              is equivalent to: ::

                  A [ { 'b1' B C , B D } ] B

              which is also equivalent to: ::

                  A [ { 'b1' B C , B D ] } B

              which is equivalent to: ::

                  A [ { 'b1' B C } , { 'b1' B D } ] B

              *note the output 'B' coroutine will have no name*

              And using the following specification: ::

                  A [ { 'b1' B } C , { 'b2' B } D ] B

              will only give 'b1' and 'b2' names to the 'B' coroutines
              (and not to the 'C' and 'D' coroutines as in the previous
              example).

              Then note the following: ::

                  A { 'b1' [ B C , { 'b2' B } D ] } B

              is equivalent to: ::

                  A [ { 'b1' B C } , { 'b2' B } { 'b1' D } ] B

              Then note that the following: ::

                  A [ { 'b1' } B , { 'b2' } B ] B

              will have no effect at all.
    """
    return _usage

_usage = usage.__doc__


@click.command(cls=Cli, chain=True,
               # add '\b' before code examples to avoid rewrapping
               # NOTE: add here because not rst compatible...
               help=usage().replace(' ::\n', ' ::\n\n\b'))
@click.option('--logfile', '-l',
              type=click.Path(exists=False),
              help='use a logfile instead of stderr')
@click.option('-v', '--verbose',
              count=True,
              help='set the log level: None=WARNING, -v=INFO, -vv=DEBUG')
@click.pass_context
def _app(ctx, logfile, verbose):
    """ this is the main command function, called by `app`

        the `_app` function itself only set up logging
    """
    log_levels = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }
    loglevel = log_levels.get(verbose, logging.DEBUG)
    # TODO more flexible logging config
    logging.basicConfig(format='%(name)s: %(levelname)s: %(message)s',
                        level=loglevel, filename=logfile)

    tasks = ctx.obj['tasks']
    tasks.context = ctx


@_app.resultcallback()
@click.pass_obj
def process(obj, rv, logfile, verbose):
    """ callback of the main command, called by `click`

        `process` creates the pipeline (using `clichain.pipeline.create`
        ), then run it with inputs from stdin and sending outputs to
        stdout (getting stdin and stdout from `click.get_text_stream`).

        if an exception occures then log the exception and raise
        `click.Abort`.

        .. seealso:: `clichain.pipeline`
    """
    _end_branch(obj)

    logger.info('creating pipeline...')
    stdin = click.get_text_stream('stdin')
    stdout = click.get_text_stream('stdout')

    def write(item):
        stdout.write(str(item))
        stdout.write('\n')

    pl = pipeline.create(obj['pipeline'], output=write)

    logger.info('processing...')
    logger.info('----------------------------------------')
    try:
        pl.run(stdin)
    except Exception as e:
        logger.error(f'abort: {type(e).__name__}: {e}')
        raise click.Abort from e
    logger.info('----------------------------------------')
    logger.info('DONE.')


@click.command(name=',')
@click.pass_obj
def _new_branch(obj):
    """ new branch """
    stack = obj['stack']
    head = stack[0]
    head['output'].extend(obj['output'])
    obj['output'] = head['input']
    _end_branch(obj)


@click.command(name='[')
@click.pass_obj
def _begin_fork(obj):
    """ begin fork """
    stack = obj['stack']
    stack.appendleft({
        'input': obj['output'],
        'output': [],
    })
    _end_branch(obj)


@click.command(name=']')
@click.pass_obj
def _end_fork(obj):
    """ end fork """
    stack = obj['stack']
    head = stack[0]
    head['output'].extend(obj['output'])
    obj['output'] = head['output']
    stack.popleft()
    _end_branch(obj)


def _end_branch(obj):
    br = obj['branch']
    if br is not None:
        index = obj['index']
        pl = obj['pipeline']

        # link and add branch's coroutines to the pipeline
        inp = br['input']
        # first to last-1 task in the branch
        for i, task in enumerate(br['sequence'][:-1]):
            task['input'] = inp
            key = f'{index}_{i}'
            pl[key] = task
            inp = key
        # last task in the branch
        # ( use <index> as key because it is the branch's output)
        task = br['sequence'][-1]
        task['input'] = inp
        pl[index] = task

        # prepare next branch
        obj['index'] = index + 1
        obj['branch'] = None


@click.command(name='{')
@click.argument('name')
@click.pass_obj
def _begin_debug_name(obj, name):
    """ begin debug name group """
    stack = obj['debug_name_stack']
    if obj['debug_name'] is not None:
        stack.appendleft(obj['debug_name'])
    obj['debug_name'] = name


@click.command(name='}')
@click.pass_obj
def _end_debug_name(obj):
    """ end debug name group """
    stack = obj['debug_name_stack']
    try:
        obj['debug_name'] = stack.popleft()
    except IndexError:
        obj['debug_name'] = None


def _get_obj(tasks, args, kwargs):
    """ get *obj* parameter for `click` context

        The created *obj* is a dict, it's used internally when
        processing commands.

        + `tasks` is the `Tasks` factory to use (containing user commands)

        + optional `args` and `kwargs` will be send to the `click`
          context (in context.obj['args'] and context.obj['kwargs']),
          they will not be used by the framework.

        This function is used by `app` and `test`.
    """
    output = ()
    return {
        'tasks': tasks,
        'pipeline': {},
        'stack': collections.deque({
            'input': [],
            'output': output,
        }),
        'debug_name_stack': collections.deque(),
        'debug_name': None,
        'index': 0,
        'args': args,
        'kwargs': kwargs,
        'branch': None,
        'output': output,
    }


def app(tasks, *args, **kw):
    """ run `click` main command: this will start the CLI tool.

        .. seealso:: `test`

        `tasks` is the `Tasks` factory to use (containing user commands)

        extra args and kwargs are added to the `click` context (**obj**)
        as '**args**' and '**kwargs**', they're not used by the
        framework.

        `app` uses `Cli` which extends `click.MultiCommand` to create
        the main command as a multicommand interface. This main command
        holds all the user defined commands and is the main entry point
        of the created tool.

        The pipeline itself is created and run by the `process`
        function, which is called when the main command itself returns,
        i.e when the all the input args have been processed by `click`.

        .. seealso:: `Tasks`, `process`

        .. seealso:: the main command itself only set up logging,
            see also `usage`
    """
    _app(obj=_get_obj(tasks, args, kw))


def test(tasks, clargs, args=None, kwargs=None, **kw):
    """ run the CLI using `click.testing`, intended for automated tests

        .. seealso:: `app`

        The main command is then run with `click.testing.CliRunner`

        this is roughly equivalent to: ::

            >>> runner = click.testing.CliRunner()
            >>> obj = cli._get_obj(tasks, args, kwargs)
            >>> result = runner.invoke(cli._app, clargs, obj=obj, **kw)

        + `tasks` is the `Tasks` factory to use
          (containing user commands)

        + `clargs` is a list containing the command line arguments,
          i.e what the user would send in interactive mode.

        + optional `args` and `kwargs` will be send to the `click`
          context (in context.obj['args'] and context.obj['kwargs']),
          they will not be used by the framework.

        + extra `kw` will be forwarded to
          `click.testing.CliRunner.invoke`, for example:

          ::

             input=[1,2,3], catch_exceptions=False

        creates a `click.testing.CliRunner` to invoke the main command
        and returns *runner.invoke* result.

        .. seealso:: `click.testing`
    """
    from click.testing import CliRunner
    runner = CliRunner()

    obj = _get_obj(tasks,
                   () if args is None else args,
                   {} if kwargs is None else kwargs)
    return runner.invoke(_app, clargs, obj=obj, **kw)
