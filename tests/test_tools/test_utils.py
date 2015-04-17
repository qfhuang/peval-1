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


def test_ast_equal():
    src = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzz']
        """

    # Different node type (`-` instead of `+`)
    different_node = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x - y)
            else:
                return kw['zzz']
        """

    # Different value in a node ('zzy' instead of 'zzz')
    different_value = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
            else:
                return kw['zzy']
        """

    # Additional element in a body
    different_length = """
        def sample_fn(x, y, foo='bar', **kw):
            if (foo == 'bar'):
                return (x + y)
                return 1
            else:
                return kw['zzz']
        """

    tree = ast.parse(unindent(src))
    different_node = ast.parse(unindent(different_node))
    different_value = ast.parse(unindent(different_value))
    different_length = ast.parse(unindent(different_length))

    assert ast_equal(tree, tree)
    assert not ast_equal(tree, different_node)
    assert not ast_equal(tree, different_value)
    assert not ast_equal(tree, different_length)
