import ast

from peval.core.function import Function
from peval.components.inline import inline_functions
from peval.components.prune_cfg import prune_cfg
from peval.components.prune_assignments import prune_assignments
from peval.components.fold import fold
from peval.tools import ast_equal


def partial_apply(fn, *args, **kwds):
    ''' Return specialized version of fn, fixing given args and kwargs,
    just as functools.partial does, but specialized function should be faster
    '''
    function = Function.from_object(fn)

    if len(args) > 0 or len(kwds) > 0:
        bound_function = function.bind_partial(*args, **kwds)
    else:
        bound_function = function

    new_tree, bindings = optimized_ast(
        bound_function.tree,
        bound_function.get_external_variables())

    globals_ = dict(bound_function.globals)
    globals_.update(bindings)

    new_function = bound_function.replace(tree=new_tree, globals_=globals_)

    return new_function.eval()


def partial_eval(fn):
    return partial_apply(fn)


def optimized_ast(tree, constants):
    while True:
        new_tree = tree
        new_constants = constants

        for func in (inline_functions, fold, prune_cfg, prune_assignments):
            new_tree, new_constants = func(new_tree, new_constants)

        if ast_equal(new_tree, tree) and new_constants == constants:
            break

        tree = new_tree
        constants = new_constants

    return new_tree, new_constants
