# -*- encoding: utf-8 -*-
import six
import ast

from peval.utils import get_fn_arg_id
from peval.function import Function
from peval.optimizer import optimized_ast


def specialized_fn(fn, globals_, locals_, *args, **kwargs):
    ''' Return specialized version of fn, fixing given args and kwargs,
    just as functools.partial does, but specialized function should be faster
    '''
    assert isinstance(globals_, dict) and isinstance(locals_, dict)
    globals_ = dict(globals_)
    globals_.update(locals_)
    function = Function.from_object(fn)
    specialized_tree, bindings = specialized_ast(
        function.tree, globals_, *args, **kwargs)
    globals_.update(bindings)
    new_function = function.replace(tree=specialized_tree.body[0], globals_=globals_)
    return new_function.eval()


def specialized_ast(fn_ast, global_bindings, *args, **kwargs):
    ''' Return AST of specialized function, and dict with closure bindings.
    args and kwargs have the same meaning as in functools.partial.
    Here we just handle the args and kwargs of function defenition.
    '''
    constants = dict(global_bindings)
    fn_args = fn_ast.args

    assert not fn_args.vararg and not fn_args.kwarg
    if args:
        for arg, value in zip(fn_args.args[:len(args)], args):
            constants[get_fn_arg_id(arg)] = value
        # Remove positional defaults, if some of user-provided args cover them.
        if len(args) > len(fn_args.args) - len(fn_args.defaults):
            del fn_args.defaults[:len(args) - (len(fn_args.args) - len(fn_args.defaults))]
        del fn_args.args[:len(args)]
    if kwargs:
        arg_by_id = dict((get_fn_arg_id(arg), arg) for arg in fn_args.args)
        for kwarg_name, kwarg_value in six.iteritems(kwargs):
            constants[kwarg_name] = kwarg_value
            fn_args.args.remove(arg_by_id[kwarg_name])
    return optimized_ast(ast.Module(body=[fn_ast]), constants)
