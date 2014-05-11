import ast
import copy

from peval.core.symbol_finder import find_symbol_creations
from peval.core.gensym import GenSym
from peval.core.walker import ast_walker


def _visit_local(gen_sym, node, to_mangle, mangled):
    ''' Replacing known variables with literal values
    '''
    is_name = isinstance(node, ast.Name)

    node_id = node.id if is_name else node.arg
    if node_id in to_mangle:
        if node_id in mangled:
            mangled_id = mangled[node_id]
        else:
            gen_sym, mangled_id = gen_sym('mangled')
            mangled[node_id] = mangled_id
        if is_name:
            return gen_sym, ast.Name(id=mangled_id, ctx=node.ctx)
        else:
            return gen_sym, ast.arg(arg=mangled_id, annotation=node.annotation)
    else:
        return gen_sym, node


@ast_walker
class _mangle:
    ''' Mangle all variable names, returns.
    '''

    @staticmethod
    def visit_arg(node, state, ctx, **kwds):
        state['gen_sym'], node = _visit_local(
            state['gen_sym'], node, ctx.fn_locals, state['mangled'])
        return node

    @staticmethod
    def visit_Name(node, state, ctx, **kwds):
        state['gen_sym'], node = _visit_local(
            state['gen_sym'], node, ctx.fn_locals, state['mangled'])
        return node

    @staticmethod
    def visit_Return(node, state, ctx, **kwds):
        ''' Substitute return with return variable assignment + break
        '''
        new_value, sub_state = _mangle(
            node.value,
            state=dict(gen_sym=state['gen_sym'], mangled=state['mangled']),
            ctx=dict(fn_locals=ctx.fn_locals, return_name=ctx.return_name))
        state['gen_sym'] = sub_state['gen_sym']
        state['mangled'] = sub_state['mangled']

        return [ast.Assign(
                    targets=[ast.Name(id=ctx.return_name, ctx=ast.Store())],
                    value=new_value),
                ast.Break()]


def mangle(gen_sym, node, return_name):
    fn_locals = find_symbol_creations(node)
    new_node, state = _mangle(
        node,
        state=dict(gen_sym=gen_sym, mangled={}),
        ctx=dict(fn_locals=fn_locals, return_name=return_name))
    return state['gen_sym'], new_node
