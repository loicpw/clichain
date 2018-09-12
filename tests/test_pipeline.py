#!/usr/bin/env python

import clichain.pipeline as pipeline
import pytest
import sys
import logging
import ast


def test_coroutine(capsys):
    @pipeline.coroutine                                                          
    def cr(*args, **kw):                                                
        print('starting...')                                            
        try:                                                            
            while True:                                                 
                item = yield                                            
                print(f'processing: {item}')                            
        except GeneratorExit:                                           
            print('ending...')  

    assert cr.__name__ == 'cr'

    c = cr()
    print('test_coroutine #1:', file=sys.stderr)
    captured = capsys.readouterr()
    print(captured.out, file=sys.stderr)
    assert captured.out == 'starting...\n'


def test_task(capsys):
    @pipeline.task
    def output(ctrl):
        with ctrl:
            while True:
                print((yield))
    
    assert output.__name__ == 'output'

    @pipeline.task
    def parse(ctrl):
        with ctrl as push:
            while True:
                value = ast.literal_eval((yield))
                push(value)
    
    @pipeline.task
    def offset(ctrl, offset):
        offset = int(offset)
        print(f'offset: {offset}')
    
        with ctrl as push:
            while True:
                value = yield
                push(value + offset)
    
        print('offset task finished, no more value')

    # create partial coroutines
    out = output()
    assert out.__name__ == 'output'

    off1 = offset(10)
    off2 = offset(offset=100)
    proc = parse()

    # create coroutines
    ctx = pipeline.Context()
    out = out(context=ctx, targets=[])
    assert out.__name__ == 'output'

    off1 = off1(context=ctx, targets=(out,))
    off2 = off2(context=ctx, targets=(out,))
    proc = proc(context=ctx, targets=[off1, off2])

    for v in map(str, range(3)):
        proc.send(v)

    proc.close()
    off1.close()
    off2.close()
    out.close()

    captured = capsys.readouterr()
    print('test_task #1:', file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
offset: 10
offset: 100
10
100
11
101
12
102
offset task finished, no more value
offset task finished, no more value
"""


# TODO -->> test push after main loop
# should raise StopIteration ?




def test_task_error(capsys, caplog):
    @pipeline.task
    def output(ctrl):
        print('start output')
        with ctrl:
            while True:
                print((yield))
        print('end output')
    
    @pipeline.task
    def compute(ctrl):
        print('start compute', ctrl.name)
    
        prev = None
        with ctrl as push:
            while True:
                value = yield
                if prev is not None:
                    push(value / prev)
                prev = value
    
        print('compute finished', ctrl.name)

    def test(**kw):
        out = output()
        comp = compute()

        ctx = pipeline.Context()
        out = out(context=ctx)
        comp = comp(context=ctx, targets=(out, ), **kw)
        try:
            for v in [2, 1, 0, -1, -2]:
                comp.send(v)
        except Exception as e:
            err = e
        out.close()
        comp.close()
        assert str(err) == 'division by zero'
        assert isinstance(err, ZeroDivisionError)

    stdout = """\
start output
start compute {name}
0.5
0.0
end output
"""

    test()
    captured = capsys.readouterr()
    print('test_task_err #1: out:', file=sys.stderr)
    print(captured.out, file=sys.stderr)
    print('test_task_err #1: err:', file=sys.stderr)
    print(captured.err, file=sys.stderr)
    assert captured.out == stdout.format(name='<noname>')
    assert any(map(lambda r: r.name == pipeline.logger.getChild('<noname>').name and
                             r.msg == "an exception occured:" and
                             r.exc_info,
                   caplog.records))

    assert "ZeroDivisionError: division by zero" in caplog.text

    # test add debug name
    test(debug='DEBUG')
    captured = capsys.readouterr()
    print('test_task_err #2: out:', file=sys.stderr)
    print(captured.out, file=sys.stderr)
    print('test_task_err #2: err:', file=sys.stderr)
    print(captured.err, file=sys.stderr)
    assert captured.out == stdout.format(name='DEBUG')
    assert any(map(lambda r: r.name == pipeline.logger.getChild('DEBUG').name and
                             r.msg == "an exception occured:" and
                             r.exc_info,
                   caplog.records))


def test_run_trivial_pipeline(capsys):
    """ example: ::

            inp >>> a --> b --> c --> d >>> out
    """
    @pipeline.coroutine
    def output(targets, **kw):
        try:
            while True:
                for t in targets:
                    t.send('RESULT: {}'.format((yield)))
        except GeneratorExit:
            return

    @pipeline.task
    def parse(ctrl):
        with ctrl as push:
            while True:
                try:
                    value = ast.literal_eval((yield))
                except (SyntaxError, ValueError):
                    continue
                push(value)

    @pipeline.task
    def offset(ctrl, off):
        name = f'{ctrl.name}({off})'
        print(f'{name}: starting')
        with ctrl as push:
            while True:
                push((yield) + off)
        print(f'{name}: ending')


    pl = pipeline.create({
        'a': parse(),
        'b': {'task': offset(1), 'input': 'a'},
        'c': {'task': offset(2), 'input': 'b'},
        'd': {'task': output, 'input': 'c'},
    })

    inputs = """
1
2
3
4
"""

    pl.run(inputs)
    captured = capsys.readouterr()
    print("=>> test_run_trivial_pipeline #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
c(2): starting
b(1): starting
RESULT: 4
RESULT: 5
RESULT: 6
RESULT: 7
b(1): ending
c(2): ending
"""


def test_run_trivial_pipeline_error(capsys, caplog):
    """ example: ::

            inp >>> a --> b --> c --> d >>> out
    """
    @pipeline.coroutine
    def output(targets, **kw):
        try:
            while True:
                for t in targets:
                    t.send('RESULT: {}'.format((yield)))
        except GeneratorExit:
            return

    @pipeline.task
    def parse(ctrl):
        with ctrl as push:
            while True:
                try:
                    value = ast.literal_eval((yield))
                except (SyntaxError, ValueError):
                    continue
                push(value)

    @pipeline.task
    def offset(ctrl, off, err=False):
        name = f'{ctrl.name}({off})'
        print(f'{name}: starting')
        with ctrl as push:
            while True:
                value = (yield) + off
                if err and value > 5:
                    raise RuntimeError(name)
                push(value)
        print(f'{name}: ending')


    pl = pipeline.create({
        'a': parse(),
        'b': {'task': offset(1), 'input': 'a', 'debug': 'TASK B'},
        'c': {'task': offset(2, err=True), 'input': 'b', 'debug': 'TASK C'},
        'd': {'task': output, 'input': 'c'},
    })

    inputs = """
1
2
3
4
"""

    try:
        pl.run(inputs)
    except Exception as e:
        err = e
    assert str(err) == 'TASK C(2)'

    captured = capsys.readouterr()
    print("=>> test_run_trivial_pipeline_error #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
TASK C(2): starting
TASK B(1): starting
RESULT: 4
RESULT: 5
"""

    assert any(map(lambda r: r.name == pipeline.logger.getChild('TASK C').name and
                             r.msg == "an exception occured:" and
                             r.exc_info,
                   caplog.records))
    assert any(map(lambda r: r.name == pipeline.logger.getChild('TASK B').name and
                             r.msg == "failing (RuntimeError: TASK C(2))" and
                             not r.exc_info,
                    caplog.records))
    assert any(map(lambda r: r.name == pipeline.logger.getChild('a').name and
                             r.msg == "failing (RuntimeError: TASK C(2))" and
                             not r.exc_info,
                    caplog.records))


def test_run_trivial_pipeline_error_specify_context(capsys, caplog):
    """ example: ::

            inp >>> a --> b --> c --> d >>> out
    """
    @pipeline.coroutine
    def output(targets, **kw):
        try:
            while True:
                for t in targets:
                    t.send('RESULT: {}'.format((yield)))
        except GeneratorExit:
            return

    @pipeline.task
    def parse(ctrl):
        print(f'context obj: {ctrl.context.obj}')
        with ctrl as push:
            while True:
                try:
                    value = ast.literal_eval((yield))
                except (SyntaxError, ValueError):
                    continue
                push(value)

    @pipeline.task
    def offset(ctrl, off, err=False):
        name = f'{ctrl.name}({off})'
        print(f'{name}: starting')
        with ctrl as push:
            while True:
                value = (yield) + off
                if err and value > 5:
                    raise RuntimeError(name)
                push(value)
        print(f'{name}: ending')


    logger = logging.getLogger('RUN1')
    obj = 'test RUN1'
    pl = pipeline.create({
        'a': parse(),
        'b': {'task': offset(1), 'input': 'a', 'debug': 'TASK B'},
        'c': {'task': offset(2, err=True), 'input': 'b', 'debug': 'TASK C'},
        'd': {'task': output, 'input': 'c'},
    }, logger=logger, obj=obj)

    inputs = """
1
2
3
4
"""

    try:
        pl.run(inputs)
    except Exception as e:
        err = e
    assert str(err) == 'TASK C(2)'

    captured = capsys.readouterr()
    print("=>> test_run_trivial_pipeline_error_specify_context #1:",
          file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
TASK C(2): starting
TASK B(1): starting
context obj: test RUN1
RESULT: 4
RESULT: 5
"""

    assert any(map(lambda r: r.name == logger.getChild('TASK C').name and
                             r.msg == "an exception occured:" and
                             r.exc_info,
                   caplog.records))
    assert any(map(lambda r: r.name == logger.getChild('TASK B').name and
                             r.msg == "failing (RuntimeError: TASK C(2))" and
                             not r.exc_info,
                    caplog.records))
    assert any(map(lambda r: r.name == logger.getChild('a').name and
                             r.msg == "failing (RuntimeError: TASK C(2))" and
                             not r.exc_info,
                    caplog.records))


@pytest.fixture
def job():
    @pipeline.task
    def job(ctrl):
        print(f'{ctrl.name}: starting')
        with ctrl as push:
            while True:
                value = (yield)
                push(f'{value}->{ctrl.name}')
        print(f'{ctrl.name}: ending')

    return job


@pytest.fixture
def run_pipeline_fork_output():
    return """\
c: starting
e: starting
b: starting
d: starting
a: starting
1->a->b->c
1->a->d->e
2->a->b->c
2->a->d->e
3->a->b->c
3->a->d->e
4->a->b->c
4->a->d->e
a: ending
d: ending
b: ending
e: ending
c: ending
"""


@pytest.fixture
def inputs():
    return "1234"


def test_run_pipeline_fork(capsys, caplog, job,
                           run_pipeline_fork_output, inputs):
    """ example: ::

                      +--> B --> C >>> out
           inp >>> A--|
                      +--> D --> E >>> out
    """

    pl = {
        'a': {'task': job(), 'output': ('b', 'd')},
        'b': job(),
        'd': job(),
        'c': {'task': job(), 'input': 'b'},
        'e': {'task': job(), 'input': 'd'},
    }
    pl = pipeline.create(pl)

    pl.run(inputs)
    captured = capsys.readouterr()
    print("=>> test_run_pipeline_fork #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == run_pipeline_fork_output


def test_run_pipeline_fork_redundant(capsys, caplog, job, inputs,
                                     run_pipeline_fork_output):
    """ example: ::

                      +--> B --> C >>> out
           inp >>> A--|
                      +--> D --> E >>> out
    """
    pl = {
        'a': {'task': job(), 'input': None, 'output': ('b', 'd')},
        'b': {'task': job(), 'input': 'a', 'output': 'c'},
        'd': {'task': job(), 'input': 'a', 'output': 'e'},
        'c': {'task': job(), 'input': 'b', 'output': None},
        'e': {'task': job(), 'input': 'd', 'output': ()},
    }
    pl = pipeline.create(pl)

    pl.run(inputs)
    captured = capsys.readouterr()
    print("=>> test_run_pipeline_fork_redundant #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == run_pipeline_fork_output


def test_run_pipeline_join_branches(capsys, caplog, job, inputs):
    """ example: ::

                   +--> B --> C --+
        inp >>> A--|              +--> F >>> out
                   +--> D --> E --+
    """

    pl = {
        'a': {'task': job(), 'output': ('b', 'd')},
        'b': job(),
        'c': {'task': job(), 'input': 'b', 'output': 'f'},
        'd': job(),
        'e': {'task': job(), 'input': 'd', 'output': 'f'},
        'f': job(),
    }
    pl = pipeline.create(pl)

    pl.run(inputs)
    captured = capsys.readouterr()
    print("=>> test_run_pipeline_join_branches #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
f: starting
c: starting
e: starting
b: starting
d: starting
a: starting
1->a->b->c->f
1->a->d->e->f
2->a->b->c->f
2->a->d->e->f
3->a->b->c->f
3->a->d->e->f
4->a->b->c->f
4->a->d->e->f
a: ending
d: ending
b: ending
e: ending
c: ending
f: ending
"""


# TODO : currently NotImplemented
def test_run_pipeline_loopback(capsys, caplog, job, inputs):
    """ CURRENTLY NOT IMPLEMENTED: examples: ::
            
                       +--> B --> C --+         + >>> out
            inp >>> A--|              +--> N -- +
                       +--> D --> E --+         |
                                      |         |
                       +--> F --> G --+         |
                       |                        |
                       +------------------------+


                       +--> B --> C --+         + >>> out
            inp >>> A--|              +--> N -- +
                       +--> D --> E --+         |
                                      |         |
                             +--> F --+         |
                             |                  |
                             +------------------+
    """
    @pipeline.task
    def loopback_first(ctrl):
        print(f'{ctrl.name}: starting')
        with ctrl as push:
            value = (yield)
            push(f'{value}->{ctrl.name}')

            while True:
                yield
        print(f'{ctrl.name}: ending')

    pl1 = {
        'a': {'task': job(), 'output': ('b', 'd')},
        'b': {'task': job(), 'output': 'c'},
        'c': {'task': job()},
        'd': {'task': job(), 'output': 'e'},
        'e': {'task': job()},
        'n': {'task': job(), 'input': ('c', 'e'), 'output': None},
        'f': {'task': job(), 'input': 'n', 'output': 'g'},
        'g': {'task': loopback_first(), 'output': 'n'},
    }
    pl2 = {
        'a': {'task': job(), 'output': ('b', 'd')},
        'b': {'task': job(), 'output': 'c'},
        'c': {'task': job()},
        'd': {'task': job(), 'output': 'e'},
        'e': {'task': job()},
        'n': {'task': job(), 'input': ('c', 'e'), 'output': None},
        'f': {'task': loopback_first(), 'input': 'n', 'output': 'n'},
    }


    with pytest.raises(NotImplementedError):
        pl1 = pipeline.create(pl1)
    
        pl1.run(inputs)
        captured = capsys.readouterr()
        print("=>> test_run_pipeline_join_branches #1:", file=sys.stderr)
        print(captured.out, file=sys.stderr)
        assert captured.out == """\
TODO
"""

    with pytest.raises(NotImplementedError):
        pl2 = pipeline.create(pl2)
    
        pl2.run(inputs)
        captured = capsys.readouterr()
        print("=>> test_run_pipeline_join_branches #2:", file=sys.stderr)
        print(captured.out, file=sys.stderr)
        assert captured.out == """\
TODO
"""


def test_run_pipeline_branches_order(capsys, job, inputs):
    """ example: ::

                   +--> 1 --+
                   +--> 2 --+
        inp >>> A--+--> 3 --+--> B >>> out
                   +--> 4 --+
                   +--> 5 --+
    """

    pl = {
        'a': job(),
        1: {'task': job(), 'input': 'a', 'output': 'b'},
        2: {'task': job(), 'input': 'a', 'output': 'b'},
        3: {'task': job(), 'input': 'a', 'output': 'b'},
        4: {'task': job(), 'input': 'a', 'output': 'b'},
        5: {'task': job(), 'input': 'a', 'output': 'b'},
        'b': job(),
    }
    pl = pipeline.create(pl)

    pl.run(inputs)
    captured = capsys.readouterr()
    print("=>> test_run_pipeline_join_branches #1:", file=sys.stderr)
    print(captured.out, file=sys.stderr)
    assert captured.out == """\
b: starting
1: starting
2: starting
3: starting
4: starting
5: starting
a: starting
1->a->1->b
1->a->2->b
1->a->3->b
1->a->4->b
1->a->5->b
2->a->1->b
2->a->2->b
2->a->3->b
2->a->4->b
2->a->5->b
3->a->1->b
3->a->2->b
3->a->3->b
3->a->4->b
3->a->5->b
4->a->1->b
4->a->2->b
4->a->3->b
4->a->4->b
4->a->5->b
a: ending
5: ending
4: ending
3: ending
2: ending
1: ending
b: ending
"""
