#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" `pipeline` module provides tools to create a pipeline of tasks

    a pipeline can be composed of one or several branches, but
    everything runs in a single thread. The initial goal of this
    framework is to provide a simple and direct way of defining task
    types and reuse them in different pipeline configurations.

    *The motivation is not to parallelise tasks yet tasks could be
    parallelized in some configurations, depending on the exact use
    case and the context...*

    tasks are implemented by *coroutines* functions as described by
    David Beazle (see http://www.dabeaz.com/coroutines/ for details).

    This module is used by `clichain.cli` module.
"""

from functools import wraps
import logging
import sys
import collections


logger = logging.getLogger(__name__)


def coroutine(func):
    """ coroutine decorator, 'prime' the coroutine function

        this function is intended to be used as a decorator to create
        a basic *coroutine* function, for instance: ::

            @coroutine
            def cr(*args, **kw):
                print('starting...')
                try:
                    while True:
                        item = yield
                        print(f'processing: {item}')
                except GeneratorExit:
                    print('ending...')

        calling the decorated function will automatically get it to the
        first *yield* statement. ::

            >>> cr()
            starting...

        .. note:: the decorated function is wrapped using
            `functools.wraps`

        .. seealso:: http://www.dabeaz.com/coroutines/
    """
    @wraps(func)
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return start


class Control:
    """ Internal, 'control' obj received by `task` decorated functions

        `Control` is a context manager

        .. seealso:: `Control.__init__`
    """
    def __init__(self, context, name, targets):
        """ initialize new `Control` object

            + `context` is a `Context` object, `Control` object
              will use it to log exception if an exception occurs
              in the coroutine while used as a context manager. The
              `Context` object is also accessible through the `context`
              attribute.

            + `name` will be accessible as `name` attribute (rw)

              ex: ::

                logger = logging.getLogger(f'{__name__}.{ctrl.name}')

            + `targets` will be accessible through `targets` property
              (ro)

              .. seealso:: `Control.targets`

            `targets` is read only to ensure consistency with `push`
            function returned by `Control.__enter__`: `Control` object
            is expected to be used as a context manager: ::

                with ctrl as push:
                    while True:
                        data = yield
                        push(data)  # send data to next coroutines

            a `push` function is defined and returned when `Control` is
            used as a context manager, but can actually be created using
            `Control.push` property.

            the purpose is to force using an efficient solution avoiding
            attributes lookup (using *self*) for every call, which has
            an impact given this function is likely to be called a lot
            (usually for each processed item). This way we define the
            function and reference it once in the user function (as
            'push' in the example).

            .. seealso:: `task` decorator
        """
        self.context = context
        self.name = name
        self._targets = targets

    @property
    def push(self):
        """ return a 'push' function sending data to next coroutines

            .. seealso:: `Control.__init__`
        """
        def push(value, targets=self.targets):
            """ send `value` to the following coroutines in the pipeline

                given 'targets' is an iterable containing the next
                coroutines, this is equivalent to:

                    for t in targets:
                        t.send(value)
            """
            for t in targets:
                t.send(value)

        return push

    def __enter__(self):
        """ return push function

            .. seealso:: `Control.push`, `Control.__exit__`
        """
        return self.push

    def __exit__(self, tpe, value, tb):
        """ handle GeneratorExit exception and log unhandled exceptions

            `Control` object is created by `task` decorator, the
            decorated function gets the `Control` object as first arg,
            and is expected to use it as a context manager, which will
            handle GeneratorExit and log any unhandled exception.

            `context` attribute (`Context` object) will be used if the
            exception is not `None` or `GeneratorExit`, in order to:

            + determine if the exception traceback should be logged,
              if the exception has already been logged by another
              `Control` object (i.e in another coroutine), then only
              an error message will be logged, otherwise the full
              exception will be recorded.

            + get the base logger to use

            .. seealso:: `task`, `Control.__init__`, `Context`
        """
        if isinstance(value, GeneratorExit):
            return True

        ctx = self.context
        lgr = ctx.logger.getChild(self.name)

        if value in ctx.exceptions:
            lgr.error(f'failing ({tpe.__name__}: {value})')
        else:
            lgr.error('an exception occured:', exc_info=(tpe, value, tb))
            ctx.exceptions.append(value)

    @property
    def targets(self):
        """ next coroutines in the pipeline """
        return self._targets


def task(func):
    """ make "partial" `coroutines` expected to be used with `create`.

        `task` will create a "partial" function, which when
        called with args and keyword args will actually return a
        `coroutine` function designed to be used with `create` function.

        example:

        a basic coroutine adding offset to input data could be defined
        as follows using `task`: ::

            @task
            def offset(ctrl, offset):
                print('pre-processing')

                with ctrl as push:
                    while True:
                        value = yield
                        push(value + offset)

                # will be executed unless an exception occurs in
                # the 'while' loop
                print('post_processing')

        + `ctrl` will handle the `GeneratorExit` exception and log any
          unhandled exception.

        + the `push` method send data to the next coroutines in the
          pipeline.

        the resulting function is called with the original function's
        args and keyword args: ::

            off = offset(offset=1)

        *off* is a partial `coroutine` function expected to be used in a
        pipeline defintion with `create`.

        the coroutine will eventually be created calling this new
        function with specific arguments depending on the pipeline
        specification (see `create` for details), ex: ::

            # create the coroutine
            off = off(targets=[t1, t2...])

        .. note:: as for `coroutine`, all the functions (partial or
            final functions) are wrapped using `functools.wraps`


        **example:**

        ::

            @task
            def output(ctrl):
                with ctrl:
                    while True:
                        print((yield))

            @task
            def parse(ctrl):
                with ctrl as push:
                    while True:
                        try:
                            value = ast.literal_eval((yield))
                        except (SyntaxError, ValueError):
                            continue
                        push(value)

            @task
            def offset(ctrl, offset):
                offset = int(offset)
                logger = logging.getLogger(f'{__name__}.{ctrl.name}')
                logger.info(f'offset: {offset}')

                with ctrl as push:
                    while True:
                        value = yield
                        push(value + offset)

                logger.info('offset task finished, no more value')

            if __name__ == '__main__':
                out = output()
                off1 = offset(10)
                off2 = offset(offset=100)
                parse = parse()

                # the previous results (out, off1, off2, proc) should
                # be used in the pipeline definition and the followings
                # should be performed by "create"
                out = out()
                off1 = off1((out,))
                off2 = off2((out,))
                parse = parse([off1, off2])

                with open('foo.txt') as inputs:
                    for data in inputs:
                        parse.send(data)

                out.close()
                off1.close()
                off2.close()
                parse.close()

        .. seealso:: `coroutine`, `create`
    """
    @coroutine
    @wraps(func)
    def _task(context, targets=None, debug='<noname>', args=None, kwargs=None):
        ctrl = Control(
            context=context,
            name=debug,
            targets=[] if targets is None else targets,
        )

        return func(ctrl,
                    *(() if args is None else args),
                    **({} if kwargs is None else kwargs))

    @wraps(func)
    def task(*args, **kwargs):
        @wraps(func)
        def _partial(*_args, **_kwargs):
            return _task(*_args, **_kwargs, args=args, kwargs=kwargs)
        return _partial

    return task


class Context:
    """ will be passed to all `coroutine`s in the pipeline

        `Context` object is a common object shared by all coroutines in
        the pipeline.

        attributes:

        + `exceptions` is a list which remains empty until an exception
          occurs within a `task` and is handled by the module. Then
          `exception` contains each exception caught by the module.
          Each exception is logged only one time with its traceback when
          it's caught by `Control` context manager.

          .. note:: if an exception is caught by the module it will be
            "re-raised" thus terminate the process but user code could
            still raise another exception(s) for example if a coroutine
            is not implemented using `task` or GeneratorExit is handled
            within the user loop...

        + `logger` will be used for every message logged by the module,
          and can be used by the user. The default is to use the
          module's `logger`.

        + `obj` attribute is an arbitrary object provided by the user
          when creating the pipeline. The default is `None`.

        .. seealso:: `create`
    """
    def __init__(self, logger=logger, obj=None):
        """ init the `Context` which will be shared by coroutines """
        self.logger = logger
        self.exceptions = []
        self.obj = obj


def create(tasks, output=print, **kw):
    """ create a pipeline of coroutines from a specification

        a pipeline is a succession of coroutines organized into one
        or several branches.

        `output` is a strategy to use for the pipeline output, the
        default strategy is `print`. `output` will be called for each
        data reaching the pipeline's output, it takes a single argument.

        **extra keyword args** will be used to initialize the `Context`
        object that will be send to all the coroutines of the pipeline.

        `tasks` argument describes the pipeline and consists of a
        mapping of coroutines as key: value pairs, where each single key
        identifies a single coroutine.

        each coroutine is defined either by a single `coroutine`
        function (see **task** field below) or a dictionnay, which
        contains the following fields:

        + **task**: the coroutine function to use

          the coroutine function will be called with the following
          keyword arguments:

          + **context**: the `Context` object shared by all the
            coroutines of the pipeline.

          + **targets**: an iterable containing the following coroutines
            in the pipeline (default is no targets).

          + **debug**: an optional name used to get a child logger from
            the `Context` logger, which will be used to log error if an
            exception occurs. The exception will be logged at error
            level and the exc_info will be passed to the log record.

            The value will be accessible (and writeable) through
            `Control.name` attribute, which can be usefull for logging:

            ex: ::

                logger = logging.getLogger(f'{__name__}.{ctrl.name}')

            .. note:: Default value is the coroutine's key in the
                pipeline definition (default will be used if value is
                `None` or an empty string).

        + **input**: (optional) set this coroutine as a 'target' of the
          coroutine(s) defined by **input**. **input** can be a single
          key or an iterable containing keys of other coroutines defined
          in the pipeline dictionnary.

          .. note:: `None` value will be interpreted as the pipeline's
            main input. No value or an empty list is equivalent as None
            if this coroutine is not specified as **output** of an other
            coroutine in the pipeline.

        + **output**: (optional) set the coroutine(s) whose keys are
          defined in **output** as a 'target' of this coroutine.
          **output** can be a single key or an iterable containing keys
          of other coroutines defined in the pipeline dictionnary.

          .. note:: `None` value will be interpreted as the pipeline's
            main output. No value or an empty list is equivalent as None
            if this coroutine is not specified as **input** of an other
            coroutine in the pipeline.

        + **debug**: (optional) a debug name to use in logging if an
          unhandled exception occurs. see above description.

        .. note:: specifying a coroutine by a `coroutine` function is
          equivalent as providing a dictionnary containing only the
          **task** field.


        **examples:**

        .. seealso:: `task`, `coroutine`

        given we have the following declarations: ::

            @coroutine
            def output(targets, **kw):
                try:
                    while True:
                        for t in targets:
                            t.send('RESULT: {}'.format((yield)))
                except GeneratorExit:
                    return

            @task
            def parse(ctrl):
                with ctrl as push:
                    while True:
                        try:
                            value = ast.literal_eval((yield))
                        except (SyntaxError, ValueError):
                            continue
                        push(value)

            @task
            def mytask(ctrl, param):
                logger = logging.getLogger(f'{__name__}.{ctrl.name}')
                logger.info('starting task')
                with ctrl as push:
                    while True:
                        [...]
                logger.info('finishing task')

        + defining a pipeline composed of a single sequence:

          example: ::

            inp >>> a --> b --> c --> d >>> out

          here's how we could define it: ::

            pipeline = pipeline.create({
                'a': parse(),
                'b': {'task': mytask(1), 'input': 'a'},
                'c': {'task': mytask(2), 'input': 'b'},
                'd': {'task': output, 'input': 'c'},
            })

          the created pipeline is a `Pipeline` object, it can be run
          over any input generator using its 'Pipeline.run' method,
          sending data to stdout by default.

          .. seealso:: `Pipeline.run`

        + define a pipeline with branches:

          example: ::

                       +--> B --> C >>> out
            inp >>> A--|
                       +--> D --> E >>> out

          here's how we could define it: ::

            pipeline = pipeline.create({
                'a': {'task': A, 'output': ('b', 'd')},
                'b': B,
                'd': D,
                'c': {'task': C, 'input': 'b'},
                'e': {'task': E, 'input': 'd'},
            })

          redoundant specification is not an issue, and the following
          example is equivalent to the previous one: ::

            pipeline = pipeline.create({
                'a': {'task': A, 'output': ('b', 'd')},
                'b': {'task': B, 'input': 'a', 'output': 'c'},
                'd': {'task': D, 'input': 'a', 'output': 'e'},
                'c': {'task': C, 'input': 'b', 'output': None},
                'e': {'task': E, 'input': 'd', 'output': ()},
            })

        + join branches

          example: given we want to implement this: ::

                       +--> B --> C --+
            inp >>> A--|              +--> N >>> out
                       +--> D --> E --+

          here's how we could define it: ::

            pipeline = pipeline.create({
                'a': {'task': A, 'output': ('b', 'd')},
                'b': B,
                'c': {'task': C, 'input': 'b', 'output': 'f'},
                'd': D,
                'e': {'task': E, 'input': 'd', 'output': 'f'},
                'f': F,
            })

        + control branches order

          the order in which coroutines are initialized, called and
          closed is reproducible.

          to control the data flow order between several branches just
          use the keys in the pipeline definition, as they will be
          sorted, like in the following example: ::

                       +--> (1) X --+
                       +--> (2) X --+
            inp >>> A--+--> (3) X --+--> B >>> out
                       +--> (4) X --+
                       +--> (5) X --+

          here's how we could define it: ::

            pipeline = pipeline.create({
                'a': A,
                1: {'task': X, 'input': 'a', 'output': 'b'},
                2: {'task': X, 'input': 'a', 'output': 'b'},
                3: {'task': X, 'input': 'a', 'output': 'b'},
                4: {'task': X, 'input': 'a', 'output': 'b'},
                5: {'task': X, 'input': 'a', 'output': 'b'},
                'b': B,
            })

          the 'X' coroutines will be initialized and processed in the
          expected order: 1, 2, 3, 4, 5 (they will be closed, if no
          exception occurs, in the opposite order).

        + loop back

          .. warning:: looping is currently not implemented and will
            raise a `NotImplementedError` when creating the pipeline.

          example: given we want to implement this: ::

                       +--> B --> C --+         + >>> out
            inp >>> A--|              +--> N -- +
                       +--> D --> E --+         |
                                      |         |
                             +--> F --+         |
                             |                  |
                             +------------------+

          here's how we could define it: ::

            pipeline = pipeline.create({
                'a': {'task': A, 'output': ('b', 'd')},
                'b': {'task': B, 'output': 'c'},
                'c': {'task': C},
                'd': {'task': D, 'output': 'e'},
                'e': {'task': E},
                'n': {'task': N, 'input': ('c', 'e'), 'output': None},
                'f': {'task': F, 'input': 'n', 'output': 'n'},
            })

          .. warning:: defining a loop can end up in an infinite recursion
              , no control is done on this, so it's up to the tasks
              implementation to handle this...

        + specify coroutines name

          in some contexts we may want to define a name for a coroutine
          which is different from its key.

          example: the previous example with ordered branches was: ::

                       +--> (1) X --+
                       +--> (2) X --+
            inp >>> A--+--> (3) X --+--> B >>> out
                       +--> (4) X --+
                       +--> (5) X --+

          here's how we could define it: ::

            pl = {
                'a': A,
                'b': B,
            }

            pl.update({
               i: {'task': X, 'input': 'a', 'output': 'b',
                   'debug': f"the X task number {i}"}
               for i in range(1, 6)
            })

            pl = pipeline.create(pl)
    """
    # ---------------------------------------------------------------- #
    # prepare coroutines
    # ---------------------------------------------------------------- #

    # NOTE: use OrderedDict to get reproducible outputs
    steps = collections.OrderedDict()  # <key>: <default>

    def default():
        return {
            'task': None,
            'input': set(),
            'output': set(),
        }

    for key, tsk in tasks.items():
        if key is None:
            raise ValueError('coroutine key cannot be None (reserved)')

        step = steps.setdefault(key, default())
        _inputs = _outputs = ()
        debug = str(key)

        if isinstance(tsk, collections.Mapping):
            _inputs = tsk.get('input', ())
            _outputs = tsk.get('output', ())
            debug = tsk.get('debug', debug)
            tsk = tsk['task']

        _inputs = _listify(_inputs)
        _outputs = _listify(_outputs)
        step['task'] = tsk
        step['debug'] = debug

        # by default if a coroutine has no input or no output the
        # pipeline input / output will be used

        # we also need to make sure coroutines are not added twice as
        # input / output of a given coroutine

        # in order to do that we link everything (except None)
        # using 'output':

        # iterate 'inputs' and add to 'input' only if None (i.e pipeline
        # input), else add to 'output' of the coroutine specified as
        # 'input'
        for inp in _inputs:
            if inp is None:
                step['input'].add(None)
            else:
                _in = steps.setdefault(inp, default())
                _in['output'].add(key)

        step['output'].update(_outputs)

        # debug checks
        assert key not in step['output'], 'coroutine output is itself'
        assert key not in step['input'], 'coroutine input is itself'

    # ---------------------------------------------------------------- #
    # create context
    # ---------------------------------------------------------------- #
    context = Context(**kw)

    # ---------------------------------------------------------------- #
    # prepare pipeline input / output
    # ---------------------------------------------------------------- #

    @coroutine
    def main_input(targets):
        try:
            while True:
                data = yield
                for target in targets:
                    target.send(data)
        except GeneratorExit:
            return

    @coroutine
    def main_output(strategy):
        try:
            while True:
                strategy((yield))
        except GeneratorExit:
            return

    main_output = main_output(output)
    pipeline = [main_output]

    # ---------------------------------------------------------------- #
    # link coroutines
    # ---------------------------------------------------------------- #

    lst = list(steps)
    loop = {}  # to detect loopback in the pipeline (not implemented)
    while lst:
        key = lst.pop(0)
        data = steps[key]
        output = data['output']

        # set default output if branch has no output
        targets = [main_output] if not output or None in output else []

        # NOTE: use sorted to get reproducible outputs
        for _out in sorted(output.difference({None}), key=str):
            # add the current coroutine as input of the target coroutine
            # so we know it has at least one input (otherwise the
            # pipeline input will be used, see below...)
            target = steps[_out]
            target['input'].add(key)

            if _out in lst:
                # the target coroutine has not been initialized yet
                # it will be initialized first
                break

            targets.append(target['task'])

        # skip for now if at least one target coroutine has not been
        # initialized yet
        if len(targets) < len(output):
            # detect loopback in the pipeline:
            # this is currently not implemented and will fail
            try:
                if loop[key] == len(lst):
                    raise NotImplementedError('recursion detected: looping is '
                                              'currently not implemented')
            except KeyError:
                pass
            loop[key] = len(lst)

            # skip and go back later to this one
            lst.append(key)
            continue

        # the coroutine can be initialized
        # ( NOTE: this will start the user generator function )
        tsk = data['task']
        cr = tsk(context=context, targets=targets, debug=data['debug'])
        data['task'] = cr
        pipeline.append(cr)

    # link pipeline input
    input_targets = []
    for key, data in steps.items():
        # link coroutine to pipeline input:
        # + if coroutine has no input, or
        # + if pipeline input (None) is specified in coroutine's inputs
        if not data['input'] or None in data['input']:
            input_targets.append(data['task'])

    pipeline.append(main_input(input_targets))
    pipeline.reverse()
    return Pipeline(pipeline)


def _listify(obj):
    """ makes sure `obj` is a `list` """
    if isinstance(obj, str):
        return [obj]
    try:
        # will fail if obj is not iterable
        return list(obj)
    except TypeError:
        return [obj]


class Pipeline:
    """ User interface returned by `create` function

        `Pipeline` object contains the `coroutine`s of a pipeline.

        When used as a context manager, it ensures that coroutines
        will be closed immediately at the end of the process.

        .. seealso:: `Pipeline.__enter__`, `Pipeline.__exit__`

        `Pipeline` also has an additional `Pipeline.run` method
        which can be called to run the pipeline over an input
        stream and wait until the process complete.
    """
    def __init__(self, targets):
        """ initialize a new pipeline with `coroutine`s

            `targets` is an iterable containing the coroutines of the
            pipeline, the first item must be the input coroutine.

            .. seealso:: `Pipeline.run`
        """
        self.targets = targets

    def run(self, inputs):
        """ run the pipeline over `inputs` iterator

            send data from `inputs` to the pipeline until their is no
            more data in inputs or an exception occurs.
        """
        with self as process:
            for data in inputs:
                process(data)

    def __enter__(self):
        """ return a function sending data thtough the pipeline

            ex: ::

                with pipeline as process:
                    for data in stream:
                        process(data)

            .. note:: this is equivalent to:

                ::

                    with pipeline:
                        target = pipeline.target
                        for data in stream:
                            target.send(data)

            .. seealso:: `Pipeline.__exit__`
        """
        def send(data, target=self.targets[0]):
            target.send(data)

        return send

    def __exit__(self, tpe, value, tb):
        """ close all the coroutines of the pipeline, raise exc if any

            The purpose of using the `Pipeline` object as a context
            manager is essentially to make sure all the coroutines will
            be terminated (closed) at the end of the process.

            This can be critical if user functions are expected to do
            some teardown jobs after processing data, for instance: ::

                # file won't be closed until the coroutine is closed
                # (see while loop...)

                @coroutine
                def cr(targets, *args, file, **kw):
                    with open(file) as f:
                        while True:
                            data = yield
                            [...]

            .. seealso:: `Pipeline.__enter__`
        """
        for coroutine in self.targets:
            coroutine.close()
