import ast

from peval.core.gensym import GenSym
from peval.utils import unshift
from peval.core.mangler import mangle

from tests.utils import assert_ast_equal


def test_mutiple_returns():

    source = unshift('''
    def f(x, y, z='foo'):
        if x:
            b = y + list(x)
            return b
        else:
            return z
    ''')
    tree = ast.parse(source)

    expected_source = unshift('''
    def f(__mangled_1, __mangled_2, __mangled_3='foo'):
        if __mangled_1:
            __mangled_4 = __mangled_2 + list(__mangled_1)
            __return_5 = __mangled_4
            break
        else:
            __return_5 = __mangled_3
            break
    ''')
    expected_tree = ast.parse(expected_source)

    gen_sym = GenSym.for_tree(tree)
    gen_sym, new_tree = mangle(gen_sym, tree, '__return_5')

    assert_ast_equal(new_tree, expected_tree)