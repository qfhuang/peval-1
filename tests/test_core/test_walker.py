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


def dummy_blocks(x, y):
    a = 1
    if x:
        b = 2
    c = 3


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


# Transformations

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


# Error checks

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


def test_hidden_mutation():
    node = get_ast(dummy)
    with pytest.raises(ValueError):
        state = change_name.inspect(node, set())


# Handler dispatchers

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


# Advanced functionality

def dummy_nested(x, y):
    def inner_function(z):
        return z
    return inner_function

def replace_field(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)

@Walker
def mangle_functions(node, **kwds):
    if isinstance(node, ast.FunctionDef):
        return replace_field(node, name='__' + node.name)
    else:
        return node

def test_walk_children():
    node = get_ast(dummy_nested)
    new_node = mangle_functions.transform(node)
    assert_ast_equal(new_node, get_ast(
        """
        def __dummy_nested(x, y):
            def __inner_function(z):
                return z
            return inner_function
        """))


def test_global_context():

    @Walker
    def rename(node, ctx, **kwds):
        if isinstance(node, ast.Name) and node.id == ctx.old_name:
            return ast.Name(id=ctx.new_name, ctx=node.ctx)
        else:
            return node

    node = get_ast(dummy)
    new_node = rename.transform(node, ctx=dict(old_name='c', new_name='d'))

    assert_ast_equal(new_node, get_ast(
        """
        def dummy(x, y):
            d = 4
            a = 1
        """))


def test_prepend():

    @Walker
    def prepender(node, prepend, **kwds):
        if isinstance(node, ast.Name):
            if node.id == 'a':
                prepend(
                    [ast.Assign(targets=[ast.Name(id='k', ctx=ast.Store())], value=ast.Num(n=10))])
                return node
            elif node.id == 'b':
                prepend(
                    [ast.Assign(targets=[ast.Name(id='l', ctx=ast.Store())], value=ast.Num(n=20))])
                return ast.Name(id='d', ctx=node.ctx)
            elif node.id == 'c':
                prepend(
                    [ast.Assign(targets=[ast.Name(id='m', ctx=ast.Store())], value=ast.Num(n=30))])
                return node
            else:
                return node
        else:
            return node

    node = get_ast(dummy_blocks)
    new_node = prepender.transform(node)

    assert_ast_equal(new_node, get_ast(
        """
        def dummy_blocks(x, y):
            k = 10
            a = 1
            if x:
                l = 20
                d = 2
            m = 30
            c = 3
        """))

