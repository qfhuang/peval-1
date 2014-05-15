import ast
import copy

from peval.utils import replace_fields
from peval.core.symbol_finder import find_symbol_creations
from peval.core.walker import ast_transformer


def remove_assignments(node, constants):
    node = simplify(node)
    return node, constants


@ast_transformer
class simplify:
    ''' Simplify AST, given information about what variables are known
    '''
    @staticmethod
    def handle_FunctionDef(node, **kwds):
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
    return _replace(node, ctx=dict(var_name=var_name, value_node=value_node))


@ast_transformer
class _replace:
    ''' Replaces uses of var_name with value_node
    '''

    @staticmethod
    def handle_Name(node, ctx, **kwds):
        if isinstance(node.ctx, ast.Load) and node.id == ctx.var_name:
            return ctx.value_node
        else:
            return node
