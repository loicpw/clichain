#!/usr/bin/env python

import pytest
from clichain import cli, pipeline
import click
from click.testing import CliRunner
import sys
import ast
import logging
from difflib import SequenceMatcher


def test_main_help():
    tasks = cli.Tasks()
    args = ['--help']
    result = cli.test(tasks, args)
    print('>> test_main_help #1:\n', result.output, file=sys.stderr)
    assert result.exit_code == 0
    assert not result.exception
    ratio = SequenceMatcher(None, result.output, cli.usage()).ratio()
    assert ratio >= 0.8


def test_basic_single_task_help():
    tasks = cli.Tasks()
    
    @tasks
    @click.command(name='compute')
    @click.option('--approximate', '-a',
                  help='compute with approximation')
    @click.argument('y')
    def compute_task_cli(approximate, y):
        " divide data by 'y' "
        pass

    args = ['compute', '--help']
    result = cli.test(tasks, args)
    print('>> test_basic_single_task_help #1:\n', result.output, file=sys.stderr)
    assert result.exit_code == 0
    assert not result.exception

    usage = """\
Usage: _app compute [OPTIONS] Y

  divide data by 'y'

Options:
  -a, --approximate TEXT  compute with approximation
  --help                  Show this message and exit.
"""
    ratio = SequenceMatcher(None, result.output, usage).ratio()
    assert ratio >= 0.8


def test_basic_single_sequence():
    inputs = '1\n2\n3\n' 

    tasks = cli.Tasks()

    @pipeline.task
    def compute_task(ctrl, y):
        with ctrl as push:
            while True:
                push((yield) / y)

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

    @tasks
    @click.command(name='compute')
    @click.option('--approximate', '-a',
                  help='compute with approximation')
    @click.argument('y')
    def compute_task_cli(approximate, y):
        " divide data by 'y' "
        y = ast.literal_eval(y)
        if y == 0:
            raise click.BadParameter("can't devide by 0")
        if approximate:
            y = round(y)
        return compute_task(y)

    args = ['compute', '0']
    result = cli.test(tasks, args, input=inputs, catch_exceptions=False)
    print('>> test_basic_single_sequence #1:\n', result.output, file=sys.stderr)

    usage = """\
Usage: _app compute [OPTIONS] Y

Error: Invalid value: can't devide by 0
"""
    ratio = SequenceMatcher(None, result.output, usage).ratio()
    assert ratio >= 0.8

    args = ['parse', 'compute', '10']
    result = cli.test(tasks, args, input=inputs, catch_exceptions=False)
    print('>> test_basic_single_sequence #2:\n', result.output, file=sys.stderr)
    assert result.output == """\
0.1
0.2
0.3
"""

def _get_pipeline(args, inputs, err_msg=None):
    tasks = cli.Tasks()
    
    @pipeline.task
    def compute_task(ctrl, name, err):
        print(f'starting {name} (coroutine name: {ctrl.name})')

        with ctrl as push:
            while True:
                value = yield
                if isinstance(value, str) and '7' in value and err:
                    raise RuntimeError(name if err_msg is None else err_msg)
                push(f'{value.strip()}->{name}')

        print(f'finished {name} (coroutine name: {ctrl.name})')
    
    @tasks
    @click.command(name='task')
    @click.argument('name')
    @click.option('--err', '-e', is_flag=True)
    def compute_task_cli(name, err):
        return compute_task(name, err)

    def test():
        result = cli.test(tasks, args.split(), input=inputs,
                          catch_exceptions=False)
        return result

    return test


def test_pipeline_one_level_split_and_join():
    """
                   +--> B --> C --+                                         
        inp >>> A--|              +--> F >>> out                            
                   +--> D --> E --+  

    
        =>> A [ B C , D E ] F 
    """
    inputs = '\n'.join('12345678')
    args = 'task A [ task B task C , task D task E ] task F'
    name = 'test_pipeline_one_level_split_and_join'

    test = _get_pipeline(args, inputs)
    result = test()
    output = result.output
    print(f'>> {name} #1:\n', output, file=sys.stderr)
    assert output == """\
starting F (coroutine name: 3)
starting C (coroutine name: 1)
starting E (coroutine name: 2)
starting B (coroutine name: 1_0)
starting D (coroutine name: 2_0)
starting A (coroutine name: 0)
1->A->B->C->F
1->A->D->E->F
2->A->B->C->F
2->A->D->E->F
3->A->B->C->F
3->A->D->E->F
4->A->B->C->F
4->A->D->E->F
5->A->B->C->F
5->A->D->E->F
6->A->B->C->F
6->A->D->E->F
7->A->B->C->F
7->A->D->E->F
8->A->B->C->F
8->A->D->E->F
finished A (coroutine name: 0)
finished D (coroutine name: 2_0)
finished B (coroutine name: 1_0)
finished E (coroutine name: 2)
finished C (coroutine name: 1)
finished F (coroutine name: 3)
"""


def test_pipeline_two_levels_split_and_join():
    """
                            +--> C1 --+                                     
                   +--> B --|         +-----+                               
                   |        +--> C2 --+     |                               
        inp >>> A--|                        +--> F >>> out                  
                   +--> D --> E ------------+ 

        =>> A [ B [ C1 , C2 ] , D E ] F
    """
    inputs = '\n'.join('12345678')
    args = 'task A [ task B [ task C1 , task C2 ] , task D task E ] task F'
    name = 'test_pipeline_two_levels_split_and_join'

    test = _get_pipeline(args, inputs)
    result = test()
    output = result.output
    print(f'>> {name} #1:\n', output, file=sys.stderr)
    assert output == """\
starting F (coroutine name: 5)
starting C1 (coroutine name: 2)
starting C2 (coroutine name: 3)
starting E (coroutine name: 4)
starting B (coroutine name: 1)
starting D (coroutine name: 4_0)
starting A (coroutine name: 0)
1->A->B->C1->F
1->A->B->C2->F
1->A->D->E->F
2->A->B->C1->F
2->A->B->C2->F
2->A->D->E->F
3->A->B->C1->F
3->A->B->C2->F
3->A->D->E->F
4->A->B->C1->F
4->A->B->C2->F
4->A->D->E->F
5->A->B->C1->F
5->A->B->C2->F
5->A->D->E->F
6->A->B->C1->F
6->A->B->C2->F
6->A->D->E->F
7->A->B->C1->F
7->A->B->C2->F
7->A->D->E->F
8->A->B->C1->F
8->A->B->C2->F
8->A->D->E->F
finished A (coroutine name: 0)
finished D (coroutine name: 4_0)
finished B (coroutine name: 1)
finished E (coroutine name: 4)
finished C2 (coroutine name: 3)
finished C1 (coroutine name: 2)
finished F (coroutine name: 5)
"""


def test_pipeline_debug_name(caplog):
    """
                   +--> B --> C --+
        inp >>> A--|              +--> B >>> out
                   +--> B --> D --+

        #equivalent:
        =>> A { 'b1' [ B C , B D ] } B
        =>> A [ { 'b1' B C , B D } ] B
        =>> A [ { 'b1' B C , B D ] } B
        =>> A [ { 'b1' B C } , { 'b1' B D } ] B

        #
        =>> A [ { 'b1' B } C , { 'b1' B } D ] B

        #equivalent:
        =>> A { 'b1' [ B C , { 'b2' B } D ] } B
        =>> A [ { 'b1' B C } , { 'b2' B } { 'b1' D } ] B

        #no effect:
        =>> A [ { 'b1' } B , { 'b2' } B ] B
    """
    inputs = '\n'.join('12345678')
    name = 'test_pipeline_debug_name'

    def _test(ex, i, args, stdout, err_name='{NAME}'):
        print('', file=sys.stderr)
        err_name = err_name.format(NAME=f'{ex}_{i}')
        args = args.format(NAME=f'{ex}_{i}')
        test = _get_pipeline(args, inputs, err_msg=err_name)
        result = test()
        # abort:
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 1

        print(f'\n>> {name}-{ex}#{i}: out:', file=sys.stderr)
        print(result.output, file=sys.stderr)
        assert result.output == stdout.format(NAME=f'{ex}_{i}')

        
        print(f'\n>> {name}-{ex}#{i}: logs:', file=sys.stderr)
        _logger = pipeline.logger.getChild(err_name)
        print(caplog.text, file=sys.stderr)
        assert any(map(lambda r: r.name == _logger.name and
                                 r.msg == "an exception occured:" and
                                 r.exc_info,
                       caplog.records))
        assert f"RuntimeError: {err_name}" in caplog.text

    # ---------------------------------------------------------------- #
    # equivalent:
    # =>> A { 'b1' [ B C , B D ] } B
    # =>> A [ { 'b1' B C , B D } ] B
    # =>> A [ { 'b1' B C , B D ] } B
    # =>> A [ { 'b1' B C } , { 'b1' B D } ] B
    # ---------------------------------------------------------------- #
    ex = 'ex_1'
    # ---------------------------------------------------------------- #
    args = [
        'task A {{ {NAME} [ task -e B task C , task B task D ] }} task B ',
        'task A [ {{ {NAME} task -e B task C , task B task D }} ] task B',
        'task A [ {{ {NAME} task -e B task C , task B task D ] }} task B',
        'task A [ {{ {NAME} task -e B task C }} , {{ {NAME} task B task D }} ] task B',
    ]

    stdout = """\
starting B (coroutine name: 3)
starting C (coroutine name: {NAME})
starting D (coroutine name: {NAME})
starting B (coroutine name: {NAME})
starting B (coroutine name: {NAME})
starting A (coroutine name: 0)
1->A->B->C->B
1->A->B->D->B
2->A->B->C->B
2->A->B->D->B
3->A->B->C->B
3->A->B->D->B
4->A->B->C->B
4->A->B->D->B
5->A->B->C->B
5->A->B->D->B
6->A->B->C->B
6->A->B->D->B
finished B (coroutine name: {NAME})
finished D (coroutine name: {NAME})
finished C (coroutine name: {NAME})
finished B (coroutine name: 3)
Aborted!
"""

    for i, args in enumerate(args):
        _test(ex, i, args, stdout)

    # ---------------------------------------------------------------- #
    # =>> A [ { 'b1' B } C , { 'b1' B } D ] B
    # ---------------------------------------------------------------- #
    ex = 'ex_2'
    # ---------------------------------------------------------------- #
    args = [
        'task A [ {{ {NAME} task -e B }} task C , {{ {NAME} task B }} task D ] task B',
    ]

    stdout = """\
starting B (coroutine name: 3)
starting C (coroutine name: 1)
starting D (coroutine name: 2)
starting B (coroutine name: {NAME})
starting B (coroutine name: {NAME})
starting A (coroutine name: 0)
1->A->B->C->B
1->A->B->D->B
2->A->B->C->B
2->A->B->D->B
3->A->B->C->B
3->A->B->D->B
4->A->B->C->B
4->A->B->D->B
5->A->B->C->B
5->A->B->D->B
6->A->B->C->B
6->A->B->D->B
finished B (coroutine name: {NAME})
finished D (coroutine name: 2)
finished C (coroutine name: 1)
finished B (coroutine name: 3)
Aborted!
"""

    for i, args in enumerate(args):
        _test(ex, i, args, stdout)

    # ---------------------------------------------------------------- #
    # equivalent:
    #  =>> A { 'b1' [ B C , { 'b2' B } D ] } B
    #  =>> A [ { 'b1' B C } , { 'b2' B } { 'b1' D } ] B
    # ---------------------------------------------------------------- #
    ex = 'ex_3'
    # ---------------------------------------------------------------- #
    args = [
        'task A {{ {NAME} [ task -e B task C , {{ {NAME}_bis task B }} task D ] }} task B ',
        'task A [ {{ {NAME} task -e B task C }} , {{ {NAME}_bis task B }} {{ {NAME} task D }} ] task B ',
    ]

    stdout = """\
starting B (coroutine name: 3)
starting C (coroutine name: {NAME})
starting D (coroutine name: {NAME})
starting B (coroutine name: {NAME})
starting B (coroutine name: {NAME}_bis)
starting A (coroutine name: 0)
1->A->B->C->B
1->A->B->D->B
2->A->B->C->B
2->A->B->D->B
3->A->B->C->B
3->A->B->D->B
4->A->B->C->B
4->A->B->D->B
5->A->B->C->B
5->A->B->D->B
6->A->B->C->B
6->A->B->D->B
finished B (coroutine name: {NAME}_bis)
finished D (coroutine name: {NAME})
finished C (coroutine name: {NAME})
finished B (coroutine name: 3)
Aborted!
"""

    for i, args in enumerate(args):
        _test(ex, i, args, stdout)

    # ---------------------------------------------------------------- #
    # =>> A [ { 'b1' } B , { 'b2' } B ] B
    # ---------------------------------------------------------------- #
    ex = 'ex_4'
    # ---------------------------------------------------------------- #
    args = [
        'task A [ {{ {NAME} }} task -e B , {{ {NAME} }} task B ] task B',
    ]

    stdout = """\
starting B (coroutine name: 3)
starting B (coroutine name: 1)
starting B (coroutine name: 2)
starting A (coroutine name: 0)
1->A->B->B
1->A->B->B
2->A->B->B
2->A->B->B
3->A->B->B
3->A->B->B
4->A->B->B
4->A->B->B
5->A->B->B
5->A->B->B
6->A->B->B
6->A->B->B
finished B (coroutine name: 2)
finished B (coroutine name: 3)
Aborted!
"""

    for i, args in enumerate(args):
        _test(ex, i, args, stdout, err_name='1')
