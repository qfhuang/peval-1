import sys
import ast
import operator

from peval.utils import ast_equal, replace_fields
from peval.core.value import KnownValue, is_known_value, kvalue_to_node, node_to_maybe_kvalue
from peval.core.immutable import immutableadict
from peval.core.dispatcher import Dispatcher


UNARY_OPS = {
    ast.UAdd: KnownValue(operator.pos),
    ast.USub: KnownValue(operator.neg),
    ast.Not: KnownValue(operator.not_),
    ast.Invert: KnownValue(operator.invert),
    }

BIN_OPS = {
    ast.Add: KnownValue(operator.add),
    ast.Sub: KnownValue(operator.sub),
    ast.Mult: KnownValue(operator.mul),
    ast.Div: KnownValue(operator.truediv),
    ast.FloorDiv: KnownValue(operator.floordiv),
    ast.Mod: KnownValue(operator.mod),
    ast.Pow: KnownValue(operator.pow),
    ast.LShift: KnownValue(operator.lshift),
    ast.RShift: KnownValue(operator.rshift),
    ast.BitOr: KnownValue(operator.or_),
    ast.BitXor: KnownValue(operator.xor),
    ast.BitAnd: KnownValue(operator.and_),
    }

def in_(x, y):
    return operator.contains(y, x)

def not_in(x, y):
    return not operator.contains(y, x)

COMPARE_OPS = {
    ast.Eq: KnownValue(operator.eq),
    ast.NotEq: KnownValue(operator.ne),
    ast.Lt: KnownValue(operator.lt),
    ast.LtE: KnownValue(operator.le),
    ast.Gt: KnownValue(operator.gt),
    ast.GtE: KnownValue(operator.ge),
    ast.Is: KnownValue(operator.is_),
    ast.IsNot: KnownValue(operator.is_not),
    ast.In: KnownValue(in_),
    ast.NotIn: KnownValue(not_in),
    }


class EvaluationResult:

    def __init__(self, fully_evaluated, node, temp_bindings, value=None):
        self.fully_evaluated = fully_evaluated
        if fully_evaluated:
            self.value = value
        self.temp_bindings = temp_bindings
        self.node = node
        self.mutated_bindings = set()


def peval_call(state, ctx, function, args=[], keywords=[], starargs=None, kwargs=None):

    can_eval = True

    function_value, state = _peval_expression(function, state, ctx)
    if not is_known_value(function_value):
        can_eval = False

    args_values = []
    for arg in args:
        value, state = _peval_expression(arg, state, ctx)
        args_values.append(value)
        if not is_known_value(value):
            can_eval = False

    keywords_values = []
    #for keyword in keywords:
    #    env, value = get_expr_value(env, keyword.value)
    #    keywords_values.append((keyword.arg, value))

    #if starargs is not None:
    #    env, starargs_value = get_expr_value(env, starargs)
    #else:
    starargs_values = None

    #if kwargs is not None:
    #    env, kwargs_value = get_expr_value(env, kwargs)
    #else:
    kwargs_values = None

    if can_eval and is_function_evalable(function_value.value):
        args = [arg.value for arg in args_values]
        keywords = [(name, keyword.value) for name, keyword in keywords_values]
        starargs = starargs_value.value if starargs_values is not None else None
        kwargs = kwargs_value.value if kwargs_values is not None else None

        try:
            value = eval_call(
                function_value.value,
                args=args, keywords=keywords, starargs=starargs, kwargs=kwargs)
        except Exception:
            pass
        else:
            return KnownValue(value), state

    # Could not evaluate the function, returning the partially evaluated node
    containers = dict(
        func=function_value,
        args=args_values,
        keywords=keywords_values,
        starargs=starargs_values,
        kwargs=kwargs_values)
    mapped_containers = {}
    for name, container in containers.items():
        container, state = map_wrap(container, state)
        mapped_containers[name] = container
    result = ast.Call(**mapped_containers)

    return result, state


def is_function_evalable(function):
    return True


def maybe_kvalue_to_node(kvalue_or_node, state):
    if is_known_value(kvalue_or_node):
        node, gen_sym, binding = kvalue_to_node(kvalue_or_node, state.gen_sym)
        state = state.update(
            gen_sym=gen_sym,
            temp_bindings=state.temp_bindings.update(binding))
        return node, state
    else:
        return kvalue_or_node, state


def map_wrap(container, state):
    if container is None:
        result = None
    elif isinstance(container, (KnownValue, ast.AST)):
        result, state = maybe_kvalue_to_node(container, state)
    elif isinstance(container, list):
        result = []
        for elem in container:
            elem_result, state = maybe_kvalue_to_node(elem, state)
            result.append(elem_result)
    return result, state


def eval_call(function, args=[], keywords=[], starargs=None, kwargs=None):

    starargs = starargs if starargs is not None else []
    kwargs = kwargs if kwargs is not None else {}

    args = args + list(starargs)
    kwds = dict(keywords)
    intersection = set(kwds).intersection(set(kwargs))
    if len(intersection) > 0:
        raise Exception("Multiple values for keyword arguments " + repr(list(intersection)))
    kwds.update(kwargs)

    return function(*args, **kwds)


def peval_boolop(state, ctx, op, values):
    assert type(op) in (ast.And, ast.Or)

    new_values = []
    for value in values:
        new_value, state = _peval_expression(value, state, ctx)

        # Short circuit
        if is_known_value(new_value):
            if ((type(op) == ast.And and not new_value.value)
                    or (type(op) == ast.Or and new_value.value)):
                return new_value, state
        else:
            new_values.append(new_value)

    if len(new_values) == 0:
        return KnownValue(type(op) == ast.And), state
    elif len(new_values) == 1:
        return new_values[0], state
    else:
        return ast.BoolOp(op=op, values=new_values), state


def peval_binop(state, ctx, op, left, right):

    if ctx.py2_division and type(op) == ast.Div:
        func = KnownValue(operator.div)
    else:
        func = BIN_OPS[type(op)]

    result, state = peval_call(state, ctx, func, args=[left, right])
    if not is_known_value(result):
        state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
        result = ast.BinOp(op=op, left=result.args[0], right=result.args[1])
    return result, state


def peval_single_compare(state, ctx, op, left, right):

    func = COMPARE_OPS[type(op)]

    result, state = peval_call(state, ctx, func, args=[left, right])
    if not is_known_value(result):
        state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
        result = ast.Compare(left=result.args[0], ops=[op], comparators=[result.args[1]])
    return result, state


def peval_compare(state, ctx, node):

    if len(node.ops) == 1:
        return peval_single_compare(state, ctx, node.ops[0], node.left, node.comparators[0])

    values = []
    for value_node in [node.left] + node.comparators:
        value, state = _peval_expression(value_node, state, ctx)
        values.append(value)

    pair_values = []
    lefts = [node.left] + node.comparators[:-1]
    rights = node.comparators
    for left, op, right in zip(lefts, node.ops, rights):
        pair_value, state = peval_single_compare(state, ctx, op, left, right)
        pair_values.append(pair_value)

    result, state = peval_boolop(state, ctx, ast.And(), pair_values)

    if is_known_value(result):
        return result, state

    if type(result) != ast.BoolOp:
        return result, state

    # Glueing non-evaluated comparisons back together.
    nodes = [result.values[0]]
    for value in result.values[1:]:
        last_node = nodes[-1]
        if (type(last_node) == ast.Compare
                and type(value) == ast.Compare
                and ast_equal(last_node.comparators[-1], value.left)):
            nodes[-1] = ast.Compare(
                left=last_node.left,
                ops=last_node.ops + value.ops,
                comparators=last_node.comparators + value.comparators)
        else:
            nodes.append(value)

    if len(nodes) == 1:
        return nodes[0], state
    else:
        return ast.BoolOp(op=ast.And(), values=nodes), state


def _peval_expression(kvalue_or_node, state, ctx):
    if is_known_value(kvalue_or_node):
        return kvalue_or_node, state

    kvalue_or_node = node_to_maybe_kvalue(kvalue_or_node, ctx.bindings)
    if is_known_value(kvalue_or_node):
        return kvalue_or_node, state

    return _peval_expression_node(kvalue_or_node, state, ctx)


@Dispatcher
class _peval_expression_node:

    @staticmethod
    def handle(node, state, ctx):
        return node, state

    #@staticmethod
    #def handle_Name(node, state, ctx):
    #    raise NotImplementedError

    #@staticmethod
    #def handle_Num(node, state, ctx):
    #    raise NotImplementedError

    #@staticmethod
    #def handle_Str(node, state, ctx):
    #    raise NotImplementedError

    @staticmethod
    def handle_BoolOp(node, state, ctx):
        return peval_boolop(state, ctx, node.op, node.values)

    @staticmethod
    def handle_BinOp(node, state, ctx):
        return peval_binop(state, ctx, node.op, node.left, node.right)

    @staticmethod
    def handle_UnaryOp(node, state, ctx):
        result, state = peval_call(
            state, ctx, UNARY_OPS[type(node.op)], args=[node.operand])
        if not is_known_value(result):
            state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
            result = ast.UnaryOp(op=node.op, operand=result.args[0])
        return result, state

    @staticmethod
    def handle_Lambda(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_IfExp(node, state, ctx):
        test_value, state = _peval_expression(node.test, state, ctx)
        if is_known_value(test_value):
            taken_node = node.body if test_value.value else node.orelse
            return _peval_expression(taken_node, state, ctx)
        else:
            new_body, state = _peval_expression(node.body, state, ctx)
            new_orelse, state = _peval_expression(node.orelse, state, ctx)

            new_body_node, state = maybe_kvalue_to_node(new_body, state)
            new_orelse_node, state = maybe_kvalue_to_node(new_orelse, state)
            return replace_fields(
                node, test=test_value, body=new_body_node, orelse=new_orelse_node), state

    @staticmethod
    def handle_Dict(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_Set(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_ListComp(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_SetComp(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_DictComp(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_GeneratorExp(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_Yield(node, state, ctx):
        raise NotImplementedError

    @staticmethod
    def handle_Compare(node, state, ctx):
        return peval_compare(state, ctx, node)

    @staticmethod
    def handle_Call(node, state, ctx):
        return peval_call(state, ctx, node.func, args=node.args)

    @staticmethod
    def handle_Repr(node, state, ctx):
        raise NotImplementedError

    #@staticmethod
    #def handle_Attribute(node, state, ctx):
    #    raise NotImplementedError

    @staticmethod
    def handle_Subscript(node, state, ctx):
        raise NotImplementedError

    #@staticmethod
    #def handle_List(node, state, ctx):
    #    raise NotImplementedError

    @staticmethod
    def handle_Tuple(node, state, ctx):
        elts = []
        for elt in node.elts:
            elt_value, state = _peval_expression(elt, state, ctx)
            elts.append(elt_value)

        if all(is_known_value(elt) for elt in elts):
            return KnownValue(tuple(elts)), state
        else:
            elts, state = map_wrap(elts, state)
            return ast.Tuple(elts=elts, ctx=ast.Load()), state


def peval_expression(node, gen_sym, bindings, py2_division=False):

    # We do not really need the Py2-style division in Py3,
    # since it never occurs in actual code.
    if py2_division and sys.version_info >= (3,):
        raise ValueError("`py2_division` is not supported on Python 3.x")

    ctx = immutableadict(bindings=bindings, py2_division=py2_division)
    state = immutableadict(gen_sym=gen_sym, temp_bindings=immutableadict())

    result, state = _peval_expression(node, state, ctx)
    if is_known_value(result):
        result_node, state = maybe_kvalue_to_node(result, state)
        eval_result = EvaluationResult(
            fully_evaluated=True,
            value=result.value,
            node=result_node,
            temp_bindings=state.temp_bindings)
    else:
        eval_result = EvaluationResult(
            fully_evaluated=False,
            node=result,
            temp_bindings=state.temp_bindings)

    return eval_result, state.gen_sym
