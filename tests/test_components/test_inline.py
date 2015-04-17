from __future__ import print_function, division

import ast
import sys

import pytest

from peval.tags import inline
from peval.components.inline import inline_functions, _replace_returns

from tests.utils import check_component, unindent, assert_ast_equal


def _test_replace_returns(source, expected_source, expected_returns_ctr, expected_returns_in_loops):

    nodes = ast.parse(unindent(source)).body

    true_val = 'true_val'
    return_var = 'return_var'
    return_flag_var = 'return_flag'

    expected_source = expected_source.format(
        return_var=return_var, return_flag=return_flag_var, true_val='true_val')
    expected_nodes = ast.parse(unindent(expected_source)).body

    true_node = ast.Name(true_val, ast.Load())
    new_nodes, returns_ctr, returns_in_loops = _replace_returns(
        nodes, return_var, return_flag_var, true_node)

    assert_ast_equal(new_nodes, expected_nodes)
    assert returns_ctr == expected_returns_ctr
    assert returns_in_loops == expected_returns_in_loops


class TestReplaceReturns:

    def test_single_return(self):
        _test_replace_returns(
            source="""
                b = y + list(x)
                return b
                """,
            expected_source="""
                b = y + list(x)
                {return_var} = b
                break
                """,
            expected_returns_ctr=1,
            expected_returns_in_loops=False)


    def test_several_returns(self):
        _test_replace_returns(
            source="""
                if a:
                    return y + list(x)
                elif b:
                    return b
                return c
                """,
            expected_source="""
                if a:
                    {return_var} = y + list(x)
                    break
                elif b:
                    {return_var} = b
                    break
                {return_var} = c
                break
                """,
            expected_returns_ctr=3,
            expected_returns_in_loops=False)


    def test_returns_in_loops(self):
        _test_replace_returns(
            source="""
                for x in range(10):
                    for y in range(10):
                        if x + y > 10:
                            return 2
                    else:
                        return 3

                if x:
                    return 1

                while z:
                    if z:
                        return 3

                return 0
                """,
            expected_source="""
                for x in range(10):
                    for y in range(10):
                        if ((x + y) > 10):
                            {return_var} = 2
                            {return_flag} = {true_val}
                            break
                    else:
                        {return_var} = 3
                        {return_flag} = {true_val}
                        break
                    if {return_flag}:
                        break
                if {return_flag}:
                    break
                if x:
                    {return_var} = 1
                    break
                while z:
                    if z:
                        {return_var} = 3
                        {return_flag} = {true_val}
                        break
                if {return_flag}:
                    break
                {return_var} = 0
                break
                """,
            expected_returns_ctr=5,
            expected_returns_in_loops=True)


    def test_returns_in_loop_else(self):
        _test_replace_returns(
            source="""
                for y in range(10):
                    x += y
                else:
                    return 1

                return 0
                """,
            expected_source="""
                for y in range(10):
                    x += y
                else:
                    {return_var} = 1
                    break

                {return_var} = 0
                break
                """,
            expected_returns_ctr=2,
            expected_returns_in_loops=False)



def _test_simple_return():

    @inline
    def inlined(y):
        l = []
        for _ in xrange(y):
            l.append(y.do_stuff())
        return l

    def outer(x):
        a = x.foo()
        if a:
            b = a * 10
        a = b + inlined(x)
        return a

    check_component(
        inline_functions, outer,
        expected_source='''
            def outer(x):
                a = x.foo()
                if a:
                    b = (a * 10)
                __peval_mangled_1 = x
                __peval_mangled_2 = []
                for __peval_mangled_3 in xrange(__peval_mangled_1):
                    __peval_mangled_2.append(__peval_mangled_1.do_stuff())
                __peval_return_1 = __peval_mangled_2
                a = (b + __peval_return_1)
                return a
        ''')


def _test_complex_return():

    @inline
    def inlined(y):
        l = []
        for i in iter(y):
            l.append(i.do_stuff())
        if l:
            return l
        else:
            return None

    def outer(x):
        a = x.foo()
        if a:
            b = a * 10
            a = inlined(x - 3) + b
        return a

    check_component(
        inline_functions, outer,
        expected_source='''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
                __peval_mangled_1 = x - 3
                __peval_while_1 = {true_const}
                while __peval_while_1:
                    __peval_while_1 = {false_const}
                    __peval_mangled_2 = []
                    for __peval_mangled_3 in iter(__peval_mangled_1):
                        __peval_mangled_2.append(__peval_mangled_3.do_stuff())
                    if __peval_mangled_2:
                        __peval_return_1 = __peval_mangled_2
                        break
                    else:
                        __peval_return_1 = None
                        break
                a = __peval_return_1 + b
            return a
        '''.format(
            true_const='__peval_True_1' if sys.version_info < (3, 4) else 'True',
            false_const='__peval_False_1' if sys.version_info < (3, 4) else 'False'))


def _test_multiple_returns():

    @inline
    def inlined(y):
        a = y + 1
        if a > 3:
            return a * 2
        else:
            return 1

    def outer(x):
        a = x.foo()
        a += inlined(x)
        return a

    check_component(
        inline_functions, outer,
        expected_source="""
            def outer(x):
                a = x.foo()
                __peval_mangled_1 = x
                __peval_while_1 = {true_const}
                while __peval_while_1:
                    __peval_while_1 = {false_const}
                    __peval_mangled_2 = (__peval_mangled_1 + 1)
                    if (__peval_mangled_2 > 3):
                        __peval_return_1 = (__peval_mangled_2 * 2)
                        break
                    else:
                        __peval_return_1 = 1
                        break
                a += __peval_return_1
                return a
        """.format(
            true_const='__peval_True_1' if sys.version_info < (3, 4) else 'True',
            false_const='__peval_False_1' if sys.version_info < (3, 4) else 'False'))
