# -*- encoding: utf-8 -*-

import six

import unittest
import ast
from ast import Module, FunctionDef, arguments, Name, Param, If, Compare, \
        Return, BinOp, Load, Add, Subscript, Index, Str, Eq
if not six.PY2:
    from ast import arg

import peval.utils

from .utils import ast_to_source


class TestCase(unittest.TestCase):
    def test_fn_to_ast(self):
        tree = peval.utils.fn_to_ast(sample_fn)
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

        self.assertEqual(tree_dump, expected_dump)

    def test_compare_ast(self):
        tree = peval.utils.fn_to_ast(sample_fn)

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

        self.assertTrue(peval.utils.ast_equal(tree, expected_tree))
        self.assertFalse(peval.utils.ast_equal(
            tree, peval.utils.fn_to_ast(sample_fn2)))
        self.assertFalse(peval.utils.ast_equal(
            tree, peval.utils.fn_to_ast(sample_fn3)))

    def test_compile_ast(self):
        tree = peval.utils.fn_to_ast(sample_fn)
        compiled_fn = peval.utils.eval_ast(tree)
        self.assertEqual(compiled_fn(3, -9), sample_fn(3, -9))
        self.assertEqual(
                compiled_fn(3, -9, 'z', zzz=map),
                sample_fn(3, -9, 'z', zzz=map))

    def test_get_source(self):
        tree = peval.utils.fn_to_ast(sample_fn)
        source = ast_to_source(tree)

        self.assertEqual(source, """
def sample_fn(x, y, foo='bar', **kw):
    if (foo == 'bar'):
        return (x + y)
    else:
        return kw['zzz']

""")


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

