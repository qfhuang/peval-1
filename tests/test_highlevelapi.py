from __future__ import print_function

import sys
import ast

import pytest

from peval.core.function import Function
from peval.decorators import inline
from peval import partial_apply
from peval.utils import unshift

from tests.utils import assert_ast_equal


def check_partial_apply(func, args=None, kwds=None,
        expected_source=None, expected_new_bindings=None):
    ''' Test that with given constants, optimized_ast transforms
    source to expected_source.
    It :expected_new_bindings: is given, we check that they
    are among new bindings returned by optimizer.
    '''

    if args is None:
        args = tuple()
    if kwds is None:
        kwds = {}

    new_func = partial_apply(func, *args, **kwds)
    function = Function.from_object(new_func)

    if expected_source is not None:
        assert_ast_equal(function.tree, ast.parse(unshift(expected_source)).body[0])

    if expected_new_bindings is not None:
        for k in expected_new_bindings:
            if k not in function.globals:
                print('Expected binding missing:', k)

            binding = function.globals[k]
            expected_binding = expected_new_bindings[k]

            # Python 3.2 defines equality for range objects incorrectly
            # (namely, the result is always False).
            # So we just test it manually.
            if sys.version_info < (3, 3) and isinstance(expected_binding, range):
                assert type(binding) == type(expected_binding)
                assert list(binding) == list(expected_binding)
            else:
                assert binding == expected_binding


# Test simple inlining

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

    check_partial_apply(
        outer,
        expected_source='''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
            __peval_mangled_3 = []
            for __peval_mangled_4 in xrange(x):
                __peval_mangled_3.append(x.do_stuff())
            a = (b + __peval_mangled_3)
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

    check_partial_apply(
        outer,
        expected_source='''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
                __peval_mangled_2 = x - 3
                __peval_while_5 = {true_const}
                while __peval_while_5:
                    __peval_while_5 = {false_const}
                    __peval_mangled_3 = []
                    for __peval_mangled_4 in iter(__peval_mangled_2):
                        __peval_mangled_3.append(__peval_mangled_4.do_stuff())
                    if __peval_mangled_3:
                        __peval_return_1 = __peval_mangled_3
                        break
                    else:
                        __peval_return_1 = None
                        break
                a = __peval_return_1 + b
            return a
        '''.format(
            true_const='__peval_True_6' if sys.version_info < (3, 4) else 'True',
            false_const='__peval_False_7' if sys.version_info < (3, 4) else 'False'))


def power(x, n):
    if n == 0:
        return 1
    elif n % 2 == 0:
        v = power(x, n // 2)
        return v * v
    else:
        return x * power(x, n - 1)


@inline
def power_inline(x, n):
    if n == 0:
        return 1
    elif n % 2 == 0:
        v = power_inline(x, n // 2)
        return v * v
    else:
        return x * power_inline(x, n - 1)


# Recursion inlining test

def test_no_inlining():
    check_partial_apply(
        power, kwds=dict(n=1),
        expected_source='''
        def power(x):
            return x * power(x, 0)
        ''')


def test_inlining_1():

    check_partial_apply(
        power_inline, kwds=dict(n=1),
        expected_source='''
        @inline
        def power_inline(x):
            return (x * 1)
        ''')
    check_partial_apply(
        power_inline, kwds=dict(n=5),
        expected_source='''
        @inline
        def power_inline(x):
            __peval_return_2 = (x * 1)
            __peval_return_1 = (__peval_return_2 * __peval_return_2)
            __peval_return_6 = (__peval_return_1 * __peval_return_1)
            return (x * __peval_return_6)
        ''')
