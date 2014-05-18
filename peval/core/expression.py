import sys
import ast
import operator

from peval.utils import ast_equal
from peval.core.immutable import immutableadict
from peval.core.dispatcher import Dispatcher


class KnownValue:

    def __init__(self, value, preferred_name=None):
        self.value = value
        self.preferred_name = preferred_name

    def __str__(self):
        return (
            "<" + str(self.value)
            + (" (" + self.preferred_name + ")" if self.preferred_name is not None else "")
            + ">")

    def __repr__(self):
        return "KnownValue({value}, preferred_name={name})".format(
            value=repr(self.value), preferred_name=self.preferred_name)


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
    if isinstance(function_value, ast.AST):
        can_eval = False

    args_values = []
    for arg in args:
        value, state = _peval_expression(arg, state, ctx)
        args_values.append(value)
        if isinstance(value, ast.AST):
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


def wrap_in_ast(value, state):
    if isinstance(value, ast.AST):
        return value, state

    obj = value.value

    if obj is True or obj is False or obj is None:
        if sys.version_info >= (3, 4):
            return ast.NameConstant(value=obj), state
        else:
            return ast.Name(id=str(obj), ctx=ast.Load()), state
    elif type(obj) in (str,):
        return ast.Str(s=obj), state
    elif type(obj) in (int, float):
        return ast.Num(n=obj), state
    elif value.preferred_name is not None:
        return ast.Name(id=value.preferred_name, ctx=ast.Load()), state
    else:
        name, gen_sym = state.gen_sym()
        new_state = state.update(
            gen_sym=gen_sym,
            temp_bindings=state.temp_bindings.set(name, obj))
        return ast.Name(id=name, ctx=ast.Load()), new_state


def map_wrap(container, state):
    if container is None:
        result = None
    elif isinstance(container, (KnownValue, ast.AST)):
        result, state = wrap_in_ast(container, state)
    elif isinstance(container, list):
        result = []
        for elem in container:
            elem_result, state = wrap_in_ast(elem, state)
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
        is_known = isinstance(new_value, KnownValue)

        # Short circuit
        # FIXME: implicit call of bool() on a value --- can be mutating
        if is_known:
            if ((isinstance(op, ast.And) and not new_value.value)
                    or (isinstance(op, ast.Or) and new_value.value)):
                return new_value, state
        else:
            new_values.append(new_value)

    if len(new_values) == 0:
        return KnownValue(isinstance(op, ast.And)), state
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
    if isinstance(result, ast.AST):
        state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
        result = ast.BinOp(op=op, left=result.args[0], right=result.args[1])
    return result, state


def peval_single_compare(state, ctx, op, left, right):

    func = COMPARE_OPS[type(op)]

    result, state = peval_call(state, ctx, func, args=[left, right])
    if isinstance(result, ast.AST):
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

    if isinstance(result, KnownValue):
        return result, state

    if not isinstance(result, ast.BoolOp):
        return result, state

    # Gluing non-evaluated comparisons back together.
    nodes = [result.values[0]]
    for value in result.values[1:]:
        last_node = nodes[-1]
        if (isinstance(last_node, ast.Compare)
                and isinstance(value, ast.Compare)
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


def _peval_expression(node_or_value, state, ctx):
    if isinstance(node_or_value, KnownValue):
        return node_or_value, state
    else:
        return _peval_expression_node(node_or_value, state, ctx)


@Dispatcher
class _peval_expression_node:

    @staticmethod
    def handle(node, state, ctx):
        return node, state

    @staticmethod
    def handle_Name(node, state, ctx):
        if node.id in ctx.bindings:
            return KnownValue(ctx.bindings[node.id], preferred_name=node.id), state
        else:
            return node, state

    @staticmethod
    def handle_Num(node, state, ctx):
        return KnownValue(node.n), state

    @staticmethod
    def handle_Call(node, state, ctx):
        return peval_call(state, ctx, node.func, args=node.args)

    @staticmethod
    def handle_BinOp(node, state, ctx):
        return peval_binop(state, ctx, node.op, node.left, node.right)

    @staticmethod
    def handle_BoolOp(node, state, ctx):
        return peval_boolop(state, ctx, node.op, node.values)

    @staticmethod
    def handle_UnaryOp(node, state, ctx):
        result, state = peval_call(
            state, ctx, UNARY_OPS[type(node.op)], args=[node.operand])
        if isinstance(result, ast.AST):
            state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
            result = ast.UnaryOp(op=node.op, operand=result.args[0])
        return result, state

    @staticmethod
    def handle_Compare(node, state, ctx):
        return peval_compare(state, ctx, node)


def peval_expression(node, gen_sym, bindings, py2_division=False):

    ctx = immutableadict(bindings=bindings, py2_division=py2_division)
    state = immutableadict(gen_sym=gen_sym, temp_bindings=immutableadict())

    result, state = _peval_expression(node, state, ctx)
    if isinstance(result, ast.AST):
        eval_result = EvaluationResult(
            fully_evaluated=False,
            node=result,
            temp_bindings=state.temp_bindings)
    else:
        result_node, state = wrap_in_ast(result, state)
        eval_result = EvaluationResult(
            fully_evaluated=True,
            value=result.value,
            node=result_node,
            temp_bindings=state.temp_bindings)

    return eval_result, state.gen_sym
