from __future__ import print_function

import ast
import warnings
import difflib

import astprint


# ignore warnings about missing lineno and col_offset
warnings.filterwarnings('ignore', module='meta.asttools.visitors', lineno=47)


def ast_to_source(tree):
    ''' Return python source of AST tree, as a string.
    '''
    source = astprint.as_code(tree)

    # trim newlines and trailing spaces --- some pretty printers add it
    source = "\n".join(line.rstrip() for line in source.split("\n"))
    source = source.strip("\n")

    return source


def ast_to_string(tree):
    ''' Return pretty-printed AST, as a string.
    '''
    return astprint.as_tree(tree)


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
