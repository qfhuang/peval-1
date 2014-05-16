import sys
import ast
import operator

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


def peval_call(gen_sym, bindings, function, args=[], keywords=[], starargs=None, kwargs=None):

    can_eval = True
    temp_bindings = {}

    gen_sym, function_value, tb = _peval_expression(gen_sym, function, bindings)
    if isinstance(function_value, ast.AST):
        can_eval = False
        temp_bindings.update(tb)

    args_values = []
    for arg in args:
        gen_sym, value, tb = _peval_expression(gen_sym, arg, bindings)
        args_values.append(value)
        if isinstance(value, ast.AST):
            can_eval = False
            temp_bindings.update(tb)

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
            gen_sym, container, temp_bindings = map_wrap(gen_sym, container, temp_bindings)
            mapped_containers[name] = container
        result = ast.Call(**mapped_containers)

    return gen_sym, result, temp_bindings


def is_function_evalable(function):
    return True


def wrap_in_ast(gen_sym, value):
    if isinstance(value, ast.AST):
        return gen_sym, value, {}

    obj = value.value
    if obj is True or obj is False or obj is None:
        if sys.version_info >= (3, 4):
            return gen_sym, ast.NameConstant(value=obj), {}
        else:
            return gen_sym, ast.Name(id=str(obj), ctx=ast.Load()), {}
    elif type(obj) in (str,):
        return gen_sym, ast.Str(s=obj), {}
    elif type(obj) in (int, float):
        return gen_sym, ast.Num(n=obj), {}
    else:
        gen_sym, name = gen_sym()
        return gen_sym, ast.Name(id=name), {name: obj}


def map_wrap(gen_sym, container, temp_bindings):
    temp_bindings = dict(temp_bindings)
    if container is None:
        result = None
    elif isinstance(container, (KnownValue, ast.AST)):
        gen_sym, result, tb = wrap_in_ast(gen_sym, container)
        temp_bindings.update(tb)
    elif isinstance(container, list):
        result = []
        for elem in container:
            gen_sym, elem_result, tb = wrap_in_ast(gen_sym, elem)
            result.append(elem_result)
            temp_bindings.update(tb)
    return gen_sym, result, temp_bindings


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
class _peval_expression_dispatch:

    @staticmethod
    def handle(node, gen_sym, bindings):
        return gen_sym, node, bindings

    @staticmethod
    def handle_Name(node, gen_sym, bindings):
        if node.id in bindings:
            return gen_sym, KnownValue(bindings[node.id]), {}
        else:
            return gen_sym, node, {}

    @staticmethod
    def handle_Num(node, gen_sym, bindings):
        return gen_sym, KnownValue(node.n), {}

    @staticmethod
    def handle_Add(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.add), {}

    @staticmethod
    def handle_Sub(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.sub), {}

    @staticmethod
    def handle_Mult(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.mul), {}

    @staticmethod
    def handle_Div(node, gen_sym, bindings):
        if sys.version_info > (3,):
            div = operator.truediv
        else:
            div = operator.div
        return gen_sym, KnownValue(div), {}

    @staticmethod
    def handle_Mod(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.mod), {}

    @staticmethod
    def handle_Lt(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.lt), {}

    @staticmethod
    def handle_Gt(node, gen_sym, bindings):
        return gen_sym, KnownValue(operator.gt), {}

    @staticmethod
    def handle_Call(node, gen_sym, bindings):
        return peval_call(gen_sym, bindings, node.func, args=node.args)

    @staticmethod
    def handle_BinOp(node, gen_sym, bindings):
        gen_sym, result, temp_bindings = peval_call(
            gen_sym, bindings, node.op, args=[node.left, node.right])
        if isinstance(result, ast.AST):
            del temp_bindings[result.func.id]
            result = ast.BinOp(op=node.op, left=result.args[0], right=result.args[1])
        return gen_sym, result, temp_bindings

    @staticmethod
    def handle_Compare(node, gen_sym, bindings):
        assert len(node.ops) == 1
        gen_sym, result, temp_bindings = peval_call(
            gen_sym, bindings, node.ops[0], args=[node.left, node.comparators[0]])
        if isinstance(result, ast.AST):
            del temp_bindings[result.func.id]
            result = ast.Compare(left=result.args[0], ops=node.ops, comparators=[result.args[1]])
        return gen_sym, result, temp_bindings


def _peval_expression(gen_sym, node, bindings):
    return _peval_expression_dispatch(node, gen_sym, bindings)


def peval_expression(gen_sym, node, bindings):
    gen_sym, result, temp_bindings = _peval_expression(gen_sym, node, bindings)
    if isinstance(result, ast.AST):
        eval_result = EvaluationResult(
            fully_evaluated=False,
            node=result,
            temp_bindings=temp_bindings)
    else:
        gen_sym, result_node, binding = wrap_in_ast(gen_sym, result)
        temp_bindings.update(binding)

        eval_result = EvaluationResult(
            fully_evaluated=True,
            value=result.value,
            node=result_node,
            temp_bindings=temp_bindings)

    return gen_sym, eval_result
