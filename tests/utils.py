from __future__ import print_function

import ast
import difflib

import astunparse

from peval.utils import unshift
from peval.core.function import Function


def ast_to_source(tree):
    ''' Return python source of AST tree, as a string.
    '''
    source = astunparse.unparse(tree)

    # trim newlines and trailing spaces --- some pretty printers add it
    source = "\n".join(line.rstrip() for line in source.split("\n"))
    source = source.strip("\n")

    return source


def ast_to_string(tree):
    ''' Return pretty-printed AST, as a string.
    '''
    return astunparse.dump(tree)


def ast_equal(tree1, tree2):
    ''' Returns whether AST tree1 is equal to tree2
    '''
    return ast.dump(tree1) == ast.dump(tree2)


def print_diff(test, expected):

    print("\n" + "=" * 40 + " expected:\n\n" + expected)
    print("\n" + "=" * 40 + " result:\n\n" + test)
    print("\n")

    expected_lines = expected.split('\n')
    test_lines = test.split('\n')

    for line in difflib.unified_diff(
            expected_lines, test_lines,
            fromfile='expected', tofile='test'):
        print(line)


def assert_ast_equal(test_ast, expected_ast, print_ast=True):
    ''' Check that test_ast is equal to expected_ast,
    printing helpful error message if they are not equal
    '''
    equal = ast_equal(test_ast, expected_ast)
    if not equal:

        if print_ast:
            expected_ast_str = ast_to_string(expected_ast)
            test_ast_str = ast_to_string(test_ast)
            print_diff(test_ast_str, expected_ast_str)

        expected_source = ast_to_source(expected_ast)
        test_source = ast_to_source(test_ast)
        print_diff(test_source, expected_source)

    assert equal


def check_component(component, func, additional_bindings=None,
        expected_source=None, expected_new_bindings=None):

    function = Function.from_object(func)
    bindings = function.get_external_variables()
    if additional_bindings is not None:
        bindings.update(additional_bindings)

    new_tree, new_bindings = component(function.tree, bindings)

    if expected_source is None:
        expected_ast = function.tree
    else:
        expected_ast = ast.parse(unshift(expected_source)).body[0]

    assert_ast_equal(new_tree, expected_ast)

    if expected_new_bindings is not None:
        for k in expected_new_bindings:
            if k not in new_bindings:
                print('Expected binding missing:', k)

            binding = new_bindings[k]
            expected_binding = expected_new_bindings[k]

            # Python 3.2 defines equality for range objects incorrectly
            # (namely, the result is always False).
            # So we just test it manually.
            if sys.version_info < (3, 3) and isinstance(expected_binding, range):
                assert type(binding) == type(expected_binding)
                assert list(binding) == list(expected_binding)
            else:
                assert binding == expected_binding
