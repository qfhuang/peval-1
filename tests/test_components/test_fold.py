import ast
import inspect

from peval.components.fold import fold


def get_body(function):
    src = inspect.getsource(function)
    return ast.parse(src).body[0].body


def dummy(x):
    a = 1
    if a > 2:
        b = 3
        c = 4 + 6
    else:
        b = 2
        c = 3 + a
    return a + b + c + x


def test_fold():
    statements = get_body(dummy)
    new_tree, new_constants = fold(statements, {})
