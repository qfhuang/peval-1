import ast
import copy

from peval.symbol_finder import find_symbol_creations
from peval.visitor import Visitor


def remove_assignments(tree, _):
    tree = copy.deepcopy(tree)
    visitor = Simplifier()
    visitor.visit(tree)
    return tree, _


def replace_node(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


class Simplifier(Visitor):
    ''' Simplify AST, given information about what variables are known
    '''
    def visit_FunctionDef(self, node):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        Inline function if it is marked with @inline.
        '''
        self.generic_visit(node)
        return replace_node(node, body=_remove_assignments(node.body))


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
    ''' Can remove it iff:
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
    node = copy.deepcopy(node)
    visitor = Replacer(var_name, value_node)
    node = visitor.visit(node)
    return node


class Replacer(ast.NodeTransformer):
    ''' Replaces uses of var_name with value_node
    '''
    def __init__(self, var_name, value_node):
        self.var_name = var_name
        self.value_node = value_node
        super(Replacer, self).__init__()

    def visit_Name(self, node):
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load) and node.id == self.var_name:
            return self.value_node
        else:
            return node
