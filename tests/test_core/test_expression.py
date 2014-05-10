import ast

from peval.core.expression import peval_expression
from peval.core.gensym import GenSym

from tests.utils import assert_ast_equal


def expression_ast(source):
    return ast.parse(source).body[0].value


def test_partial_bin_op():

    node = expression_ast("5 + 6 + a")
    bindings = dict()
    gen_sym = GenSym()

    gen_sym, result = peval_expression(gen_sym, bindings, node)
    expected_node = expression_ast("11 + a")

    assert result.temp_bindings == {}
    assert not result.fully_evaluated
    assert_ast_equal(result.node, expected_node)


def test_full_bin_op():

    node = expression_ast("5 + 6 + a")
    bindings = dict(a=7)
    gen_sym = GenSym()

    gen_sym, result = peval_expression(gen_sym, bindings, node)
    expected_value = 18
    expected_node = ast.Num(n=18)

    assert result.temp_bindings == {}
    assert result.fully_evaluated
    assert_ast_equal(result.node, expected_node)
    assert result.value == expected_value
