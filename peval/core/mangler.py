import ast
import copy

from peval.tools import immutabledict, ast_walker
from peval.core.gensym import GenSym
from peval.core.symbol_finder import find_symbol_creations


def _visit_local(gen_sym, node, to_mangle, mangled):
    ''' Replacing known variables with literal values
    '''
    is_name = type(node) == ast.Name

    node_id = node.id if is_name else node.arg

    if node_id in to_mangle:

        if node_id in mangled:
            mangled_id = mangled[node_id]
        else:
            mangled_id, gen_sym = gen_sym('mangled')
            mangled = mangled.set(node_id, mangled_id)

        if is_name:
            node = ast.Name(id=mangled_id, ctx=node.ctx)
        else:
            node = ast.arg(arg=mangled_id, annotation=node.annotation)

    return gen_sym, node, mangled


@ast_walker
class _mangle:
    ''' Mangle all variable names, returns.
    '''

    @staticmethod
    def handle_arg(node, state, ctx, **kwds):
        gen_sym, new_node, mangled = _visit_local(
            state.gen_sym, node, ctx.fn_locals, state.mangled)
        new_state = state.update(gen_sym=gen_sym, mangled=mangled)
        return new_node, new_state

    @staticmethod
    def handle_Name(node, state, ctx, **kwds):
        gen_sym, new_node, mangled = _visit_local(
            state.gen_sym, node, ctx.fn_locals, state.mangled)
        new_state = state.update(gen_sym=gen_sym, mangled=mangled)
        return new_node, new_state


def mangle(gen_sym, node):
    fn_locals = find_symbol_creations(node)
    new_node, state = _mangle(
        node,
        state=dict(gen_sym=gen_sym, mangled=immutabledict()),
        ctx=dict(fn_locals=fn_locals))
    return state.gen_sym, new_node
