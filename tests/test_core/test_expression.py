import ast

import pytest

from peval.core.expression import peval_expression
from peval.core.gensym import GenSym
from peval.decorators import pure_function

from tests.utils import assert_ast_equal


def expression_ast(source):
    return ast.parse(source).body[0].value


def check_peval_expression(source, bindings, expected_source,
        fully_evaluated=False, expected_value=None, expected_temp_bindings=None):

    source_tree = expression_ast(source)
    expected_tree = expression_ast(expected_source)

    gen_sym = GenSym()
    gen_sym, result = peval_expression(gen_sym, bindings, source_tree)

    assert result.fully_evaluated == fully_evaluated
    if fully_evaluated:
        assert result.value == expected_value

    assert_ast_equal(result.node, expected_tree)

    if expected_temp_bindings is not None:
        for key, val in expected_temp_bindings.items():
            assert key in result.temp_bindings
            assert result.temp_bindings[key] == expected_temp_bindings[key]


def test_partial_bin_op():
    check_peval_expression(
        "5 + 6 + a", {},
        "11 + a")


def test_full_bin_op():
    check_peval_expression(
        "5 + 6 + a", dict(a=7),
        "18",
        fully_evaluated=True, expected_value=18)


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


def test_propagation_named_constant():
    check_peval_expression(
        'foo', dict(foo=False),
        'False',
        fully_evaluated=True, expected_value=False)
    check_peval_expression(
        'foo', dict(foo=True),
        'True',
        fully_evaluated=True, expected_value=True)
    check_peval_expression(
        'foo', dict(foo=None),
        'None',
        fully_evaluated=True, expected_value=None)


def test_propagation_subclass():
    """
    Test that constant propogation does not happen on primitive subclasses
    """

    # Currently when wrapping a value in an AST node,
    # we do not check whether this value is already bound to some variable
    # (which is often the case).
    # This makes this test fail.
    pytest.xfail()

    class Int(int): pass
    check_peval_expression(
        'm * n', dict(m=Int(2)),
        'm * n')
    check_peval_expression(
        'm * n', dict(m=Int(2), n=3),
        'm * 3')

    class Float(float): pass
    check_peval_expression(
        'm * n', dict(m=Float(2.0)),
        'm * n')

    class Text(six.text_type): pass
    check_peval_expression(
        'm + n', dict(m=Text(six.u('foo'))),
        'm + n')

    class Binary(six.binary_type): pass
    check_peval_expression(
        'm + n', dict(m=Binary(six.b('foo'))),
        'm + n')


def test_call_no_args():
    @pure_function
    def fn():
        return 'Hi!'
    check_peval_expression(
        'fn()', dict(fn=fn), '"Hi!"',
        fully_evaluated=True, expected_value='Hi!')


def test_call_with_args():

    # Currently when wrapping a value in an AST node,
    # we do not check whether this value is already bound to some variable
    # (which is often the case).
    # This makes this test fail.
    pytest.xfail()

    @pure_function
    def fn(x, y):
        return x + [y]
    check_peval_expression('fn(x, y)', dict(fn=fn, x=10), 'fn(10, y)')
    check_peval_expression(
            'fn(x, y)',
            dict(fn=fn, x=[10], y=20.0),
            '__binding_1',
            expected_temp_bindings=dict(__binding_1=[10, 20.0]))


def test_exception():
    """
    A pure function which throws an exception during partial evaluation
    is left unevaluated.
    """

    # Exception catching is not implemented yet
    pytest.xfail()

    @pure_function
    def fn():
        return 1 / 0
    check_peval_expression('fn()', dict(fn=fn), 'fn()')


def test_evaluate_builtins():
    """
    Test that we can evaluate builtins
    """

    # Builtin recognition is not implemented yet
    pytest.xfail()

    check_peval_expression('isinstance(n, int)', dict(n=10), 'True')


def test_not():

    # UnaryOp processing is not implemented yet
    pytest.xfail()

    check_peval_expression('not x', dict(x="s"), 'False')
    check_peval_expression('not x', dict(x=0), 'True')
    check_peval_expression('not 1', dict(), 'False')
    check_peval_expression('not False', dict(), 'True')


def test_and():

    # BoolOp processing is not implemented yet
    pytest.xfail()

    check_peval_expression('a and b', dict(a=False), 'False')
    check_peval_expression('a and b', dict(a=True), 'b')
    check_peval_expression(
        'a and b()', dict(a=True, b=pure_function(lambda: True)),
        'True')
    check_peval_expression(
        'a and b and c and d', dict(a=True, c=True),
        'b and d')

def test_and_short_circuit():

    # BoolOp processing is not implemented yet
    pytest.xfail()

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_peval_expression('a and inc()', dict(a=False, inc=inc), 'False')
    assert global_state['cnt'] == 0

    check_peval_expression('a and inc()', dict(a=True, inc=inc), 'True')
    assert global_state['cnt'] == 1


def test_or():

    # BoolOp processing is not implemented yet
    pytest.xfail()

    check_peval_expression('a or b', dict(a=False), 'b')
    check_peval_expression('a or b', dict(a=True), 'True')
    check_peval_expression('a or b', dict(a=False, b=False), 'False')
    check_peval_expression(
            'a or b()', dict(a=False, b=pure_function(lambda: True)),
            'True')
    check_peval_expression('a or b or c or d', dict(a=False, c=False), 'b or d')


def test_or_short_circuit():

    # BoolOp processing is not implemented yet
    pytest.xfail()

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_peval_expression('a or inc()', dict(a=True, inc=inc), 'True')
    assert global_state['cnt'] == 0

    check_peval_expression('a or inc()', dict(a=False, inc=inc), 'True')
    assert global_state['cnt'] == 1


def test_eq():

    # BoolOp processing is not implemented yet
    pytest.xfail()

    check_peval_expression('0 == 0', {}, 'True')
    check_peval_expression('0 == 1', {}, 'False')
    check_peval_expression('a == b', dict(a=1), '1 == b')
    check_peval_expression('a == b', dict(b=1), 'a == 1')
    check_peval_expression('a == b', dict(a=1, b=1), 'True')
    check_peval_expression('a == b', dict(a=2, b=1), 'False')
    check_peval_expression(
            'a == b == c == d', dict(a=2, c=2),
            '2 == b == 2 == d')


def test_mix():

    # multivalue Compare processing is not implemented yet
    pytest.xfail()

    check_peval_expression('a < b >= c', dict(a=0, b=1, c=1), 'True')
    check_peval_expression('a <= b > c', dict(a=0, b=1, c=1), 'False')


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
