import sys
import ast
import operator


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

    gen_sym, function_value, tb = _peval_expression(gen_sym, bindings, function)
    if isinstance(function_value, ast.AST):
        can_eval = False
        temp_bindings.update(tb)

    args_values = []
    for arg in args:
        gen_sym, value, tb = _peval_expression(gen_sym, bindings, arg)
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
    elif isinstance(obj, int):
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


def _peval_expression(gen_sym, bindings, node):
    # Returns: gen_sym, AST/KnownValue, new_bindings
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return gen_sym, KnownValue(bindings[node.id]), {}
        else:
            return gen_sym, node, {}
    elif isinstance(node, ast.Num):
        return gen_sym, KnownValue(node.n), {}
    elif isinstance(node, ast.Add):
        return gen_sym, KnownValue(operator.add), {}
    elif isinstance(node, ast.Lt):
        return gen_sym, KnownValue(operator.lt), {}
    elif isinstance(node, ast.Gt):
        return gen_sym, KnownValue(operator.lt), {}
    elif isinstance(node, ast.BinOp):
        gen_sym, result, temp_bindings = peval_call(
            gen_sym, bindings, node.op, args=[node.left, node.right])
        if isinstance(result, ast.AST):
            del temp_bindings[result.func.id]
            result = ast.BinOp(op=node.op, left=result.args[0], right=result.args[1])
        return gen_sym, result, temp_bindings
    elif isinstance(node, ast.Compare):
        assert len(node.ops) == 1
        gen_sym, result, temp_bindings = peval_call(
            gen_sym, bindings, node.ops[0], args=[node.left, node.comparators[0]])
        if isinstance(result, ast.AST):
            del temp_bindings[result.func.id]
            result = ast.Compare(left=result.args[0], ops=node.ops, comparators=[result.args[1]])
        return gen_sym, result, temp_bindings
    else:
        return gen_sym, node, {}


def peval_expression(gen_sym, bindings, node):
    gen_sym, result, temp_bindings = _peval_expression(gen_sym, bindings, node)
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
