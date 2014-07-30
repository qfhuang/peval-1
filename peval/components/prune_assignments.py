import ast
import copy

from peval.tools import (
    ast_transformer, ast_inspector, ast_walker, replace_fields, immutabledict, immutableset)
from peval.core.symbol_finder import find_symbol_usages, find_symbol_creations


def prune_assignments(node, constants):
    used_symbols = find_symbol_usages(node.body)
    node = remove_unused_assignments(node, ctx=dict(used_symbols=used_symbols))

    node = remove_simple_assignments(node)

    return node, constants


@ast_transformer
class remove_unused_assignments:
    @staticmethod
    def handle_Assign(node, ctx, **kwds):
        if all(type(target) == ast.Name for target in node.targets):
            names = set(target.id for target in node.targets)
            if ctx.used_symbols.isdisjoint(names):
                return None
            else:
                return node
        else:
            return node


def remove_simple_assignments(node):
    """
    Remove one assigment at a time, touching only the top level block.
    """

    remaining_nodes = list(node.body)
    new_nodes = []

    while len(remaining_nodes) > 0:
        cur_node = remaining_nodes.pop(0)
        if type(cur_node) == ast.Assign:
            can_remove, dest_name, src_name = _can_remove_assignment(cur_node, remaining_nodes)
            if can_remove:
                remaining_nodes = replace_name(
                    remaining_nodes, ctx=dict(dest_name=dest_name, src_name=src_name))
            else:
                new_nodes.append(cur_node)
        else:
            new_nodes.append(cur_node)

    if len(new_nodes) == len(node.body):
        return node

    return replace_fields(node, body=new_nodes)


def _can_remove_assignment(assign_node, node_list):
    """
    Can remove it if:
    * it is "simple"
    * result it not used in "Store" context elsewhere
    """
    if (len(assign_node.targets) == 1 and type(assign_node.targets[0]) == ast.Name
            and type(assign_node.value) == ast.Name):
        src_name = assign_node.value.id
        dest_name = assign_node.targets[0].id
        if dest_name not in find_symbol_creations(node_list):
            return True, dest_name, src_name
    return False, None, None


@ast_transformer
class replace_name:
    @staticmethod
    def handle_Name(node, ctx, **kwds):
        if type(node.ctx) == ast.Load and node.id == ctx.dest_name:
            return replace_fields(node, id=ctx.src_name)
        else:
            return node
