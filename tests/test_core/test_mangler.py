import ast

from peval.tools import unindent
from peval.core.gensym import GenSym
from peval.core.mangler import mangle

from tests.utils import assert_ast_equal


def test_mutiple_returns():

    source = unindent('''
    def f(x, y, z='foo'):
        if x:
            b = y + list(x)
            return b
        else:
            return z
    ''')
    tree = ast.parse(source)

    expected_source = unindent('''
    def f(__peval_mangled_1, __peval_mangled_2, __peval_mangled_3='foo'):
        if __peval_mangled_1:
            __peval_mangled_4 = __peval_mangled_2 + list(__peval_mangled_1)
            __peval_return_5 = __peval_mangled_4
            break
        else:
            __peval_return_5 = __peval_mangled_3
            break
    ''')
    expected_tree = ast.parse(expected_source)

    gen_sym = GenSym.for_tree(tree)
    gen_sym, new_tree = mangle(gen_sym, tree, '__peval_return_5')

    assert_ast_equal(new_tree, expected_tree)
