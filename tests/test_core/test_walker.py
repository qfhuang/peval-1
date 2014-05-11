import copy
import ast
import inspect
import sys

import pytest

from peval.utils import unshift
from peval.core.walker import ast_inspector, ast_transformer, ast_walker

from tests.utils import assert_ast_equal


def get_ast(function):
    if isinstance(function, str):
        return ast.parse(unshift(function))
    else:
        return ast.parse(inspect.getsource(function))


def check_mutation(node, walker):
    node_ref = copy.deepcopy(node)
    new_node = walker(node)
    assert ast.dump(node) != ast.dump(new_node)
    assert_ast_equal(node, node_ref)
    return new_node


def replace_fields(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


def dummy(x, y):
    c = 4
    a = 1


def dummy_blocks(x, y):
    a = 1
    if x:
        b = 2
    c = 3


def dummy_nested(x, y):
    def inner_function(z):
        return z
    return inner_function


def dummy_if():
    if a:
        if b:
            pass


def test_mutable_state():

    @ast_inspector
    def collect_numbers(node, state, **kwds):
        if isinstance(node, ast.Num):
            state.add(node.n)
        return node

    node = get_ast(dummy)
    state = collect_numbers(node, state=set())
    assert state == set([1, 4])


def test_walk_list():

    @ast_inspector
    def collect_numbers(node, state, **kwds):
        if isinstance(node, ast.Num):
            state.add(node.n)
        return node

    node = get_ast(dummy)
    state = collect_numbers(node.body, state=set())
    assert state == set([1, 4])


# Transformations

def test_change_node():

    @ast_transformer
    def change_name(node, **kwds):
        if isinstance(node, ast.Name) and node.id == 'a':
            return ast.Name(id='b', ctx=node.ctx)
        else:
            return node

    node = get_ast(dummy)
    new_node = check_mutation(node, change_name)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
            b = 1
        """))


def test_add_statement():

    @ast_transformer
    def add_statement(node, **kwds):
        if isinstance(node, ast.Assign):
            return [node, ast.parse("b = 2").body[0]]
        else:
            return node

    node = get_ast(dummy)
    new_node = check_mutation(node, add_statement)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
            b = 2
            a = 1
            b = 2
        """))


def test_list_element():
    """
    Tests the removal of an AST node that is an element of a list
    referenced by a field of the parent node.
    """

    @ast_transformer
    def remove_list_element(node, **kwds):
        if isinstance(node, ast.Assign) and node.targets[0].id == 'a':
            return None
        else:
            return node

    node = get_ast(dummy)
    new_node = check_mutation(node, remove_list_element)
    assert_ast_equal(new_node, get_ast("""
        def dummy(x, y):
            c = 4
        """))


def test_remove_field():
    """
    Tests the removal of an AST node that is referenced by a field of the parent node.
    """

    @ast_transformer
    def remove_field(node, **kwds):
        if sys.version_info >= (3,) and isinstance(node, ast.arg) and node.arg == 'x':
            return None
        elif sys.version_info < (3,) and isinstance(node, ast.Name) and node.id == 'x':
            return None
        else:
            return node

    node = get_ast(dummy)
    new_node = check_mutation(node, remove_field)
    assert_ast_equal(new_node, get_ast("""
        def dummy(y):
            c = 4
            a = 1
        """))


# Error checks

def test_wrong_root_type():

    @ast_inspector
    def pass_through(node, **kwds):
        return node

    with pytest.raises(TypeError):
        pass_through({})


def test_wrong_root_return_value():

    @ast_inspector
    def wrong_root_return_value(node, **kwds):
        return 1

    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_root_return_value(node)


def test_wrong_field_return_value():

    @ast_inspector
    def wrong_field_return_value(node, **kwds):
        if isinstance(node, ast.Num):
            return 1
        else:
            return node

    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_field_return_value(node)


def test_wrong_list_return_value():

    @ast_inspector
    def wrong_list_return_value(node, **kwds):
        if isinstance(node, ast.Assign):
            return 1
        else:
            return node

    node = get_ast(dummy)
    with pytest.raises(TypeError):
        wrong_list_return_value(node)


def test_hidden_mutation():

    @ast_inspector
    def change_name(node, **kwds):
        if isinstance(node, ast.Name) and node.id == 'a':
            return ast.Name(id='b', ctx=node.ctx)
        else:
            return node

    node = get_ast(dummy)
    with pytest.raises(ValueError):
        state = change_name(node, set())


# Handler dispatchers

def test_dispatched_walker():

    @ast_inspector
    class collect_numbers_with_default:
        @staticmethod
        def visit_num(node, state, **kwds):
            state.add(node.n)
            return node

        @staticmethod
        def visit(node, state, **kwds):
            return node

    @ast_inspector
    class collect_numbers:
        @staticmethod
        def visit_num(node, state, **kwds):
            state.add(node.n)
            return node

    node = get_ast(dummy)

    state = collect_numbers(node, state=set())
    assert state == set([1, 4])

    state = collect_numbers_with_default(node, state=set())
    assert state == set([1, 4])


# Advanced functionality

def test_walk_children():

    @ast_transformer
    def mangle_functions(node, **kwds):
        if isinstance(node, ast.FunctionDef):
            return replace_fields(node, name='__' + node.name)
        else:
            return node

    node = get_ast(dummy_nested)
    new_node = mangle_functions(node)
    assert_ast_equal(new_node, get_ast(
        """
        def __dummy_nested(x, y):
            def __inner_function(z):
                return z
            return inner_function
        """))


def test_global_context():

    @ast_transformer
    def rename(node, ctx, **kwds):
        if isinstance(node, ast.Name) and node.id == ctx.old_name:
            return ast.Name(id=ctx.new_name, ctx=node.ctx)
        else:
            return node

    node = get_ast(dummy)
    new_node = rename(node, ctx=dict(old_name='c', new_name='d'))

    assert_ast_equal(new_node, get_ast(
        """
        def dummy(x, y):
            d = 4
            a = 1
        """))


def test_prepend():

    @ast_transformer
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
    new_node = prepender(node)

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


def test_visit_after():

    @ast_transformer
    def simplify(node, visit_after, visiting_after, **kwds):
        if isinstance(node, ast.If):
            if not visiting_after:
                visit_after()
                return node

            # This wouldn't work if we didn't simplify the child nodes first
            if (len(node.orelse) == 0 and len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)):
                return ast.Pass()
            else:
                return node
        else:
            return node

    node = get_ast(dummy_if)
    new_node = simplify(node)

    assert_ast_equal(new_node, get_ast(
        """
        def dummy_if():
            pass
        """))


def test_block_autofix():

    # This transformer removes If nodes from statement blocks,
    # but it has no way to check whether the resulting body still has some nodes or not.
    # That's why the walker adds a Pass node automatically if after all the transformations
    # a statement block turns out to be empty.
    @ast_transformer
    def delete_ifs(node, **kwds):
        if isinstance(node, ast.If):
            return None
        else:
            return node

    node = get_ast(dummy_if)
    new_node = delete_ifs(node)

    assert_ast_equal(new_node, get_ast(
        """
        def dummy_if():
            pass
        """))


def test_manual_fields_processing():

    @ast_transformer
    def increment(node, skip_fields, walk_field, **kwds):
        if isinstance(node, ast.Assign):
            skip_fields()
            return replace_fields(node, targets=node.targets, value=walk_field(node.value))
        elif isinstance(node, ast.Num):
            return ast.Num(n=node.n + 1)
        else:
            return node

    node = get_ast(dummy)
    new_node = increment(node)

    assert_ast_equal(new_node, get_ast(
        """
        def dummy(x, y):
            c = 5
            a = 2
        """))
