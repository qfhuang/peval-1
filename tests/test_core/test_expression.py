import ast
import sys

import pytest

from peval.core.expression import peval_expression
from peval.core.gensym import GenSym
from peval.decorators import pure_function

from tests.utils import assert_ast_equal


def expression_ast(source):
    return ast.parse(source).body[0].value


def check_peval_expression(source, bindings, expected_source,
        fully_evaluated=False, expected_value=None, expected_temp_bindings=None,
        py2_division=False):

    source_tree = expression_ast(source)

    # In some cases we need to enforce the expected node,
    # because it cannot be obtained by parsing
    # (e.g. "-5" is parsed as "UnaryOp(op=USub(), Num(n=5))", not as "Num(n=-5)").
    # But we expect the latter from a fully evaluated expression.
    if isinstance(expected_source, str):
        expected_tree = expression_ast(expected_source)
    else:
        expected_tree = expected_source

    gen_sym = GenSym()
    result, gen_sym = peval_expression(source_tree, gen_sym, bindings, py2_division=py2_division)

    assert_ast_equal(result.node, expected_tree)

    assert result.fully_evaluated == fully_evaluated
    if fully_evaluated:
        assert result.value == expected_value

    if expected_temp_bindings is not None:
        for key, val in expected_temp_bindings.items():
            assert key in result.temp_bindings
            assert result.temp_bindings[key] == expected_temp_bindings[key]


def check_peval_expression_bool(source, bindings, expected_value):
    """
    Since prior to Py3.4 `True` and `False` are regular variables,
    these values will be bound to unique names by peval_expression.
    This helper function hides the corresponding logic fork.
    """
    assert expected_value is True or expected_value is False
    if sys.version_info >= (3, 4):
        check_peval_expression(
            source, bindings, expected_source=str(expected_value),
            fully_evaluated=True, expected_value=expected_value)
    else:
        expected_binding = '__peval_' + str(expected_value) + '_1'
        check_peval_expression(
            source, bindings, expected_source=expected_binding,
            expected_temp_bindings={expected_binding: expected_value},
            fully_evaluated=True, expected_value=expected_value)


def test_bin_op_support():
    """
    Check that all possible binary operators are handled by the evaluator.
    """
    check_peval_expression("1 + 2", {}, "3", fully_evaluated=True, expected_value=3)
    check_peval_expression("2 - 1", {}, "1", fully_evaluated=True, expected_value=1)
    check_peval_expression("2 * 3", {}, "6", fully_evaluated=True, expected_value=6)
    if sys.version_info < (3,):
        check_peval_expression(
            "9 / 2", {}, "4", fully_evaluated=True, expected_value=4, py2_division=True)
        check_peval_expression(
            "9 / 2.", {}, "4.5", fully_evaluated=True, expected_value=4.5, py2_division=True)
    else:
        with pytest.raises(ValueError):
            check_peval_expression(
                "9 / 2", {}, "4", fully_evaluated=True, expected_value=4, py2_division=True)
    check_peval_expression(
        "9 / 2", {}, "4.5", fully_evaluated=True, expected_value=4.5, py2_division=False)
    check_peval_expression("9 // 2", {}, "4", fully_evaluated=True, expected_value=4)
    check_peval_expression("9 % 2", {}, "1", fully_evaluated=True, expected_value=1)
    check_peval_expression("2 ** 4", {}, "16", fully_evaluated=True, expected_value=16)
    check_peval_expression("3 << 2", {}, "12", fully_evaluated=True, expected_value=12)
    check_peval_expression("64 >> 3", {}, "8", fully_evaluated=True, expected_value=8)
    check_peval_expression("17 | 3", {}, "19", fully_evaluated=True, expected_value=19)
    check_peval_expression("17 ^ 3", {}, "18", fully_evaluated=True, expected_value=18)
    check_peval_expression("17 & 3", {}, "1", fully_evaluated=True, expected_value=1)


def test_unary_op_support():
    """
    Check that all possible unary operators are handled by the evaluator.
    """
    check_peval_expression("+(2)", {}, "2", fully_evaluated=True, expected_value=2)
    check_peval_expression("-(-3)", {}, "3", fully_evaluated=True, expected_value=3)
    check_peval_expression_bool("not 0", {}, True)
    check_peval_expression("~(-4)", {}, "3", fully_evaluated=True, expected_value=3)


def test_comparison_op_support():
    """
    Check that all possible comparison operators are handled by the evaluator.
    """
    check_peval_expression_bool("1 == 2", {}, False)
    check_peval_expression_bool("2 != 3", {}, True)
    check_peval_expression_bool("1 < 10", {}, True)
    check_peval_expression_bool("1 <= 1", {}, True)
    check_peval_expression_bool("2 > 5", {}, False)
    check_peval_expression_bool("4 >= 6", {}, False)

    class Foo: pass
    x = Foo()
    y = Foo()
    check_peval_expression_bool("a is b", dict(a=x, b=x), True)
    check_peval_expression_bool("a is not b", dict(a=x, b=y), True)

    check_peval_expression_bool("1 in (3, 4, 5)", {}, False)
    check_peval_expression_bool("'a' not in 'abcd'", {}, False)


def test_ifexp():
    check_peval_expression('x if (not a) else y', dict(a=False), 'x')
    check_peval_expression('x if a else y', dict(a=False), 'y')
    check_peval_expression('(x + y) if a else (y + 4)', dict(x=1, y=2), '3 if a else 6')


def test_ifexp_short_circuit():

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_peval_expression('x if a else inc()', dict(a=True, inc=inc), 'x')
    assert global_state['cnt'] == 0

    check_peval_expression('inc() if a else x', dict(a=False, inc=inc), 'x')
    assert global_state['cnt'] == 0

    check_peval_expression_bool('inc() if a else x', dict(a=True, inc=inc), True)
    assert global_state['cnt'] == 1


def test_partial_bin_op():
    check_peval_expression("5 + 6 + a", {}, "11 + a")


def test_full_bin_op():
    check_peval_expression("5 + 6 + a", dict(a=7), "18", fully_evaluated=True, expected_value=18)


def test_propagation_int():
    check_peval_expression(
        "a * n + (m - 2) * (n + 1)", dict(n=5),
        "a * 5 + (m - 2) * 6")


def test_propagation_float():
    check_peval_expression(
        'a * n + (m - 2) * (n + 1)', dict(n=5.0),
        'a * 5.0 + (m - 2) * 6.0')


def test_propagation_str():
    check_peval_expression(
        "a + foo", dict(foo="bar"),
        "a + 'bar'")


def test_preferred_name():
    """
    Test that when a non-literal value is transformed back into an AST node,
    it takes back the name it was bound to.
    """

    class Int(int): pass
    check_peval_expression(
        'm * n', dict(m=Int(2)),
        'm * n')


def test_call_no_args():

    @pure_function
    def fn():
        return 'Hi!'

    check_peval_expression(
        'fn()', dict(fn=fn), '"Hi!"',
        fully_evaluated=True, expected_value='Hi!')


def test_call_with_args():

    @pure_function
    def fn(x, y):
        return x + [y]

    check_peval_expression('fn(x, y)', dict(fn=fn, x=10), 'fn(10, y)')
    check_peval_expression(
            'fn(x, y)',
            dict(fn=fn, x=[10], y=20.0),
            '__peval_temp_1',
            expected_temp_bindings=dict(__peval_temp_1=[10, 20.0]),
            fully_evaluated=True, expected_value=[10, 20.0])


def test_exception():
    """
    A pure function which throws an exception during partial evaluation
    is left unevaluated.
    """

    @pure_function
    def fn():
        return 1 / 0
    check_peval_expression('fn()', dict(fn=fn), 'fn()')


def test_and():
    check_peval_expression_bool('a and b', dict(a=False), False)
    check_peval_expression('a and b', dict(a=True), 'b')
    check_peval_expression_bool('a and b()', dict(a=True, b=pure_function(lambda: True)), True)
    check_peval_expression('a and b and c and d', dict(a=True, c=True), 'b and d')


def test_and_short_circuit():

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_peval_expression_bool('a and inc()', dict(a=False, inc=inc), False)
    assert global_state['cnt'] == 0

    check_peval_expression_bool('a and inc()', dict(a=True, inc=inc), True)
    assert global_state['cnt'] == 1


def test_or():
    check_peval_expression('a or b', dict(a=False), 'b')
    check_peval_expression_bool('a or b', dict(a=True), True)
    check_peval_expression_bool('a or b', dict(a=False, b=False), False)
    check_peval_expression_bool('a or b()', dict(a=False, b=pure_function(lambda: True)), True)
    check_peval_expression('a or b or c or d', dict(a=False, c=False), 'b or d')


def test_or_short_circuit():

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_peval_expression_bool('a or inc()', dict(a=True, inc=inc), True)
    assert global_state['cnt'] == 0

    check_peval_expression_bool('a or inc()', dict(a=False, inc=inc), True)
    assert global_state['cnt'] == 1


def test_eq():
    check_peval_expression_bool('0 == 0', {}, True)
    check_peval_expression_bool('0 == 1', {}, False)
    check_peval_expression('a == b', dict(a=1), '1 == b')
    check_peval_expression('a == b', dict(b=1), 'a == 1')
    check_peval_expression_bool('a == b', dict(a=1, b=1), True)
    check_peval_expression_bool('a == b', dict(a=2, b=1), False)
    check_peval_expression(
            'a == b == c == d', dict(a=2, c=2),
            '2 == b == 2 == d')


def test_mix():
    check_peval_expression_bool('a < b >= c', dict(a=0, b=1, c=1), True)
    check_peval_expression_bool('a <= b > c', dict(a=0, b=1, c=1), False)


def test_arithmetic():
    check_peval_expression(
        '1 + 1', {}, '2', fully_evaluated=True, expected_value=2)
    check_peval_expression(
        '1 + (1 * 67.0)', {}, '68.0', fully_evaluated=True, expected_value=68.0)
    check_peval_expression(
        '1 / 2.0', {}, '0.5', fully_evaluated=True, expected_value=0.5)
    check_peval_expression(
        '3 % 2', {}, '1', fully_evaluated=True, expected_value=1)
    check_peval_expression(
        'x / y', dict(x=1, y=2.0), '0.5', fully_evaluated=True, expected_value=0.5)
