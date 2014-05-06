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

    gen_sym, fully_evaluated, result, temp_bindings = peval_expression(gen_sym, bindings, node)
    expected_result = expression_ast("11 + a")

    assert temp_bindings == {}
    assert not fully_evaluated
    assert_ast_equal(result, expected_result)


def test_full_bin_op():

    node = expression_ast("5 + 6 + a")
    bindings = dict(a=7)
    gen_sym = GenSym()

    gen_sym, fully_evaluated, result, temp_bindings = peval_expression(gen_sym, bindings, node)
    expected_result = 18

    assert temp_bindings == {}
    assert fully_evaluated
    assert result == expected_result
