# -*- encoding: utf-8 -*-

import ast

from peval.utils import shift_source, get_locals
from peval.mangler import mangle

from .utils import BaseTestCase


class TestInliner(BaseTestCase):
    def test_mutiple_returns(self):
        source = '''
        def f(x, y, z='foo'):
            if x:
                b = y + list(x)
                return b
            else:
                return z
        '''
        ast_tree = ast.parse(shift_source(source))
        expected_source = '''
        def f(__peval_var_4, __peval_var_5, __peval_var_6='foo'):
            if __peval_var_4:
                __peval_var_7 = __peval_var_5 + list(__peval_var_4)
                __peval_var_8 = __peval_var_7
                break
            else:
                __peval_var_8 = __peval_var_6
                break
        '''
        new_ast, new_var_count, return_var = mangle(ast_tree, 3)
        self.assertASTEqual(new_ast, ast.parse(shift_source(expected_source)))
        self.assertEqual(new_var_count, 8)
        self.assertEqual(return_var, '__peval_var_8')
