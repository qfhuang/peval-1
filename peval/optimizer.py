import ast
import copy

from peval.components.inline import inline_functions
from peval.components.var_simplifier import remove_assignments
from peval.components.prune_cfg import prune_cfg
from peval.utils import ast_equal


def optimized_ast(tree, constants):
    while True:
        new_tree = tree
        new_constants = constants

        for func in (inline_functions, remove_assignments, prune_cfg):
            new_tree, new_constants = func(new_tree, new_constants)

        if ast_equal(new_tree, tree) and new_constants == constants:
            break

        tree = new_tree
        constants = new_constants

    return new_tree, new_constants
