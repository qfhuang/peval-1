import ast
import copy
import sys

from peval.tags import is_inline
from peval.core.value import value_to_node
from peval.core.expression import try_peval_expression
from peval.core.function import Function
from peval.core.mangler import mangle
from peval.core.gensym import GenSym
from peval.tools import get_fn_arg_id, ast_walker, replace_fields


def inline_functions(tree, constants):
    gen_sym = GenSym.for_tree(tree)
    constants = dict(constants)
    tree, state = inliner(
        tree, state=dict(gen_sym=gen_sym, constants=constants))
    return tree, state.constants


@ast_walker
def inliner(node, state, prepend, **kwds):
    """
    If the function in a Call node is known and inlineable, inline it.
    """
    if type(node) == ast.Call:
        gen_sym = state.gen_sym
        constants = state.constants

        evaluated, fn = try_peval_expression(node.func, constants)

        if evaluated and is_inline(fn):
            return_name, gen_sym = gen_sym('return')
            inlined_body, gen_sym, constants = _inline(node, gen_sym, return_name, constants)
            prepend(inlined_body)
            new_state = state.update(gen_sym=gen_sym, constants=constants)

            return ast.Name(id=return_name, ctx=ast.Load()), new_state
        else:
            return node, state
    else:
        return node, state


def _inline(node, gen_sym, return_name, constants):
    """
    Return a list of nodes, representing inlined function call.
    """
    fn = constants[node.func.id]
    fn_ast = Function.from_object(fn).tree
    constants = dict(constants)

    gen_sym, new_fn_ast = mangle(gen_sym, fn_ast, return_name)

    parameter_assignments = _build_parameter_assignments(node, fn_ast.args)

    return_flag, gen_sym = gen_sym('return_flag')
    true_node, gen_sym, true_binding = value_to_node(True, gen_sym)
    constants.update(true_binding)

    body_nodes = new_fn_ast.body
    if type(body_nodes[-1]) != ast.Return:
        none_node, gen_sym, none_binding = value_to_node(None, gen_sym)
        constants.update(none_binding)
        body_nodes = body_nodes + [ast.Return(value=none_node)]

    inlined_code, returns_ctr = _replace_returns(
        body_nodes, return_name, return_flag, true_node)

    if returns_ctr == 1 and type(inlined_code[-1]) == ast.Break:
    # A shortcut for a common case wit a single return in the end of the function.
    # No loop is required.
        inlined_body = parameter_assignments + inlined_code[:-1]
    else:
    # Multiple returns - wrap in a `while` loop.
        inlined_body = list(parameter_assignments)

        if returns_in_loops:
            # `return_flag` value will be used to detect returns from nested loops
            false_node, gen_sym, false_binding = value_to_node(False, gen_sym)
            constants.update(false_binding)

            inlined_body.append(
                ast.Assign(
                    targets=[ast.Name(return_flag, ast.Store())],
                    value=false_node))

        inlined_body.append(
            ast.While(
                test=true_node,
                body=inlined_code))

    return inlined_body, gen_sym, constants


def _build_parameter_assignments(call_node, args_node):
    assert not call_node.starargs and not call_node.kwargs
    parameter_assignments = []
    for callee_arg, fn_arg in zip(call_node.args, args_node.args):
        arg_id = get_fn_arg_id(fn_arg)
        parameter_assignments.append(ast.Assign(
            targets=[ast.Name(arg_id, ast.Store())],
            value=callee_arg))
    return parameter_assignments


def _handle_loop(node, state, ctx, visit_after, visiting_after, walk_field, **kwds):
    if not visiting_after:
        # Need to traverse fields explicitly since for the purposes of _replace_returns(),
        # the body of `orelse` field is not inside a loop.
        state = state.update(loop_nesting_ctr=state.loop_nesting_ctr + 1)
        new_body, state = walk_field(node.body, state, block_context=True)
        state = state.update(loop_nesting_ctr=state.loop_nesting_ctr - 1)
        new_orelse, state = walk_field(node.orelse, state, block_context=True)

        visit_after()
        return replace_fields(node, body=new_body, orelse=new_orelse), state
    else:
        # If there was a return inside a loop, append a conditional break
        # to propagate the return otside all nested loops
        if state.return_inside_a_loop:
            new_nodes = [
                node,
                ast.If(
                    test=ast.Name(id=ctx.return_flag_var),
                    body=[ast.Break()],
                    orelse=[])]
        else:
            new_nodes = node

        # if we are at root level, reset the return-inside-a-loop flag
        if state.loop_nesting_ctr == 0:
            state = state.update(return_inside_a_loop=False)

        return new_nodes, state


@ast_walker
class _replace_returns_walker:
    """Replace returns with variable assignment + break."""

    @staticmethod
    def handle_For(node, state, ctx, visit_after, visiting_after, **kwds):
        return _handle_loop(node, state, ctx, visit_after, visiting_after, **kwds)

    @staticmethod
    def handle_While(node, state, ctx, visit_after, visiting_after, **kwds):
        return _handle_loop(node, state, ctx, visit_after, visiting_after, **kwds)

    @staticmethod
    def handle_Return(node, state, ctx, **kwds):

        state_update = dict(returns_ctr=state.returns_ctr + 1)

        new_nodes = [
            ast.Assign(
                targets=[ast.Name(id=ctx.return_var, ctx=ast.Store())],
                value=node.value)]

        if state.loop_nesting_ctr > 0:
            new_nodes.append(
                ast.Assign(
                    targets=[ast.Name(id=ctx.return_flag_var, ctx=ast.Store())],
                    value=ctx.true_node))
            state_update.update(return_inside_a_loop=True, returns_in_loops=True)

        new_nodes.append(ast.Break())

        return new_nodes, state.update(state_update)


def _replace_returns(nodes, return_var, return_flag_var, true_node):
    new_nodes, state = _replace_returns_walker(
        nodes,
        state=dict(
            returns_ctr=0, loop_nesting_ctr=0,
            returns_in_loops=False, return_inside_a_loop=False),
        ctx=dict(return_var=return_var, return_flag_var=return_flag_var, true_node=true_node))
    return new_nodes, state.returns_ctr, state.returns_in_loops
