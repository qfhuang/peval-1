# -*- encoding: utf-8 -*-

import ast

from peval.gensym import GenSym
from peval.utils import shift_source
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
        def f(__mangled_1, __mangled_2, __mangled_3='foo'):
            if __mangled_1:
                __mangled_4 = __mangled_2 + list(__mangled_1)
                __return_5 = __mangled_4
                break
            else:
                __return_5 = __mangled_3
                break
        '''
        gen_sym = GenSym(ast_tree)
        new_ast, new_gen_sym_state, return_var = mangle(ast_tree, gen_sym.get_state())
        self.assertASTEqual(new_ast, ast.parse(shift_source(expected_source)))
        self.assertEqual(return_var, '__return_5')
