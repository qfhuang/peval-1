import ast
import astunparse
import inspect
import itertools
from functools import reduce
import copy

from peval.core.gensym import GenSym
from peval.core.cfg import build_cfg
from peval.core.expression import peval_expression
from peval.core.walker import Walker


class Value:

    def __init__(self, value=None, undefined=False):
        if undefined:
            self.defined = False
        else:
            self.defined = True
            self.value = value

    def __str__(self):
        if not self.defined:
            return "<undefined>"
        else:
            return "<" + str(self.value) + ">"

    def __repr__(self):
        if not self.defined:
            return "Value(undefined=True)"
        else:
            return "Value(value={value})".format(value=repr(self.value))


def meet_values(val1, val2):
    if not val1.defined or not val2.defined:
        return Value(undefined=True)

    v1 = val1.value
    v2 = val2.value

    if v1 is v2:
        return Value(value=v1)

    eq = False
    try:
        eq = (v1 == v2)
    except:
        pass

    if eq:
        return Value(value=v1)
    else:
        return Value(undefined=True)


class Environment:

    def __init__(self, values=None):
        self.values = values if values is not None else {}

    @classmethod
    def from_dict(cls, values):
        return cls(values={name:Value(value=value) for name, value in values.items()})

    def known_values(self):
        return {name:value.value for name, value in self.values.items() if value.defined}


def meet_envs(env1, env2):

    lhs = env1.values
    rhs = env2.values
    lhs_keys = set(lhs.keys())
    rhs_keys = set(rhs.keys())
    result = {}

    for var in lhs_keys - rhs_keys:
        result[var] = lhs[var]

    for var in rhs_keys - lhs_keys:
        result[var] = rhs[var]

    for var in lhs_keys & rhs_keys:
        result[var] = meet_values(lhs[var], rhs[var])

    return Environment(values=result)


def my_reduce(func, seq):
    if len(seq) == 1:
        return seq[0]
    else:
        return reduce(func, seq[1:], seq[0])


def forward_transfer(gen_sym, in_env, statement):

    if isinstance(statement, ast.Assign):
        target = statement.targets[0].id
        gen_sym, result = peval_expression(gen_sym, in_env.known_values(), statement.value)

        new_values=dict(in_env.values)

        for name in result.mutated_bindings:
            new_values[name] = Value(undefined=True)

        if result.fully_evaluated:
            new_value = Value(value=result.value)
        else:
            new_value = Value(undefined=True)
        new_values[target] = new_value
        new_node = ast.Assign(target=target, value=result.node)

        out_env = Environment(values=new_values)
        return gen_sym, out_env, new_node, result.temp_bindings

    elif isinstance(statement, (ast.Expr, ast.Return)):
        gen_sym, result = peval_expression(gen_sym, in_env.known_values(), statement.value)

        new_values=dict(in_env.values)

        for name in result.mutated_bindings:
            new_values[name] = Value(undefined=True)

        out_env = Environment(values=new_values)
        return gen_sym, out_env, type(statement)(value=result.node), result.temp_bindings

    elif isinstance(statement, ast.If):
        gen_sym, result = peval_expression(gen_sym, in_env.known_values(), statement.test)

        new_values=dict(in_env.values)

        for name in result.mutated_bindings:
            new_values[name] = Value(undefined=True)

        out_env = Environment(values=new_values)
        new_node = ast.If(test=result.node, body=statement.body, orelse=statement.orelse)
        return gen_sym, out_env, new_node, result.temp_bindings

    else:
        raise NotImplementedError(type(statement))


class State:

    def __init__(self, out_env, node, temp_bindings):
        self.out_env = out_env
        self.node = node
        self.temp_bindings = temp_bindings


def maximal_fixed_point(gen_sym, graph, enter, bindings):

    states = {
        node_id:State(Environment(), graph._nodes[node_id].ast_node, {})
        for node_id in graph._nodes}
    enter_env = Environment.from_dict(bindings)

    # first make a pass over each basic block
    todo_forward = set(graph._nodes)

    while todo_forward:
        node_id = todo_forward.pop()
        state = states[node_id]

        # compute the environment at the entry of this BB
        if node_id == enter:
            new_in_env = enter_env
        else:
            parent_envs = list(map(
                lambda parent_id: states[parent_id].out_env,
                graph.parents_of(node_id)))
            new_in_env = my_reduce(meet_envs, parent_envs)

        # propagate information for this basic block
        gen_sym, new_out_env, new_node, temp_bindings = \
            forward_transfer(gen_sym, new_in_env, graph._nodes[node_id].ast_node)
        if new_out_env != states[node_id].out_env:
            states[node_id] = State(new_out_env, new_node, temp_bindings)
            todo_forward |= graph.children_of(node_id)

    # Converged
    new_nodes = {}
    temp_bindings = {}
    for node_id, state in states.items():
        new_nodes[node_id] = state.node
        temp_bindings.update(state.temp_bindings)

    return new_nodes, temp_bindings


def replace_nodes(tree, new_nodes):
    return _replace_nodes.transform(tree, ctx=dict(new_nodes=new_nodes))


@Walker
def _replace_nodes(node, ctx, **kwds):
    if id(node) in ctx.new_nodes:
        return ctx.new_nodes[id(node)]
    else:
        return node


def fold(tree, constants):
    statements = tree.body
    cfg = build_cfg(statements)
    gen_sym = GenSym.for_tree(tree)
    new_nodes, temp_bindings = maximal_fixed_point(gen_sym, cfg.graph, cfg.enter, constants)
    constants = dict(constants)
    constants.update(temp_bindings)
    new_tree = replace_nodes(tree, new_nodes)
    return new_tree, constants
