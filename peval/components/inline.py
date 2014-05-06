import ast
import copy
import sys

from peval.utils import get_fn_arg_id, get_literal_node, get_node_value_if_known
from peval.core.function import Function
from peval.core.mangler import mangle
from peval.core.gensym import GenSym
from peval.core.visitor import Visitor


def inline(tree, constants):
    tree = copy.deepcopy(tree)
    gen_sym = GenSym(tree)
    visitor = Inliner(dict(constants), gen_sym)
    visitor.visit(tree)
    return tree, visitor._constants


class Inliner(Visitor):
    ''' Simplify AST, given information about what variables are known
    '''

    def __init__(self, constants, gen_sym):
        super(Inliner, self).__init__()
        self._constants = constants
        self._gen_sym = gen_sym

    def visit_Call(self, node):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        Inline function if it is marked with @inline.
        '''
        is_known, fn = get_node_value_if_known(node.func, self._constants)
        if is_known and is_inlined_fn(fn):
            inlined_body, result_node, new_gen_sym_state, self._constants = \
                _inline(fn, node, self._gen_sym.get_state(), self._constants)
            self._gen_sym.set_state(new_gen_sym_state)

            #inlined_body = self._visit(inlined_body) # optimize inlined code

            self._current_block.extend(inlined_body)
            return result_node
        else:
            self.generic_visit(node)
            return node


def is_inlined_fn(fn):
    ''' fn should be inlined
    '''
    return getattr(fn, '_peval_inline', False)


def _inline(fn, node, gen_sym_state, constants):
    ''' Return a list of nodes, representing inlined function call,
    and a node, repesenting the variable that stores result.
    '''
    fn_ast = Function.from_object(fn).tree
    constants = dict(constants)

    new_fn_ast, new_gen_sym_state, return_var = mangle(fn_ast, gen_sym_state)
    gen_sym = GenSym.from_state(gen_sym_state)

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
        while_var = gen_sym('while')
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

    return inlined_body, ast.Name(id=return_var, ctx=ast.Load()), gen_sym.get_state(), constants
