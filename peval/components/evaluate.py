from __future__ import division

import ast
import operator

import six
import sys

from peval.core.gensym import GenSym
from peval.core.function import Function
from peval.utils import get_fn_arg_id, get_literal_node, get_node_value_if_known
from peval.core.walker import ast_walker


def evaluate(ast_tree, constants):
    ''' Try running Optimizer until it finishes without rollback.
    Return optimized AST and a list of bindings that the AST needs.
    '''
    gen_sym = GenSym.for_tree(ast_tree)
    constants = dict(constants)

    state=dict(gen_sym=gen_sym, constants=constants, mutated_nodes=set())

    while True:
        try:
            new_ast, state = optimize(ast_tree, state=state)
        except Rollback:
            # we gathered more knowledge and want to try again
            continue

        return new_ast, constants


NUMBER_TYPES = six.integer_types + (float,)
STRING_TYPES = six.string_types + (six.text_type, six.binary_type)

# build-in functions that return the same result for the same arguments
# and do not change their arguments or global environment
PURE_FUNCTIONS = (
    abs, divmod, staticmethod,
    all, enumerate, int, ord, str,
    any, isinstance, pow, sum,
    issubclass, super,
    bin, iter, property, tuple,
    bool, filter, len, range, type,
    bytearray, float, list,
    callable, format,
    chr, frozenset,
    classmethod, getattr, map, repr,
    max, reversed, zip,
    hasattr, round,
    complex, hash, min, set,
    help, next,
    dict, hex, object, slice,
    dir, id, oct, sorted,
    )

if six.PY2:
    PURE_FUNCTIONS += (
        basestring, unichr, reduce, xrange, unicode, long, cmp, apply, coerce)


class Rollback(Exception):
    pass


@ast_walker
class optimize:
    ''' Simplify AST, given information about what variables are known
    '''

    @staticmethod
    def visit_Module(node, state, **kwds):
        # True if old behavior of division operator is active
        # (truediv for floats, floordiv for integers).
        state['py2_div'] = (six.PY2 and state['constants'].get('division') is not division)
        return node

    @staticmethod
    def visit_ImportFrom(node, state, **kwds):
        # Detecting 'from __future__ import division'
        if node.module == '__future__' and any(alias.name == 'division' for alias in node.names):
            state['py2_div'] = False
        return node

    @staticmethod
    def visit_Name(node, state, **kwds):
        ''' Replacing known variables with literal values
        '''
        if isinstance(node.ctx, ast.Load) and node.id in state['constants']:
            literal_node = get_literal_node(state['constants'][node.id])
            if literal_node is not None:
                return literal_node
            else:
                return node
        else:
            return node

    @staticmethod
    def visit_If(node, state, visit_after, visiting_after, skip_fields, walk_field, **kwds):
        ''' Leave only one branch, if possible
        '''
        new_test = walk_field(node.test)

        is_known, test_value = get_node_value_if_known(new_test, state['constants'])
        if is_known:
            pass_ = ast.Pass()
            taken_node = node.body if test_value else node.orelse
            if taken_node:
                return walk_field(taken_node, block_context=True) or pass_
            else:
                return pass_
        else:
            new_body = walk_field(node.body, block_context=True)
            new_orelse = walk_field(node.orelse, block_context=True)
            return ast.If(test=new_test, body=new_body, orelse=new_orelse)

    @staticmethod
    def visit_Call(node, state, visit_after, visiting_after, **kwds):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        '''
        if not visiting_after:
            visit_after()
            return node

        is_known, fn = get_node_value_if_known(node.func, state['constants'])
        if is_known:
            if _is_pure_fn(fn):
                state['gen_sym'], state['constants'], node = \
                    _fn_result_node_if_safe(state['gen_sym'], fn, node, state['constants'])
                return node
            else:
                return node
        else:
            assert not node.kwargs and not node.starargs
            # check for mutations from function call:
            # if we don't know it's pure, it can mutate the arguments
            for arg_node in node.args:
                if is_load_name(arg_node):
                    _mark_mutated_node(state['mutated_nodes'], state['constants'], arg_node)
                else:
                    # The function argument is an expression.
                    # Technically, this expression can return one of its arguments
                    # and then the function will mutate it.
                    pass
            # if this a method call, it can also mutate "self"
            if isinstance(node.func, ast.Attribute):
                obj_node = node.func.value
                if is_load_name(obj_node):
                    _mark_mutated_node(state['mutated_nodes'], state['constants'], obj_node)
                else:
                    # Well, it is hard, because it can be something like
                    # Fooo(x).transform() that also mutates x.
                    # Above this case will be handled by argument mutation
                    # and dataflow analysis, but maybe there are other cases?
                    pass
        return node

    @staticmethod
    def visit_UnaryOp(node, state, visit_after, visiting_after, **kwds):
        ''' Hanle "not" - evaluate if possible
        '''
        if not visiting_after:
            visit_after()
            return node

        if isinstance(node.op, ast.Not):
            is_known, value = get_node_value_if_known(node.operand, state['constants'])
            if is_known:
                state['gen_sym'], state['constants'], node = \
                    _new_binding_node(state['gen_sym'], state['constants'], not value)
                return node
        return node

    @staticmethod
    def visit_BoolOp(node, state, visit_after, visiting_after, skip_fields, walk_field, **kwds):
        ''' and, or - handle short-circuting
        '''
        assert type(node.op) in (ast.And, ast.Or)

        new_value_nodes = []
        for value_node in node.values:
            new_value_node = walk_field(value_node)
            is_known, value = get_node_value_if_known(new_value_node, state['constants'])
            if is_known:
                if isinstance(node.op, ast.And):
                    if not value:
                        state['gen_sym'], state['constants'], new_node = \
                            _new_binding_node(state['gen_sym'], state['constants'], False)
                        return new_node
                elif isinstance(node.op, ast.Or):
                    if value:
                        state['gen_sym'], state['constants'], new_node = \
                            _new_binding_node(state['gen_sym'], state['constants'], value)
                        return new_node
            else:
                new_value_nodes.append(new_value_node)
        if len(new_value_nodes) == 0:
            state['gen_sym'], state['constants'], new_node = \
                _new_binding_node(state['gen_sym'], state['constants'],
                    isinstance(node.op, ast.And))
            return new_node
        elif len(new_value_nodes) == 1:
            return new_value_nodes[0]
        else:
            return type(node)(op=node.op, values=new_value_nodes)

    @staticmethod
    def visit_Compare(node, state, visit_after, visiting_after, **kwds):
        ''' ==, >, etc. - evaluate only if all are known
        '''
        if not visiting_after:
            visit_after()
            return node

        is_known, value = get_node_value_if_known(node.left, state['constants'])
        if not is_known:
            return node
        value_list = [value]
        for value_node in node.comparators:
            is_known, value = get_node_value_if_known(value_node, state['constants'])
            if not is_known:
                return node
            value_list.append(value)
        for a, b, op in zip(value_list, value_list[1:], node.ops):
            result = {
                    ast.Eq: lambda: a == b,
                    ast.Lt: lambda: a < b,
                    ast.Gt: lambda: a > b,
                    ast.GtE: lambda: a >= b,
                    ast.LtE: lambda: a <= b,
                    ast.NotEq: lambda: a != b,
                    }[type(op)]()
            if not result:
                state['gen_sym'], state['constants'], node = \
                    _new_binding_node(state['gen_sym'], state['constants'], False)
                return node

        state['gen_sym'], state['constants'], node = \
            _new_binding_node(state['gen_sym'], state['constants'], True)
        return node

    @staticmethod
    def visit_BinOp(node, state, visit_after, visiting_after, **kwds):
        ''' Binary arithmetic - + * / etc.
        Evaluate if everything is known.
        '''
        if not visiting_after:
            visit_after()
            return node

        operations = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Mod: operator.mod,
                ast.Pow: operator.pow,
                ast.LShift: operator.lshift,
                ast.RShift: operator.rshift,
                ast.BitOr: operator.or_,
                ast.BitAnd: operator.and_,
                ast.BitXor: operator.xor,
                ast.FloorDiv: operator.floordiv,
                }
        if state['py2_div']:
            operations[ast.Div] = operator.div
        else:
            operations[ast.Div] = operator.truediv

        can_apply = lambda is_known, value: is_known and type(value) in NUMBER_TYPES
        if type(node.op) in operations:
            is_known, l_value = get_node_value_if_known(node.left, state['constants'])
            if can_apply(is_known, l_value):
                is_known, r_value = get_node_value_if_known(node.right, state['constants'])
                if can_apply(is_known, r_value):
                    value = operations[type(node.op)](l_value, r_value)
                    state['gen_sym'], state['constants'], node = \
                        _new_binding_node(state['gen_sym'], state['constants'], value)
                    return node
        return node


def _fn_result_node_if_safe(gen_sym, fn, node, constants):
    ''' Check that we know all fn args.
    Than call it and return a node representing the value.
    It we can not call fn, just return node.
    Assume that fn is pure.
    '''
    assert isinstance(node, ast.Call) and _is_pure_fn(fn)
    args = []
    for arg_node in node.args:
        is_known, value = get_node_value_if_known(arg_node, constants)
        if is_known:
            args.append(value)
        else:
            return gen_sym, constants, node

    assert not node.kwargs and not node.keywords and not node.starargs
    try:
        fn_value = fn(*args)
    except:
        # do not optimize the call away to leave original exception
        return gen_sym, constants, node
    else:
        return _new_binding_node(gen_sym, constants, fn_value)


def _is_pure_fn(fn):
    ''' fn has no side effects, and its value is determined only by
    its inputs
    '''
    if fn in PURE_FUNCTIONS:
        return True
    else:
        return getattr(fn, '_peval_is_pure', False)


def _new_binding_node(gen_sym, constants, value):
    ''' Generate unique variable name, add it to constants with given value,
    and return the node that loads generated variable.
    '''
    literal_node = get_literal_node(value)
    if literal_node is not None:
        return gen_sym, constants, literal_node
    else:
        gen_sym, var_name = gen_sym('binding')
        constants[var_name] = value
        return gen_sym, constants, ast.Name(id=var_name, ctx=ast.Load())


def _mark_mutated_node(mutated_nodes, constants, node):
    ''' Mark that node holding some variable can be mutated,
    and propagate this information up the dataflow graph
    '''
    assert is_load_name(node)
    mutated_nodes.add(node)
    if node.id in constants:
        # obj can be mutated, and we can not assume we know it
        # so we have to rollback here
        del constants[node.id]
        raise Rollback('%s is mutated' % node.id)


def is_load_name(node):
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
