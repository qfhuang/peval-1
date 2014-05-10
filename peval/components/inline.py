import ast
import copy
import sys

from peval.utils import get_fn_arg_id, get_literal_node, get_node_value_if_known
from peval.core.function import Function
from peval.core.mangler import mangle
from peval.core.gensym import GenSym
from peval.core.walker import Walker


def inline(tree, constants):
    gen_sym = GenSym.for_tree(tree)
    constants = dict(constants)
    tree, state = inliner.transform_inspect(
        tree, state=dict(gen_sym=gen_sym, constants=constants))
    return tree, state['constants']


@Walker
def inliner(node, state, prepend, **kwds):
    ''' Make a call, if it is a pure function,
    and handle mutations otherwise.
    Inline function if it is marked with @inline.
    '''
    if isinstance(node, ast.Call):
        gen_sym = state['gen_sym']
        constants = state['constants']

        is_known, fn = get_node_value_if_known(node.func, constants)
        if is_known and is_inlined_fn(fn):
            gen_sym, return_name = gen_sym('return')
            gen_sym, inlined_body, constants = _inline(gen_sym, node, return_name, constants)

            prepend(inlined_body)
            state['constants'] = constants
            state['gen_sym'] = gen_sym

            return ast.Name(id=return_name, ctx=ast.Load())
        else:
            return node
    else:
        return node


def is_inlined_fn(fn):
    ''' fn should be inlined
    '''
    return getattr(fn, '_peval_inline', False)


def _inline(gen_sym, node, return_name, constants):
    ''' Return a list of nodes, representing inlined function call,
    and a node, repesenting the variable that stores result.
    '''
    fn = constants[node.func.id]
    fn_ast = Function.from_object(fn).tree
    constants = dict(constants)

    gen_sym, new_fn_ast = mangle(gen_sym, fn_ast, return_name)

    inlined_body = []
    assert not node.kwargs and not node.starargs
    for callee_arg, fn_arg in zip(node.args, new_fn_ast.args.args):
        # setup mangled values before call
        arg_id = get_fn_arg_id(fn_arg)
        inlined_body.append(ast.Assign(
            targets=[ast.Name(arg_id, ast.Store())],
            value=callee_arg))
        is_known, value = get_node_value_if_known(callee_arg, constants)
        if is_known:
            constants[arg_id] = value

    inlined_code = new_fn_ast.body

    if isinstance(inlined_code[-1], ast.Break): # single return
        inlined_body.extend(inlined_code[:-1])
    else: # multiple returns - wrap in "while"
        gen_sym, while_var = gen_sym('while')
        inlined_body.extend([
            ast.Assign(
                targets=[ast.Name(id=while_var, ctx=ast.Store())],
                value=get_literal_node(True)),
            ast.While(
                test=ast.Name(id=while_var, ctx=ast.Load()),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=while_var, ctx=ast.Store())],
                        value=get_literal_node(False))] +
                    inlined_code,
                orelse=[])
            ])

    return gen_sym, inlined_body, constants
