from __future__ import print_function

import ast
import unittest

from ast_pe.utils import ast_to_string, ast_to_source


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
