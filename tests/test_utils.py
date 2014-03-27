# -*- encoding: utf-8 -*-

import six

import ast
from ast import Module, FunctionDef, arguments, Name, Param, If, Compare, \
        Return, BinOp, Load, Add, Subscript, Index, Str, Eq
if not six.PY2:
    from ast import arg

from peval.utils import fn_to_ast, ast_equal, eval_ast, shift_source

from .utils import ast_to_source


def test_fn_to_ast():
    tree = fn_to_ast(sample_fn)
    tree_dump = ast.dump(tree, annotate_fields=False)

    if six.PY2:
        expected_dump = (
            "Module([FunctionDef('sample_fn', "
            "arguments([Name('x', Param()), Name('y', Param()), "
            "Name('foo', Param())], None, 'kw', [Str('bar')]), "
            "[If(Compare(Name('foo', Load()), [Eq()], [Str('bar')]), "
            "[Return(BinOp(Name('x', Load()), Add(), Name('y', Load())))], "
            "[Return(Subscript(Name('kw', Load()), "
            "Index(Str('zzz')), Load()))])], [])])")
    else:
        expected_dump = (
            "Module([FunctionDef('sample_fn', "
            "arguments([arg('x', None), arg('y', None), arg('foo', None)], "
            "None, None, [], 'kw', None, [Str('bar')], []), "
            "[If(Compare(Name('foo', Load()), [Eq()], [Str('bar')]), "
            "[Return(BinOp(Name('x', Load()), Add(), Name('y', Load())))], "
            "[Return(Subscript(Name('kw', Load()), "
            "Index(Str('zzz')), Load()))])], [], None)])")

    assert tree_dump == expected_dump


def test_compare_ast():
    tree = fn_to_ast(sample_fn)

    if six.PY2:
        fn_args = arguments(
            args=[Name('x', Param()), Name('y', Param()), Name('foo', Param())],
            vararg=None,
            kwarg='kw',
            defaults=[Str('bar')])
        fn_returns = tuple()
    else:
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

    expected_tree = Module([
        FunctionDef(
            'sample_fn',
            fn_args,
            [
                If(Compare(Name('foo', Load()), [Eq()], [Str('bar')]),
                [Return(BinOp(Name('x', Load()), Add(), Name('y', Load())))],
                [Return(Subscript(Name('kw', Load()),
                Index(Str('zzz')), Load()))])],
            [],
            *fn_returns)])

    assert ast_equal(tree, expected_tree)
    assert not ast_equal(tree, fn_to_ast(sample_fn2))
    assert not ast_equal(tree, fn_to_ast(sample_fn3))


def test_compile_ast():
    tree = fn_to_ast(sample_fn)
    compiled_fn = eval_ast(tree)
    assert compiled_fn(3, -9) == sample_fn(3, -9)
    assert compiled_fn(3, -9, 'z', zzz=map) == sample_fn(3, -9, 'z', zzz=map)


def test_get_source():
    tree = fn_to_ast(sample_fn)
    source = ast_to_source(tree)

    expected_source = shift_source(
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

