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
                __mangled_2 = x
                __mangled_3 = (__mangled_2 + 1)
                __return_1 = (__mangled_3 * 2)
                a += __return_1
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
                __mangled_2 = x
                __mangled_3 = (__mangled_2 + 1)
                __return_1 = (__mangled_3 * 2)
                a += __return_1
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
                __mangled_2 = x
                __while_4 = True
                while __while_4:
                    __while_4 = False
                    __mangled_3 = (__mangled_2 + 1)
                    if (__mangled_3 > 3):
                        __return_1 = (__mangled_3 * 2)
                        break
                    else:
                        __return_1 = 1
                        break
                a += __return_1
                return a
        """)
