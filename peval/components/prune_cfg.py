import ast
import copy

from peval.utils import replace_fields
from peval.core.expression import try_peval_expression
from peval.core.walker import ast_transformer


def prune_cfg(node, bindings):
    node = remove_unreachable_statements(node, ctx=dict(bindings=bindings))
    node = simplify_loops(node, ctx=dict(bindings=bindings))
    node = remove_unreachable_branches(node, ctx=dict(bindings=bindings))
    return node, bindings


@ast_transformer
def remove_unreachable_statements(node, walk_field, **kwds):
    for attr in ('body', 'orelse'):
        if hasattr(node, attr):
            old_list = getattr(node, attr)
            new_list = filter_block(old_list)
            if new_list is not old_list:
                new_list = walk_field(new_list, block_context=True)
                kwds = {attr: new_list}
                node = replace_fields(node, **kwds)
    return node


def filter_block(node_list):
    """
    Remove no-op code (``pass``), or any code after
    an unconditional jump (``return``, ``break``, ``continue``, ``raise``).
    """
    if len(node_list) == 1:
        return node_list

    new_list = []
    for node in node_list:
        if type(node) == ast.Pass:
            continue
        new_list.append(node)
        if type(node) in (ast.Return, ast.Break, ast.Continue, ast.Raise):
            break
    if len(new_list) == len(node_list):
        return node_list
    else:
        return new_list


@ast_transformer
class simplify_loops:

    @staticmethod
    def handle_While(node, **kwds):
        last_node = node.body[-1]
        unconditional_jump = type(last_node) in (ast.Break, ast.Raise, ast.Return)
        if unconditional_jump:
            if type(last_node) == ast.Break:
                new_body = node.body[:-1]
            else:
                new_body = node.body
            return ast.If(test=node.test, body=new_body, orelse=node.orelse)
        else:
            return node


@ast_transformer
class remove_unreachable_branches:

    @staticmethod
    def handle_If(node, ctx, walk_field, **kwds):
        evaluated, test = try_peval_expression(node.test, ctx.bindings)
        if evaluated:
            taken_node = node.body if test else node.orelse
            new_node = walk_field(taken_node, block_context=True)
            return new_node
        else:
            return node
