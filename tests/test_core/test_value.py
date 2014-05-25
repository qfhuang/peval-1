import ast
import sys

import pytest

from peval.core.value import KnownValue, is_known_value, kvalue_to_node, value_to_node
from peval.core.gensym import GenSym

from tests.utils import assert_ast_equal


def check_kvalue_to_node(value, expected_ast, preferred_name=None, expected_binding=None):
    kvalue = KnownValue(value, preferred_name=preferred_name)
    gen_sym = GenSym()
    node, gen_sym, binding = kvalue_to_node(kvalue, gen_sym)

    assert_ast_equal(node, expected_ast)
    if expected_binding is not None:
        assert binding == expected_binding


def check_node_to_maybe_kvalue(node, bindings, expected_result, expected_preferred_name=None):
    node_or_kvalue = node_to_maybe_kvalue(node, bindings)

    if is_known_value(node_or_kvalue):
        assert node_or_kvalue.value == expected_result
        assert node_or_kvalue.preferred_name == expected_preferred_name
    else:
        assert_ast_equal(node_or_kvalue, expected_result)


def test_simple_kvalue_to_node():
    if sys.version_info >= (3, 4):
        check_kvalue_to_node(True, ast.NameConstant(value=True))
        check_kvalue_to_node(False, ast.NameConstant(value=False))
        check_kvalue_to_node(None, ast.NameConstant(value=None))
    else:
        check_kvalue_to_node(
            True, ast.Name(id='__peval_True_1', ctx=ast.Load()),
            expected_binding=dict(__peval_True_1=True))

    class Dummy(): pass
    x = Dummy()
    check_kvalue_to_node(
        x, ast.Name(id='__peval_temp_1', ctx=ast.Load()),
        expected_binding=dict(__peval_temp_1=x))
    check_kvalue_to_node(
        x, ast.Name(id='y', ctx=ast.Load()),
        preferred_name='y', expected_binding=dict(y=x))

    check_kvalue_to_node(1, ast.Num(n=1))
    check_kvalue_to_node(2.3, ast.Num(n=2.3))
    check_kvalue_to_node(3+4j, ast.Num(n=3+4j))
    check_kvalue_to_node('abc', ast.Str(s='abc'))
    if sys.version_info < (3,):
        check_kvalue_to_node(unicode('abc'), ast.Str(s=unicode('abc')))
    else:
        s = bytes('abc', encoding='ascii')
        check_kvalue_to_node(s, ast.Bytes(s=s))


def test_value_to_node():
    class Dummy(): pass
    x = Dummy()
    gen_sym = GenSym()
    node, gen_sym, binding = value_to_node(x, gen_sym)
    assert_ast_equal(node, ast.Name(id='__peval_temp_1', ctx=ast.Load()))
    assert binding == dict(__peval_temp_1=x)


def test_str_repr():
    kv = KnownValue(1, preferred_name='x')
    s = str(kv)
    nkv = eval(repr(kv))
    assert nkv.value == kv.value
    assert nkv.preferred_name == kv.preferred_name
