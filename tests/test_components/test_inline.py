from __future__ import print_function, division

import ast
import sys

import pytest

from peval.decorators import pure_function, inline
from peval.components.inline import inline_functions

from tests.utils import check_component


def test_simple_return():

    @inline
    def inlined(y):
        a = y + 1
        return a * 2

    def outer(x):
        a = x.foo()
        a += inlined(x)
        return a

    check_component(
        inline_functions, outer,
        expected_source="""
            def outer(x):
                a = x.foo()
                __peval_mangled_2 = x
                __peval_mangled_3 = (__peval_mangled_2 + 1)
                __peval_return_1 = (__peval_mangled_3 * 2)
                a += __peval_return_1
                return a
        """)


def test_simple_return():

    @inline
    def inlined(y):
        a = y + 1
        return a * 2

    def outer(x):
        a = x.foo()
        a += inlined(x)
        return a

    check_component(
        inline_functions, outer,
        expected_source="""
            def outer(x):
                a = x.foo()
                __peval_mangled_2 = x
                __peval_mangled_3 = (__peval_mangled_2 + 1)
                __peval_return_1 = (__peval_mangled_3 * 2)
                a += __peval_return_1
                return a
        """)


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
                __peval_mangled_2 = x
                __peval_while_4 = True
                while __peval_while_4:
                    __peval_while_4 = False
                    __peval_mangled_3 = (__peval_mangled_2 + 1)
                    if (__peval_mangled_3 > 3):
                        __peval_return_1 = (__peval_mangled_3 * 2)
                        break
                    else:
                        __peval_return_1 = 1
                        break
                a += __peval_return_1
                return a
        """)
