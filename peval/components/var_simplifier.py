import ast
import copy

from peval.core.symbol_finder import find_symbol_creations
from peval.core.walker import Walker


def remove_assignments(node, constants):
    node = Simplifier.transform(node)
    return node, constants


def replace_fields(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


@Walker
class Simplifier:
    ''' Simplify AST, given information about what variables are known
    '''
    @staticmethod
    def visit_functiondef(node, **kwds):
        return replace_fields(node, body=_remove_assignments(node.body))


def _remove_assignments(node_list):
    ''' Remove one assigment at a time, touching only top level block
    (i.e. not going inside while, if, for etc)
    '''
    remaining_nodes = list(node_list)
    new_nodes = []

    while len(remaining_nodes) > 0:
        node = remaining_nodes.pop(0)
        if isinstance(node, ast.Assign):
            can_remove, var_name, value_node = _can_remove_assignment(node, remaining_nodes)
            if can_remove:
                remaining_nodes = [replace(n, var_name, value_node) for n in remaining_nodes]
            else:
                new_nodes.append(node)
        else:
            new_nodes.append(node)

    return new_nodes


def _can_remove_assignment(assign_node, node_list):
    ''' Can remove it if:
     * it is "simple"
     * result it not used in "Store" context elsewhere
    '''
    if len(assign_node.targets) == 1 and isinstance(assign_node.targets[0], ast.Name):
        value_node = assign_node.value
        if isinstance(value_node, (ast.Name, ast.Num, ast.Str)):
            # value_node is "simple"
            assigned_name = assign_node.targets[0].id
            if assigned_name not in find_symbol_creations(node_list):
                return True, assigned_name, value_node
    return False, None, None


def replace(node, var_name, value_node):
    return Replacer.transform(node, ctx=dict(var_name=var_name, value_node=value_node))


@Walker
class Replacer:
    ''' Replaces uses of var_name with value_node
    '''

    @staticmethod
    def visit_name(node, ctx, **kwds):
        if isinstance(node.ctx, ast.Load) and node.id == ctx.var_name:
            return ctx.value_node
        else:
            return node
