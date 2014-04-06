import ast
import copy

from peval.function import Function


global_var = 1


def global_var_writer(x):
    global global_var
    global_var = x


def global_var_reader():
    return global_var


def make_one_var_closure():
    closure_var = [1]
    def closure():
        some_local_var = 3
        closure_var[0] += 1
        return closure_var[0]
    return closure


def make_two_var_closure():
    closure_var1 = [1]
    closure_var2 = [2]
    def closure():
        some_local_var = closure_var1[0]
        closure_var2[0] += 1
        return closure_var2[0]
    return closure


def dummy_func(a, b, c=4, d=5):
    return a, b, c, d


def dummy_func_arg_groups(a, b, *args, **kwds):
    return a, b, args, kwargs


def test_bind_partial_args():

    func = Function.from_object(dummy_func)

    new_func = func.bind_partial(1)
    assert new_func.globals['a'] == 1
    assert 'a' not in new_func.signature.parameters
    assert 'b' in new_func.signature.parameters
    assert 'c' in new_func.signature.parameters
    assert 'd' in new_func.signature.parameters


def test_bind_partial_kwds():

    func = Function.from_object(dummy_func)

    new_func = func.bind_partial(1, d=10)
    assert new_func.globals['a'] == 1
    assert new_func.globals['d'] == 10
    assert 'a' not in new_func.signature.parameters
    assert 'b' in new_func.signature.parameters
    assert 'c' in new_func.signature.parameters
    assert 'd' not in new_func.signature.parameters


def test_bind_partial_varargs():

    func = Function.from_object(dummy_func_arg_groups)

    new_func = func.bind_partial(1, 2, 3)
    assert new_func.globals['a'] == 1
    assert new_func.globals['b'] == 2
    assert new_func.globals['args'] == (3,)
    assert 'a' not in new_func.signature.parameters
    assert 'b' not in new_func.signature.parameters
    assert 'args' not in new_func.signature.parameters


def test_bind_partial_varkwds():

    func = Function.from_object(dummy_func_arg_groups)

    new_func = func.bind_partial(1, 2, 3)
    assert new_func.globals['a'] == 1
    assert new_func.globals['b'] == 2
    assert new_func.globals['args'] == (3,)
    assert 'a' not in new_func.signature.parameters
    assert 'b' not in new_func.signature.parameters
    assert 'args' not in new_func.signature.parameters


def test_globals_contents():

    func = Function.from_object(make_one_var_closure())

    assert 'global_var' in func.globals
    assert 'closure_var' not in func.globals


def test_closure_contents():

    func = Function.from_object(make_one_var_closure())

    assert 'global_var' not in func.closure_names
    assert 'closure_var' in func.closure_names


def test_restore_globals():

    global_var_writer(10)
    assert global_var_reader() == 10
    assert global_var == 10

    reader = Function.from_object(global_var_reader).eval()
    writer = Function.from_object(global_var_writer).eval()

    writer(20)
    assert reader() == 20
    assert global_var == 20


def test_restore_simple_closure():

    closure_ref = make_one_var_closure()
    assert closure_ref() == 2

    closure = Function.from_object(closure_ref).eval()
    assert closure() == 3
    assert closure_ref() == 4


def test_restore_modified_closure():

    def remove_first_line(node):
        assert isinstance(node, ast.FunctionDef)
        node = copy.deepcopy(node)
        node.body = node.body[1:]
        return node

    closure_ref = make_two_var_closure()
    assert closure_ref() == 3

    closure = Function.from_object(closure_ref)
    closure = closure.replace(tree=remove_first_line(closure.tree)).eval()

    assert closure() == 4
    assert closure_ref() == 5


def recursive_outer(x):
    if x > 1:
        return recursive_outer(x - 1)
    else:
        return x


def make_recursive():
    def recursive_inner(x):
        if x > 2:
            return recursive_inner(x - 1)
        else:
            return x
    return recursive_inner


def test_recursive_call():
    # When evaluated inside a fake closure (to detect closure variables),
    # the function name will be included in the list of closure variables.
    func = Function.from_object(recursive_outer)
    func = func.replace()
    func = func.eval()
    assert func(10) == 1

    func = Function.from_object(make_recursive())
    func = func.replace()
    func = func.eval()
    assert func(10) == 2
