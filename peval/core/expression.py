import sys
import ast
import operator

from peval.core.immutable import immutableadict
from peval.core.dispatcher import Dispatcher


class KnownValue:

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "<" + str(self.value) + ">"

    def __repr__(self):
        return "KnownValue({value})".format(value=repr(self.value))


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
        result = KnownValue(eval_call(
            function_value.value,
            args=[arg.value for arg in args_values],
            keywords=[(name, keyword.value) for name, keyword in keywords_values],
            starargs=starargs_value.value if starargs_values is not None else None,
            kwargs=kwargs_value.value if kwargs_values is not None else None))
    else:
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
    else:
        gen_sym, name = state.gen_sym()
        new_state = state.update(
            gen_sym=gen_sym,
            temp_bindings=state.temp_bindings.set(name, obj))
        return ast.Name(id=name), new_state


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

    # FIXME: may catch exceptions and return a more meaningful error here
    return function(*args, **kwds)


@Dispatcher
class _peval_expression:

    @staticmethod
    def handle(node, state, ctx):
        return node, state

    @staticmethod
    def handle_Name(node, state, ctx):
        if node.id in ctx.bindings:
            return KnownValue(ctx.bindings[node.id]), state
        else:
            return node, state

    @staticmethod
    def handle_Num(node, state, ctx):
        return KnownValue(node.n), state

    @staticmethod
    def handle_Add(node, state, ctx):
        return KnownValue(operator.add), state

    @staticmethod
    def handle_Sub(node, state, ctx):
        return KnownValue(operator.sub), state

    @staticmethod
    def handle_Mult(node, state, ctx):
        return KnownValue(operator.mul), state

    @staticmethod
    def handle_Div(node, state, ctx):
        if ctx.py2_division:
            div = operator.div
        else:
            div = operator.truediv
        return KnownValue(div), state

    @staticmethod
    def handle_Mod(node, state, ctx):
        return KnownValue(operator.mod), state

    @staticmethod
    def handle_Lt(node, state, ctx):
        return KnownValue(operator.lt), state

    @staticmethod
    def handle_Gt(node, state, ctx):
        return KnownValue(operator.gt), state

    @staticmethod
    def handle_Call(node, state, ctx):
        return peval_call(state, ctx, node.func, args=node.args)

    @staticmethod
    def handle_BinOp(node, state, ctx):
        result, state = peval_call(
            state, ctx, node.op, args=[node.left, node.right])
        if isinstance(result, ast.AST):
            state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
            result = ast.BinOp(op=node.op, left=result.args[0], right=result.args[1])
        return result, state

    @staticmethod
    def handle_Compare(node, state, ctx):
        assert len(node.ops) == 1
        result, state = peval_call(
            state, ctx, node.ops[0], args=[node.left, node.comparators[0]])
        if isinstance(result, ast.AST):
            state = state.update(temp_bindings=state.temp_bindings.del_(result.func.id))
            result = ast.Compare(left=result.args[0], ops=node.ops, comparators=[result.args[1]])
        return result, state


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
