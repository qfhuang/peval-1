# -*- encoding: utf-8 -*-
from __future__ import division

import functools

from peval import partial_apply
from peval.decorators import inline


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


def test_if_on_stupid_power():

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
                v *= x
            return v

    for n in ('foo', 0, 1, 2, 3):
        for x in [0, 1, 0.01, 5e10]:
            check_partial_fn(stupid_power, lambda: dict(n=n), lambda: {'x': x })


def test_if_on_recursive_power():

    @inline
    def power(x, n):
        if not isinstance(n, int) or n < 0:
            raise ValueError('Base should be a positive integer')
        elif n == 0:
            return 1
        elif n % 2 == 0:
            v = power(x, n // 2)
            return v * v
        else:
            return x * power(x, n - 1)

    for n in ('foo', 0, 1, 2, 3):
        for x in [0, 1, 0.01, 5e10]:
            check_partial_fn(power, lambda: dict(n=n), lambda: {'x': x })


def test_mutation_via_method():

    def mutty(x, y):
        x.append('foo')
        return x + [y]

    check_partial_fn(mutty, lambda: dict(x=[1]), lambda: {'y': 2 })


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

