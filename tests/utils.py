from __future__ import print_function

import ast
import unittest
import warnings

import meta.asttools


# ignore warnings about missing lineno and col_offset
warnings.filterwarnings('ignore', module='meta.asttools.visitors', lineno=47)


def ast_to_source(tree):
    ''' Return python source of AST tree, as a string.
    '''
    source = meta.asttools.dump_python_source(tree)

    # trim trailing spaces --- some pretty printers add it
    source = "\n".join(line.rstrip() for line in source.split("\n"))

    return source


def ast_to_string(tree):
    ''' Return pretty-printed AST, as a string.
    '''
    return meta.asttools.str_ast(tree)


class BaseTestCase(unittest.TestCase):
    def assertASTEqual(self, test_ast, expected_ast, print_ast=False):
        ''' Check that test_ast is equal to expected_ast,
        printing helpful error message if they are not equal
        '''
        dump1, dump2 = ast.dump(test_ast), ast.dump(expected_ast)
        if dump1 != dump2:
            if print_ast:
                print('\n' + '=' * 40 + ' expected ast:\n{expected_ast}\n'\
                    '\ngot ast:\n{test_ast}\n'.format(
                            expected_ast=ast_to_string(expected_ast),
                            test_ast=ast_to_string(test_ast)))
            print('\n' + '=' * 40 + ' expected source:\n{expected_source}\n'\
                  '\ngot source:\n{test_source}\n'.format(
                          expected_source=ast_to_source(expected_ast),
                          test_source=ast_to_source(test_ast)))
        self.assertEqual(dump1, dump2)