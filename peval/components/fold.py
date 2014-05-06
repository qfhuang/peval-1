import ast
import astunparse
import inspect
import itertools
from functools import reduce

from peval.core.cfg import build_cfg


class Environment:

    def __init__(self, values=None):
        self.values = {} if values is None else values


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


def try_eval(env, expr):
    if isinstance(expr, ast.Name):
        if expr.id in env.values:
            return env.values[expr.id]
        else:
            return Value(undefined=True)
    elif isinstance(expr, ast.Num):
        return Value(values=[expr.n])
    elif isinstance(expr, ast.BinOp):
        assert isinstance(expr.op, ast.Add)
        lval = try_eval(env, expr.left)
        rval = try_eval(env, expr.right)
        if not lval.defined or not rval.defined:
            return Value(undefined=True)
        if not lval.hashable or not rval.hashable:
            return Value(undefined=True)
        return Value(values=set(x + y for x, y in itertools.product(lval.values, rval.values)))
    else:
        return Value(undefined=True)


def forward_transfer(in_env, statement):

    if isinstance(statement, ast.Assign):
        target = statement.targets[0].id
        value = try_eval(in_env, statement.value)
        print("* Assign to", target, statement.value, value)
        new_values=dict(in_env.values)
        new_values[target] = value
        out_env = Environment(values=new_values)
        return out_env
    else:
        return in_env


def maximal_fixed_point(graph, enter, init_env):
    # state at the entry and exit of each basic block
    in_envs, out_envs = {}, {}
    for node_id in graph._nodes:
        in_envs[node_id] = Environment()
        out_envs[node_id] = Environment()
    in_envs[enter] = init_env

    # first make a pass over each basic block
    todo_forward = set(graph._nodes)

    while todo_forward:
        node_id = todo_forward.pop()

        # compute the environment at the entry of this BB
        parent_envs = list(map(out_envs.get, graph.parents_of(node_id)))
        if len(parent_envs) > 1:
            new_in_env = reduce(meet_envs, parent_envs[1:], parent_envs[0])
        elif len(parent_envs) == 1:
            new_in_env = parent_envs[0]
        elif node_id == enter:
            new_in_env = init_env

        # propagate information for this basic block
        new_out_env = forward_transfer(new_in_env, graph._nodes[node_id].ast_node)
        if new_out_env != out_envs[node_id]:
            out_envs[node_id] = new_out_env
            todo_forward |= graph.children_of(node_id)

    # IN and OUT have converged
    return out_envs


def fold(tree, constants):
    cfg = build_cfg(tree)
    env = Environment(values=constants)
    OUT = maximal_fixed_point(cfg.graph, cfg.enter, env)
    node_id = id(statements[-1])
    print(OUT[node_id].values)

    #return new_tree, new_constants
