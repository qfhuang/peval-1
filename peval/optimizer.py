import ast
import copy

from peval.inline import inline
from peval.evaluate import evaluate
from peval.var_simplifier import remove_assignments
from peval.eliminate import eliminate
from peval.while_remover import while_remover


def optimized_ast(tree, constants):
    while True:
        new_tree = tree
        new_constants = constants

        for func in (inline, evaluate, remove_assignments, eliminate, while_remover):
            new_tree, new_constants = func(new_tree, new_constants)

        if ast.dump(new_tree) == ast.dump(tree) and new_constants == constants:
            break

        tree = new_tree
        constants = new_constants

    return new_tree, new_constants
