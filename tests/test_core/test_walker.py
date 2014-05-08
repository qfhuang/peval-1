import copy
import ast
import inspect
import sys

import pytest

from peval.utils import unshift
from peval.core.walker import Walker

from tests.utils import assert_ast_equal


def get_ast(function):
    if isinstance(function, str):
        return ast.parse(unshift(function))
    else:
        return ast.parse(inspect.getsource(function))


def check_mutation(node, walker):
    node_ref = copy.deepcopy(node)
    new_node = walker.transform(node)
    assert ast.dump(node) != ast.dump(new_node)
    assert_ast_equal(node, node_ref)
    return new_node


def dummy(x, y):
    c = 4
    a = 1


@Walker
def collect_numbers(node, state, **kwds):
    if isinstance(node, ast.Num):
        state.add(node.n)
    return node

def test_mutable_state():
    node = get_ast(dummy)
    state = collect_numbers.inspect(node, state=set())
    assert state == set([1, 4])


def test_walk_list():
    node = get_ast(dummy)
    state = collect_numbers.inspect(node.body, state=set())
    assert state == set([1, 4])


@Walker
def change_name(node, **kwds):
    if isinstance(node, ast.Name) and node.id == 'a':
        return ast.Name(id='b', ctx=node.ctx)
    else:
        return node

def test_change_name():
    node = get_ast(dummy)
    new_node = check_mutation(node, change_name)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
            b = 1
        """))


@Walker
def add_statement(node, **kwds):
    if isinstance(node, ast.Assign):
        return [node, ast.parse("b = 2").body[0]]
    else:
        return node

def test_add_statement():
    node = get_ast(dummy)
    new_node = check_mutation(node, add_statement)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
            b = 2
            a = 1
            b = 2
        """))


@Walker
def remove_list_element(node, **kwds):
    if isinstance(node, ast.Assign) and node.targets[0].id == 'a':
        return None
    else:
        return node

def test_list_element():
    """
    Tests the removal of an AST node that is an element of a list
    referenced by a field of the parent node.
    """
    node = get_ast(dummy)
    new_node = check_mutation(node, remove_list_element)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
        """))


@Walker
def remove_field(node, **kwds):
    if sys.version_info >= (3,) and isinstance(node, ast.arg) and node.arg == 'x':
        return None
    elif sys.version_info < (3,) and isinstance(node, ast.Name) and node.id == 'x':
        return None
    else:
        return node

def test_remove_field():
    """
    Tests the removal of an AST node that is referenced by a field of the parent node.
    """
    node = get_ast(dummy)
    new_node = check_mutation(node, remove_field)
    assert_ast_equal(new_node, get_ast("""
        def dummy(y):
            c = 4
            a = 1
        """))


@Walker
def pass_through(node, **kwds):
    return node

def test_wrong_root_type():
    with pytest.raises(TypeError):
        pass_through.inspect({})


@Walker
def wrong_root_return_value(node, **kwds):
    return 1

def test_wrong_root_return_value():
    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_root_return_value.inspect(node)


@Walker
def wrong_field_return_value(node, **kwds):
    if isinstance(node, ast.Num):
        return 1
    else:
        return node

def test_wrong_field_return_value():
    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_field_return_value.inspect(node)


@Walker
def wrong_list_return_value(node, **kwds):
    if isinstance(node, ast.Assign):
        return 1
    else:
        return node

def test_wrong_list_return_value():
    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_list_return_value.inspect(node)


@Walker
class CollectNumbersWithDefault:
    @staticmethod
    def visit_num(node, state, **kwds):
        state.add(node.n)
        return node

    @staticmethod
    def visit(node, state, **kwds):
        return node

@Walker
class CollectNumbers:
    @staticmethod
    def visit_num(node, state, **kwds):
        state.add(node.n)
        return node

def test_dispatched_walker():
    node = get_ast(dummy)

    state = CollectNumbers.inspect(node, state=set())
    assert state == set([1, 4])

    state = CollectNumbersWithDefault.inspect(node, state=set())
    assert state == set([1, 4])
