# -*- encoding: utf-8 -*-
import six
import ast

from peval.utils import get_fn_arg_id
from peval.function import Function
from peval.optimizer import optimized_ast


def specialized_fn(fn, *args, **kwargs):
    ''' Return specialized version of fn, fixing given args and kwargs,
    just as functools.partial does, but specialized function should be faster
    '''
    function = Function.from_object(fn)

    bound_function = function.bind_partial(*args, **kwargs)

    new_module, bindings = optimized_ast(
        ast.Module(body=[bound_function.tree]), bound_function.globals)

    new_tree = new_module.body[0]
    globals_ = dict(bound_function.globals)
    globals_.update(bindings)

    new_function = bound_function.replace(tree=new_tree, globals_=globals_)

    return new_function.eval()
