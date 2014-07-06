import sys
import ast
import operator

import funcsigs

from peval.utils import ast_equal, replace_fields
from peval.core.gensym import GenSym
from peval.core.value import KnownValue, is_known_value, kvalue_to_node
from peval.core.immutable import immutableadict
from peval.core.dispatcher import Dispatcher
from peval.wisdom import get_mutation_info, get_signature


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

# Wrapping ``contains``, because its parameters
# do not follow the pattern (left operand, right operand).

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


# Some functions that map other functions over different containers,
# passing through the given state object.
# Since it is not Haskell, for performance reasons
# we have a separate specialization for each function.


# For ``kvalue_to_node()`` we do not need to pass through the whole state, only ``gen_sym``.
# So we have this internal function that does that.
def _fmap_kvalue_to_node(container, gen_sym):
    if container is None:
        return None, gen_sym, {}
    elif type(container) in (list, tuple, zip):
        new_container = []
        result_bindings = {}
        for elem in container:
            new_elem, gen_sym, temp_bindings = _fmap_kvalue_to_node(elem, gen_sym)
            new_container.append(new_elem)
            result_bindings.update(temp_bindings)
        container_type = type(container)
        result_type = list if container_type == zip else container_type
        return result_type(new_container), gen_sym, result_bindings
    elif type(container) == dict:
        new_container = dict(container)
        result_bindings = {}
        for key in new_container:
            new_container[key], gen_sym, temp_bindings = (
                _fmap_kvalue_to_node(new_container[key], gen_sym))
            result_bindings.update(temp_bindings)
        return new_container, gen_sym, result_bindings
    elif is_known_value(container):
        return kvalue_to_node(container, gen_sym)
    else:
        # Should be an AST node
        return container, gen_sym, {}


def fmap_kvalue_to_node(container, state):
    new_container, gen_sym, temp_bindings = _fmap_kvalue_to_node(container, state.gen_sym)
    new_state = state.update(
        gen_sym=gen_sym,
        temp_bindings=state.temp_bindings.update(temp_bindings))
    return new_container, new_state


def fmap_peval_expression(container, state, ctx):
    if container is None:
        return None, state
    elif type(container) in (list, tuple, zip):
        new_container = []
        for elem in container:
            new_elem, state = fmap_peval_expression(elem, state, ctx)
            new_container.append(new_elem)
        container_type = type(container)
        result_type = list if container_type == zip else container_type
        return result_type(new_container), state
    elif type(container) == dict:
        new_container = dict(container)
        for key in new_container:
            new_container[key], state = fmap_peval_expression(new_container[key], state, ctx)
        return new_container, state
    elif is_known_value(container):
        return container, state
    else:
        # Should be an AST node
        return _peval_expression(container, state, ctx)


def fmap_is_known_value(container):
    if type(container) in (list, tuple, zip):
        return all(map(fmap_is_known_value, container))
    elif type(container) == dict:
        return all(map(fmap_is_known_value, container.values()))
    else:
        return is_known_value(container)


def fmap_is_known_value_or_none(container):
    if type(container) in (list, tuple, zip):
        return all(map(fmap_is_known_value_or_none, container))
    elif type(container) == dict:
        return all(map(fmap_is_known_value_or_none, container.values()))
    else:
        return container is None or is_known_value(container)


def fmap_get_value_or_none(container):
    container_type = type(container)
    if container_type in (list, tuple, zip):
        result_type = list if container_type == zip else container_type
        return result_type(map(fmap_get_value_or_none, container))
    elif type(container) == dict:
        return dict((key, fmap_get_value_or_none(value)) for key, value in container.items())
    elif container is None:
        return None
    else:
        return container.value


def try_call(obj, args=(), kwds={}):
    # The only entry point for function calls.
    print("Evaluating", obj, args, kwds)
    try:
        sig = get_signature(obj)
    except ValueError:
        print("Failed to get signature")
        return False, None

    try:
        ba = sig.bind(*args, **kwds)
    except TypeError:
        # binding failed
        print("Failed to bind")
        return False, None

    argtypes = dict((argname, type(value)) for argname, value in ba.arguments.items())
    pure, mutating = get_mutation_info(obj, argtypes)
    if not pure or len(mutating) > 0:
        print("Mutating")
        return False, None

    try:
        value = obj(*args, **kwds)
    except Exception:
        print("Failed to call")
        return False, None

    print("Result:", value)
    return True, value


def try_get_attribute(obj, name):
    return try_call(getattr, args=(obj, name))


def try_call_method(obj, name, args=(), kwds={}):
    success, attr = try_get_attribute(obj, name)
    if not success:
        return False, None
    return try_call(attr, args=args, kwds=kwds)


def peval_call(state, ctx, func, args=[], keywords=[], starargs=None, kwargs=None):

    # ``keywords`` is a list of ``ast.keyword`` objects
    keywords_order = [keyword.arg for keyword in keywords]
    keywords = dict((keyword.arg, keyword) for keyword in keywords)

    results, state = fmap_peval_expression(
        dict(func=func, args=args, keywords=keywords, starargs=starargs, kwargs=kwargs),
        state, ctx)

    if fmap_is_known_value_or_none(results):
        values = fmap_get_value_or_none(results)
        success, value = try_eval_call(
            values['func'], args=values['args'], keywords=values['keywords'],
            starargs=values['starargs'], kwargs=values['kwargs'])
        if success:
            return KnownValue(value=value), state

    nodes, state = fmap_kvalue_to_node(results, state)

    # restore the keyword list
    keywords = nodes['keywords']
    nodes['keywords'] = [ast.keyword(arg=key, value=keywords[key]) for key in keywords_order]

    return ast.Call(**nodes), state


def try_eval_call(function, args=[], keywords=[], starargs=None, kwargs=None):

    starargs = starargs if starargs is not None else []
    kwargs = kwargs if kwargs is not None else {}

    args = args + list(starargs)
    kwds = dict(keywords)
    intersection = set(kwds).intersection(set(kwargs))
    if len(intersection) > 0:
        # Multiple values for some of the keyword arguments, will raise an exception on call.
        return False, None

    kwds.update(kwargs)
    return try_call(function, args=args, kwds=kwds)


def peval_boolop(state, ctx, op, values):
    assert type(op) in (ast.And, ast.Or)

    new_values = []
    for value in values:
        new_value, state = _peval_expression(value, state, ctx)

        # Short circuit
        if is_known_value(new_value):
            success, bool_value = try_call(bool, args=(new_value.value,))
            if success and ((type(op) == ast.And and not bool_value)
                    or (type(op) == ast.Or and bool_value)):
                return new_value, state
            # Just skip it, it won't change the BoolOp result.
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


class CannotEvaluateComprehension(Exception):
    pass


class ListAccumulator:

    def __init__(self):
        self.accum = []

    def add_elem(self, elem):
        self.accum.append(elem)

    def add_part(self, part):
        self.accum.extend(part)

    def get_accum(self):
        return self.accum


class SetAccumulator:

    def __init__(self):
        self.accum = set()

    def add_elem(self, elem):
        self.accum.add(elem)

    def add_part(self, part):
        self.accum.update(part)

    def get_accum(self):
        return self.accum


class DictAccumulator:

    def __init__(self):
        self.accum = {}

    def add_elem(self, elem):
        self.accum[elem[0]] = elem[1]

    def add_part(self, part):
        self.accum.update(part)

    def get_accum(self):
        return self.accum


class GeneratorExpAccumulator:
    """
    This is just a list that presents itself as a generator expression
    (to preserve the type after partial evaluation).
    Since we are evaluating each of its elements before returning it anyway,
    it does not really matter.
    """

    def __init__(self):
        self.accum = []

    def add_elem(self, elem):
        self.accum.append(elem)

    def add_part(self, part):
        self.accum.extend(list(part))

    def get_accum(self):
        return (x for x in self.accum)


def peval_comprehension(node, state, ctx):

    accum_cls = {
        ast.ListComp: ListAccumulator,
        ast.GeneratorExp: GeneratorExpAccumulator,
    }

    if sys.version_info >= (2, 7):
        accum_cls.update({
            ast.SetComp: SetAccumulator,
            ast.DictComp: DictAccumulator,
        })

    # variables from generators temporary mask bindings
    target_names = set()
    for generator in node.generators:
        if type(generator.target) == ast.Name:
            target_names.add(generator.target.id)
        else:
            target_names.update([elt.id for elt in generator.target.elts])

    # pre-evaluate the expression
    elt_bindings = dict(ctx.bindings)
    for name in target_names:
        if name in elt_bindings:
            del elt_bindings[name]
    elt_ctx = ctx.update(bindings=elt_bindings)

    if sys.version_info >= (2, 7) and type(node) == ast.DictComp:
        elt = ast.Tuple(elts=[node.key, node.value])
    else:
        elt = node.elt
    new_elt, state = _peval_expression(elt, state, elt_ctx)

    try:
        container, state = _peval_comprehension(
            accum_cls[type(node)], new_elt, node.generators, state, ctx)
        evaluated = True
    except CannotEvaluateComprehension:
        evaluated = False

    if evaluated:
        return KnownValue(value=container), state
    else:
        new_elt, state = fmap_kvalue_to_node(new_elt, state)
        new_generators, state = _peval_comprehension_generators(node.generators, state, ctx)
        if sys.version_info >= (2, 7) and type(node) == ast.DictComp:
            key, value = new_elt.elts
            return replace_fields(node, key=key, value=value, generators=new_generators), state
        else:
            return replace_fields(node, elt=new_elt, generators=new_generators), state


def _peval_comprehension_ifs(ifs, state, ctx):
    if len(ifs) > 0:
        joint_ifs = ast.BoolOp(op=ast.And(), values=ifs)
        joint_ifs_result, state = _peval_expression(joint_ifs, state, ctx)
        if is_known_value(joint_ifs_result):
            return joint_ifs_result, state
        else:
            return joint_ifs_result.values, state
    else:
        return KnownValue(value=True), state


def _get_masked_bindings(target, bindings):
    if type(target) == ast.Name:
        target_names = [target.id]
    else:
        target_names = [elt.id for elt in target.elts]

    new_bindings = dict(bindings)
    for name in target_names:
        if name in new_bindings:
            del new_bindings[name]

    return new_bindings


def _peval_comprehension_generators(generators, state, ctx):
    if len(generators) == 0:
        return [], state

    generator = generators[0]
    next_generators = generators[1:]

    iter_result, state = _peval_expression(generator.iter, state, ctx)

    masked_bindings = _get_masked_bindings(generator.target, ctx.bindings)
    masked_ctx = ctx.set('bindings', masked_bindings)

    ifs_result, state = _peval_comprehension_ifs(generator.ifs, state, masked_ctx)

    if is_known_value(ifs_result):
        success, bool_value = try_call(bool, args=(ifs_result.value,))
        if success and bool_value:
            ifs_result = []

    new_generator_kwds, state = fmap_kvalue_to_node(
        dict(target=generator.target, iter=iter_result, ifs=ifs_result), state)
    new_generator = ast.comprehension(**new_generator_kwds)

    new_generators, state = _peval_comprehension_generators(next_generators, state, ctx)

    return [new_generator] + new_generators, state


def _try_unpack_sequence(seq, node):
    # node is either a Name, a Tuple of Names, or a List of Names
    if type(node) == ast.Name:
        return True, {node.id: seq}
    elif type(node) in (ast.Tuple, ast.List):
        if not all(map(lambda elt: type(elt) == ast.Name, node.elts)):
            return False, None
        bindings = {}
        success, it = try_call(iter, args=(seq,))
        if not success:
            return False, None

        if it is seq:
            return False, None

        for elt in node.elts:
            try:
                elem = next(it)
            except StopIteration:
                return False, None
            bindings[elt.id] = elem

        try:
            elem = next(it)
        except StopIteration:
            return True, bindings

        return False, None

    else:
        return False, None


def _peval_comprehension(accum_cls, elt, generators, state, ctx):

    generator = generators[0]
    next_generators = generators[1:]

    iter_result, state = _peval_expression(generator.iter, state, ctx)

    masked_bindings = _get_masked_bindings(generator.target, ctx.bindings)
    masked_ctx = ctx.set('bindings', masked_bindings)

    ifs_result, state = _peval_comprehension_ifs(generator.ifs, state, masked_ctx)

    if is_known_value(iter_result):
        iterable = iter_result.value
        iterator_evaluated, iterator = try_call(iter, args=(iterable,))
    else:
        iterator_evaluated = False

    if not iterator_evaluated or iterator is iterable:
        raise CannotEvaluateComprehension

    accum = accum_cls()

    for targets in iterable:

        unpacked, target_bindings = _try_unpack_sequence(targets, generator.target)
        if not unpacked:
            raise CannotEvaluateComprehension

        iter_bindings = dict(ctx.bindings)
        iter_bindings.update(target_bindings)
        iter_ctx = ctx.set('bindings', iter_bindings)

        ifs_value, state = _peval_expression(ifs_result, state, iter_ctx)
        if not is_known_value(ifs_value):
            raise CannotEvaluateComprehension

        success, bool_value = try_call(bool, args=(ifs_value.value,))
        if not success:
            raise CannotEvaluateComprehension
        if success and not bool_value:
            continue

        if len(next_generators) == 0:
            elt_result, state = _peval_expression(elt, state, iter_ctx)
            if not is_known_value(elt_result):
                raise CannotEvaluateComprehension
            accum.add_elem(elt_result.value)
        else:
            part, state = _peval_comprehension(accum_cls, elt, next_generators, state, iter_ctx)
            accum.add_part(part)

    return accum.get_accum(), state


@Dispatcher
class _peval_expression:

    @staticmethod
    def handle(node, state, ctx):
        # Pass through in case of type(node) == KnownValue
        return node, state

    @staticmethod
    def handle_Name(node, state, ctx):
        name = node.id
        if name in ctx.bindings:
            return KnownValue(ctx.bindings[name], preferred_name=name), state
        else:
            return node, state

    @staticmethod
    def handle_Num(node, state, ctx):
        return KnownValue(node.n), state

    @staticmethod
    def handle_Str(node, state, ctx):
        return KnownValue(node.s), state

    @staticmethod
    def handle_Bytes(node, state, ctx):
        # For Python >= 3
        return KnownValue(node.s), state

    @staticmethod
    def handle_NameConstant(node, state, ctx):
        # For Python >= 3.4
        return KnownValue(node.value), state

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
            success, bool_value = try_call(bool, args=(test_value.value,))
            if success:
                taken_node = node.body if bool_value else node.orelse
                return _peval_expression(taken_node, state, ctx)

        new_body, state = _peval_expression(node.body, state, ctx)
        new_orelse, state = _peval_expression(node.orelse, state, ctx)

        new_body_node, state = fmap_kvalue_to_node(new_body, state)
        new_orelse_node, state = fmap_kvalue_to_node(new_orelse, state)
        return replace_fields(
            node, test=test_value, body=new_body_node, orelse=new_orelse_node), state

    @staticmethod
    def handle_Dict(node, state, ctx):

        pairs, state = fmap_peval_expression(zip(node.keys, node.values), state, ctx)
        can_eval = fmap_is_known_value(pairs)

        if can_eval:
            new_dict = dict((key.value, value.value) for key, value in pairs)
            return KnownValue(value=new_dict), state
        else:
            keys_values, state = fmap_kvalue_to_node(zip(*pairs), state)
            new_node = replace_fields(node, keys=list(keys_values[0]), values=list(keys_values[1]))
            return new_node, state

    @staticmethod
    def handle_List(node, state, ctx):

        elts, state = fmap_peval_expression(node.elts, state, ctx)
        can_eval = fmap_is_known_value(elts)

        if can_eval:
            new_list = [elt.value for elt in elts]
            return KnownValue(value=new_list), state
        else:
            new_elts, state = fmap_kvalue_to_node(elts, state)
            return replace_fields(node, elts=new_elts), state

    @staticmethod
    def handle_Tuple(node, state, ctx):

        elts, state = fmap_peval_expression(node.elts, state, ctx)
        can_eval = fmap_is_known_value(elts)

        if can_eval:
            new_list = tuple(elt.value for elt in elts)
            return KnownValue(value=new_list), state
        else:
            new_elts, state = fmap_kvalue_to_node(elts, state)
            return replace_fields(node, elts=new_elts), state

    @staticmethod
    def handle_Set(node, state, ctx):

        elts, state = fmap_peval_expression(node.elts, state, ctx)
        can_eval = fmap_is_known_value(elts)

        if can_eval:
            new_set = set(elt.value for elt in elts)
            return KnownValue(value=new_set), state
        else:
            new_elts, state = fmap_kvalue_to_node(elts, state)
            return replace_fields(node, elts=new_elts), state

    @staticmethod
    def handle_ListComp(node, state, ctx):
        return peval_comprehension(node, state, ctx)

    @staticmethod
    def handle_SetComp(node, state, ctx):
        return peval_comprehension(node, state, ctx)

    @staticmethod
    def handle_DictComp(node, state, ctx):
        return peval_comprehension(node, state, ctx)

    @staticmethod
    def handle_GeneratorExp(node, state, ctx):
        return peval_comprehension(node, state, ctx)

    @staticmethod
    def handle_Yield(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)

        # We cannot evaluate a yield expression,
        # so just wrap whatever we've got in a node and return.
        new_value, state = fmap_kvalue_to_node(result, state)
        return replace_fields(node, value=new_value), state

    @staticmethod
    def handle_YieldFrom(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)

        # We cannot evaluate a yield expression,
        # so just wrap whatever we've got in a node and return.
        new_value, state = fmap_kvalue_to_node(result, state)
        return replace_fields(node, value=new_value), state

    @staticmethod
    def handle_Compare(node, state, ctx):
        return peval_compare(state, ctx, node)

    @staticmethod
    def handle_Call(node, state, ctx):
        return peval_call(
            state, ctx, node.func, args=node.args, keywords=node.keywords,
            starargs=node.starargs, kwargs=node.kwargs)

    @staticmethod
    def handle_keyword(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)
        if is_known_value(result):
            # The handler for ast.Call will take care of preserving this keyword's name;
            # this method's task is to try and calculate the value.
            return KnownValue(value=result.value), state
        else:
            return node, state

    @staticmethod
    def handle_Repr(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)
        if is_known_value(result):
            success, value = try_call_method(result.value, '__repr__')
            if success:
                return KnownValue(value=value), state

        new_value, state = fmap_kvalue_to_node(result, state)
        return replace_fields(node, value=new_value), state

    @staticmethod
    def handle_Attribute(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)
        if is_known_value(result):
            success, attr = try_get_attribute(result.value, node.attr)
            if success:
                return KnownValue(value=attr), state

        new_value, state = fmap_kvalue_to_node(result, state)
        return replace_fields(node, value=new_value), state

    @staticmethod
    def handle_Subscript(node, state, ctx):
        value_result, state = _peval_expression(node.value, state, ctx)
        slice_result, state = _peval_expression(node.slice, state, ctx)
        if is_known_value(value_result) and is_known_value(slice_result):
            success, elem = try_call_method(
                value_result.value, '__getitem__', args=(slice_result.value,))
            if success:
                return KnownValue(value=elem), state

        new_value, state = fmap_kvalue_to_node(value_result, state)
        new_slice, state = fmap_kvalue_to_node(slice_result, state)
        if type(new_slice) not in (ast.Index, ast.Slice, ast.ExtSlice):
            new_slice = ast.Index(value=new_slice)
        return replace_fields(node, value=new_value, slice=new_slice), state

    @staticmethod
    def handle_Index(node, state, ctx):
        result, state = _peval_expression(node.value, state, ctx)
        if is_known_value(result):
            return KnownValue(value=result.value), state
        else:
            return result, state

    @staticmethod
    def handle_Slice(node, state, ctx):
        results, state = fmap_peval_expression((node.lower, node.upper, node.step), state, ctx)
        # how do we handle None values in nodes? Technically, they are known values
        if fmap_is_known_value_or_none(results):
            lower, upper, step = [result if result is None else result.value for result in results]
            return KnownValue(value=slice(lower, upper, step)), state
        new_nodes, state = fmap_kvalue_to_node(results, state)
        new_node = replace_fields(node, lower=new_nodes[0], upper=new_nodes[1], step=new_nodes[2])
        return new_node, state

    @staticmethod
    def handle_ExtSlice(node, state, ctx):
        results, state = fmap_peval_expression(node.dims, state, ctx)
        if fmap_is_known_value(results):
            return KnownValue(value=tuple(result.value for result in results)), state
        new_nodes, state = fmap_kvalue_to_node(results, state)
        return replace_fields(node, dims=new_nodes), state


class EvaluationResult:

    def __init__(self, fully_evaluated, node, temp_bindings, value=None):
        self.fully_evaluated = fully_evaluated
        if fully_evaluated:
            self.value = value
        self.temp_bindings = temp_bindings
        self.node = node
        self.mutated_bindings = set()


def peval_expression(node, gen_sym, bindings, py2_division=False):

    # We do not really need the Py2-style division in Py3,
    # since it never occurs in actual code.
    if py2_division and sys.version_info >= (3,):
        raise ValueError("`py2_division` is not supported on Python 3.x")

    ctx = immutableadict(bindings=bindings, py2_division=py2_division)
    state = immutableadict(gen_sym=gen_sym, temp_bindings=immutableadict())

    result, state = _peval_expression(node, state, ctx)
    if is_known_value(result):
        result_node, state = fmap_kvalue_to_node(result, state)
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


def try_peval_expression(node, bindings, py2_division=False):

    gen_sym = GenSym()
    eval_result, gen_sym = peval_expression(node, gen_sym, bindings, py2_division=py2_division)
    if eval_result.fully_evaluated:
        return True, eval_result.value
    else:
        return False, node

