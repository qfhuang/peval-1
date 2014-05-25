from __future__ import print_function

import sys
import ast
import functools

import pytest

from peval.core.function import Function
from peval.decorators import inline
from peval import partial_apply
from peval.utils import unshift

from tests.utils import assert_ast_equal


def assert_func_equal_on(fn1, fn2, *args, **kwargs):
    ''' Check that functions are the same, or raise the same exception
    '''
    v1 = v2 = e1 = e2 = None
    try:
        v1 = fn1(*args, **kwargs)
    except Exception as _e1:
        e1 = _e1
    try:
        v2 = fn2(*args, **kwargs)
    except Exception as _e2:
        e2 = _e2
    if e1 or e2:
        # reraise exception, if there is only one
        if e1 is None: fn2(*args, **kwargs)
        if e2 is None: fn1(*args, **kwargs)
        if type(e1) != type(e2):
            # assume that fn1 is more correct, so raise exception from fn2
            fn2(*args, **kwargs)
        assert type(e1) == type(e2)
        assert e1.args == e2.args
    else:
        assert e1 is None
        assert e2 is None
        assert v1 == v2


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


def check_partial_fn(base_fn, get_partial_kwargs, get_kwargs):
    ''' Check that partial evaluation of base_fn with partial_args
    gives the same result on args_list
    as functools.partial(base_fn, partial_args)
    '''
    fn = partial_apply(base_fn, **get_partial_kwargs())
    partial_fn = functools.partial(base_fn, **get_partial_kwargs())
    # call two times to check for possible side-effects
    assert_func_equal_on(partial_fn, fn, **get_kwargs()) # first
    assert_func_equal_on(partial_fn, fn, **get_kwargs()) # second


def test_args_handling():

    def args_kwargs(a, b, c=None):
        return 1.0 * a / b * (c or 3)

    assert partial_apply(args_kwargs, 1)(2) == 1.0 / 2 * 3
    assert partial_apply(args_kwargs, 1, 2, 1)() == 1.0 / 2 * 1


def test_kwargs_handling():

    def args_kwargs(a, b, c=None):
        return 1.0 * a / b * (c or 3)

    assert partial_apply(args_kwargs, c=4)(1, 2) == 1.0 / 2 * 4
    assert partial_apply(args_kwargs, 2, c=4)(6) == 2.0 / 6 * 4



@inline
def smart_power(n, x):
    if not isinstance(n, int) or n < 0:
        raise ValueError('Base should be a positive integer')
    elif n == 0:
        return 1
    elif n % 2 == 0:
        v = smart_power(n // 2, x)
        return v * v
    else:
        return x * smart_power(n - 1, x)


@inline
def stupid_power(n, x):
    if not isinstance(n, int) or n < 0:
        raise ValueError('Base should be a positive integer')
    else:
        if n == 0:
            return 1
        if n == 1:
            return x
        v = 1
        for _ in xrange(n):
            v = v * x
        return v


def test_if_on_stupid_power():
    for n in ('foo', 0, 1, 2, 3):
        for x in [0, 1, 0.01, 5e10]:
            check_partial_fn(stupid_power, lambda: dict(n=n), lambda: {'x': x })


def test_if_on_recursive_power():
    for n in ('foo', 0, 1, 2, 3):
        for x in [0, 1, 0.01, 5e10]:
            check_partial_fn(smart_power, lambda: dict(n=n), lambda: {'x': x })


def test_mutation_via_method():

    # Currently mutation is not detected, so ``x.append``
    # gets evaluated and replaced with ``None``.
    pytest.xfail()

    def mutty(x, y):
        x.append('foo')
        return x + [y]

    check_partial_fn(mutty, lambda: dict(x=[1]), lambda: {'y': 2 })
