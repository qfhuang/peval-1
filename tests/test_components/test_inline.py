from __future__ import print_function, division

import ast
import sys

import pytest

from peval.tags import pure_function, inline
from peval.components.inline import inline_functions

from tests.utils import check_component


def test_simple_return():

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


def test_complex_return():

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


def test_multiple_returns():

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
