import six
import sys

import ast
from ast import Module, FunctionDef, arguments, Name, Param, If, Compare, \
        Return, BinOp, Load, Add, Subscript, Index, Str, Eq
if not six.PY2:
    from ast import arg

import pytest

from peval.tools import unindent
from peval.core.function import Function

from tests.utils import ast_to_source, ast_equal, assert_ast_equal


def test_unindent():
    src = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzz']
        """
    expected_src = """def sample_fn(x, y, foo='bar', **kw):
    if (foo == 'bar'):
        return (x + y)
    else:
        return kw['zzz']"""

    assert unindent(src) == expected_src


def test_unindent_unexpected_indentation():
    src = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzz']
       some_code() # indentation here does not start from the same position as the first line!
        """

    with pytest.raises(ValueError):
        result = unindent(src)


def test_unindent_empty_line():
    src = (
        """
        def sample_fn(x, y, foo='bar', **kw):\n"""
        # Technically, this line would be an unexpected indentation,
        # because it does not start with 8 spaces.
        # But `unindent` will see that it's just an empty line
        # and just replace it with a single `\n`.
        "    \n"
        """            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzz']
        """)

    expected_src = (
        "def sample_fn(x, y, foo='bar', **kw):\n"
        "\n"
        """    if (foo == 'bar'):
        return (x + y)
    else:
        return kw['zzz']""")

    assert unindent(src) == expected_src


def test_compare_ast():
    function = Function.from_object(sample_fn)

    if sys.version_info < (3,):
        fn_args = arguments(
            args=[Name('x', Param()), Name('y', Param()), Name('foo', Param())],
            vararg=None,
            kwarg='kw',
            defaults=[Str('bar')])
        fn_returns = tuple()
    elif sys.version_info < (3, 4,):
        fn_args = arguments(
            args=[arg('x', None), arg('y', None), arg('foo', None)],
            vararg=None,
            varargannotation=None,
            kwonlyargs=[],
            kwarg='kw',
            kwargannotation=None,
            defaults=[Str('bar')],
            kw_defaults=[])
        fn_returns = (None,) # return annotation
    else:
        # In Py3.4 ast.arguments() fields changed again ---
        # vararg and kwarg became arg() objects too.
        fn_args = arguments(
            args=[arg('x', None), arg('y', None), arg('foo', None)],
            vararg=None,
            kwonlyargs=[],
            kwarg=arg('kw', None),
            defaults=[Str('bar')],
            kw_defaults=[])
        fn_returns = (None,) # return annotation

    expected_tree = FunctionDef(
        'sample_fn',
        fn_args,
        [
            If(Compare(Name('foo', Load()), [Eq()], [Str('bar')]),
            [Return(BinOp(Name('x', Load()), Add(), Name('y', Load())))],
            [Return(Subscript(Name('kw', Load()),
            Index(Str('zzz')), Load()))])],
        [],
        *fn_returns)

    assert_ast_equal(function.tree, expected_tree)
    assert not ast_equal(function.tree, Function.from_object(sample_fn2).tree)
    assert not ast_equal(function.tree, Function.from_object(sample_fn3).tree)


def test_compile_ast():
    function = Function.from_object(sample_fn)
    compiled_fn = function.eval()
    assert compiled_fn(3, -9) == sample_fn(3, -9)
    assert compiled_fn(3, -9, 'z', zzz=map) == sample_fn(3, -9, 'z', zzz=map)


def test_get_source():
    function = Function.from_object(sample_fn)
    source = ast_to_source(function.tree)

    expected_source = unindent(
        """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzz']
        """)

    assert source == expected_source


def sample_fn(x, y, foo='bar', **kw):
    if foo == 'bar':
        return x + y
    else:
        return kw['zzz']


def sample_fn2(x, y, foo='bar', **kw):
    if foo == 'bar':
        return x - y
    else:
        return kw['zzz']


def sample_fn3(x, y, foo='bar', **kwargs):
    if foo == 'bar':
        return x + y
    else:
        return kwargs['zzz']

