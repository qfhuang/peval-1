from __future__ import division

import ast
import operator

import six
import sys

from peval.gensym import GenSym
from peval.function import Function
from peval.utils import get_fn_arg_id, get_literal_node, get_node_value_if_known
from peval.visitor import Visitor


def evaluate(ast_tree, constants):
    ''' Try running Optimizer until it finishes without rollback.
    Return optimized AST and a list of bindings that the AST needs.
    '''
    gen_sym = GenSym(ast_tree)
    optimizer = Optimizer(constants, gen_sym)
    while True:
        try:
            new_ast = optimizer.visit(ast_tree)
        except Optimizer.Rollback:
            # we gathered more knowledge and want to try again
            continue
        else:
            all_bindings = dict(constants)
            all_bindings.update(optimizer.get_bindings())
            return new_ast, all_bindings


class Optimizer(Visitor):
    ''' Simplify AST, given information about what variables are known
    '''
    class Rollback(Exception):
        pass

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

    def __init__(self, constants, gen_sym):
        '''
        :constants: a dict names-> values of variables known at compile time
        '''
        super(Optimizer, self).__init__()
        self._gen_sym = gen_sym
        self._constants = dict(constants)
        self._mutated_nodes = set()

    def get_bindings(self):
        ''' Return a dict, populated with newly bound variables
        (results of calculations done at compile time), and survived
        initial constants.
        '''
        return self._constants

    def visit_Module(self, node):
        # True if old behavior of division operator is active
        # (truediv for floats, floordiv for integers).
        self._py2_div = (six.PY2 and self._constants.get('division') is not division)
        self.generic_visit(node)
        return node

    def visit_ImportFrom(self, node):
        # Detecting 'from __future__ import division'
        if node.module == '__future__' and any(alias.name == 'division' for alias in node.names):
            self._py2_div = False
        return node

    def visit_Name(self, node):
        ''' Replacing known variables with literal values
        '''
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load) and node.id in self._constants:
            literal_node = get_literal_node(self._constants[node.id])
            if literal_node is not None:
                return literal_node
        return node

    def visit_If(self, node):
        ''' Leave only one branch, if possible
        '''
        node.test = self.visit(node.test)
        is_known, test_value = get_node_value_if_known(node.test, self._constants)
        if is_known:
            pass_ = ast.Pass()
            taken_node = node.body if test_value else node.orelse
            if taken_node:
                return self._visit(taken_node) or pass_
            else:
                return pass_
        else:
            node.body = self._visit(node.body)
            node.orelse = self._visit(node.orelse)
        return node

    def visit_Call(self, node):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        '''
        self.generic_visit(node)
        is_known, fn = get_node_value_if_known(node.func, self._constants)
        if is_known:
            if self._is_pure_fn(fn):
                return self._fn_result_node_if_safe(fn, node)
            else:
                return node
        else:
            assert not node.kwargs and not node.starargs
            # check for mutations from function call:
            # if we don't know it's pure, it can mutate the arguments
            for arg_node in node.args:
                if is_load_name(arg_node):
                    self._mark_mutated_node(arg_node)
                else:
                    # The function argument is an expression.
                    # Technically, this expression can return one of its arguments
                    # and then the function will mutate it.
                    pass
            # if this a method call, it can also mutate "self"
            if isinstance(node.func, ast.Attribute):
                obj_node = node.func.value
                if is_load_name(obj_node):
                    self._mark_mutated_node(obj_node)
                else:
                    # Well, it is hard, because it can be something like
                    # Fooo(x).transform() that also mutates x.
                    # Above this case will be handled by argument mutation
                    # and dataflow analysis, but maybe there are other cases?
                    pass
        return node

    def visit_UnaryOp(self, node):
        ''' Hanle "not" - evaluate if possible
        '''
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            is_known, value = get_node_value_if_known(node.operand, self._constants)
            if is_known:
                return self._new_binding_node(not value)
        return node

    def visit_BoolOp(self, node):
        ''' and, or - handle short-circuting
        '''
        assert type(node.op) in (ast.And, ast.Or)
        new_value_nodes = []
        for value_node in node.values:
            value_node = self.visit(value_node)
            is_known, value = get_node_value_if_known(value_node, self._constants)
            if is_known:
                if isinstance(node.op, ast.And):
                    if not value:
                        return self._new_binding_node(False)
                elif isinstance(node.op, ast.Or):
                    if value:
                        return self._new_binding_node(value)
            else:
                new_value_nodes.append(value_node)
        if not new_value_nodes:
            return self._new_binding_node(isinstance(node.op, ast.And))
        elif len(new_value_nodes) == 1:
            return new_value_nodes[0]
        else:
            node.values = new_value_nodes
            return node

    def visit_Compare(self, node):
        ''' ==, >, etc. - evaluate only if all are know
        '''
        self.generic_visit(node)
        is_known, value = get_node_value_if_known(node.left, self._constants)
        if not is_known:
            return node
        value_list = [value]
        for value_node in node.comparators:
            is_known, value = get_node_value_if_known(value_node, self._constants)
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
                return self._new_binding_node(False)
        return self._new_binding_node(True)

    def visit_BinOp(self, node):
        ''' Binary arithmetic - + * / etc.
        Evaluate if everything is known.
        '''
        self.generic_visit(node)
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
        if self._py2_div:
            operations[ast.Div] = operator.div
        else:
            operations[ast.Div] = operator.truediv

        can_apply = lambda is_known, value: is_known and \
                type(value) in self.NUMBER_TYPES
        if type(node.op) in operations:
            is_known, l_value = get_node_value_if_known(node.left, self._constants)
            if can_apply(is_known, l_value):
                is_known, r_value = get_node_value_if_known(node.right, self._constants)
                if can_apply(is_known, r_value):
                    value = operations[type(node.op)](l_value, r_value)
                    return self._new_binding_node(value)
        return node

    def _fn_result_node_if_safe(self, fn, node):
        ''' Check that we know all fn args.
        Than call it and return a node representing the value.
        It we can not call fn, just return node.
        Assume that fn is pure.
        '''
        assert isinstance(node, ast.Call) and self._is_pure_fn(fn)
        args = []
        for arg_node in node.args:
            is_known, value = get_node_value_if_known(arg_node, self._constants)
            if is_known:
                args.append(value)
            else:
                return node

        assert not node.kwargs and not node.keywords and not node.starargs
        try:
            fn_value = fn(*args)
        except:
            # do not optimize the call away to leave original exception
            return node
        else:
            return self._new_binding_node(fn_value)

    def _is_pure_fn(self, fn):
        ''' fn has no side effects, and its value is determined only by
        its inputs
        '''
        if fn in self.PURE_FUNCTIONS:
            return True
        else:
            return getattr(fn, '_peval_is_pure', False)

    def _new_binding_node(self, value):
        ''' Generate unique variable name, add it to constants with given value,
        and return the node that loads generated variable.
        '''
        literal_node = get_literal_node(value)
        if literal_node is not None:
            return literal_node
        else:
            var_name = self._gen_sym('binding')
            self._constants[var_name] = value
            return ast.Name(id=var_name, ctx=ast.Load())

    def _mark_mutated_node(self, node):
        ''' Mark that node holding some variable can be mutated,
        and propagate this information up the dataflow graph
        '''
        assert is_load_name(node)
        self._mutated_nodes.add(node)
        if node.id in self._constants:
            # obj can be mutated, and we can not assume we know it
            # so we have to rollback here
            del self._constants[node.id]
            raise self.Rollback('%s is mutated' % node.id)


def is_load_name(node):
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
