import ast
import sys
import copy


class Node:
    def __init__(self, ast_node):
        self.ast_node = ast_node
        self.parents = set()
        self.children = set()


class Graph:

    def __init__(self):
        self._nodes = {}

    def add_node(self, ast_node):
        node_id = id(ast_node)
        self._nodes[node_id] = Node(ast_node)
        return node_id

    def add_edge(self, src, dest):

        assert src in self._nodes
        assert dest in self._nodes

        #assert dest not in self.children_of(src)
        #assert src not in self.parents_of(dest)

        self._nodes[src].children.add(dest)
        self._nodes[dest].parents.add(src)

    def children_of(self, node):
        return self._nodes[node].children

    def parents_of(self, node):
        return self._nodes[node].parents

    def update(self, other):
        for node in other._nodes:
            assert node not in self._nodes
        self._nodes.update(other._nodes)


class Jumps:

    def __init__(self, returns=None, breaks=None, continues=None, raises=None):
        self.returns = [] if returns is None else returns
        self.breaks = [] if breaks is None else breaks
        self.continues = [] if continues is None else continues
        self.raises = [] if raises is None else raises

    def join(self, other):
        return Jumps(
            returns=self.returns + other.returns,
            breaks=self.breaks + other.breaks,
            continues=self.continues + other.continues,
            raises=self.raises + other.raises)


class ControlFlowSubgraph:
    def __init__(self, graph, enter, exits=None, jumps=None):
        self.graph = graph
        self.enter = enter
        self.exits = [] if exits is None else exits
        self.jumps = Jumps() if jumps is None else jumps


class ControlFlowGraph:
    def __init__(self, graph, enter, exits=None, raises=None):
        self.graph = graph
        self.enter = enter
        self.exits = [] if exits is None else exits
        self.raises = [] if raises is None else raises


def _build_if_cfg(node):

    cfg_true = _build_cfg(node.body)
    exits = cfg_true.exits
    jumps = cfg_true.jumps
    graph = cfg_true.graph

    node_id = graph.add_node(node)

    graph.add_edge(node_id, cfg_true.enter)

    if len(node.orelse) > 0:
        cfg_false = _build_cfg(node.orelse)
        exits += cfg_false.exits
        jumps = jumps.join(cfg_false.jumps)
        graph.update(cfg_false.graph)
        graph.add_edge(node_id, cfg_false.enter)
    else:
        exits.append(node_id)

    return ControlFlowSubgraph(graph, node_id, exits=exits, jumps=jumps)


def _build_loop_cfg(node):

    cfg = _build_cfg(node.body)
    graph = cfg.graph

    node_id = graph.add_node(node)

    graph.add_edge(node_id, cfg.enter)

    for c_id in cfg.jumps.continues:
        graph.add_edge(c_id, node_id)
    exits = cfg.jumps.breaks
    jumps = Jumps(raises=cfg.jumps.raises)

    for exit in cfg.exits:
        graph.add_edge(exit, node_id)

    if len(node.orelse) == 0:
        exits += cfg.exits
    else:
        cfg_orelse = _build_cfg(node.orelse)

        graph.update(cfg_orelse.graph)
        exits += cfg_orelse.exits
        jumps = jumps.join(Jumps(raises=cfg_orelse.jumps.raises))
        for exit in cfg.exits:
            graph.add_edge(exit, cfg_orelse.enter)

    return ControlFlowSubgraph(graph, node_id, exits=exits, jumps=jumps)


def _build_with_cfg(node):
    cfg = _build_cfg(node.body)
    graph = cfg.graph

    node_id = graph.add_node(node)

    graph.add_edge(node_id, cfg.enter)
    return ControlFlowSubgraph(graph, node_id, exits=cfg.exits, jumps=cfg.jumps)


def _build_break_cfg(node):
    graph = Graph()
    node_id = graph.add_node(node)
    return ControlFlowSubgraph(graph, node_id, jumps=Jumps(breaks=[node_id]))


def _build_continue_cfg(node):
    graph = Graph()
    node_id = graph.add_node(node)
    return ControlFlowSubgraph(graph, node_id, jumps=Jumps(continues=[node_id]))


def _build_return_cfg(node):
    graph = Graph()
    node_id = graph.add_node(node)
    return ControlFlowSubgraph(graph, node_id, jumps=Jumps(returns=[node_id]))


def _build_statement_cfg(node):
    graph = Graph()
    node_id = graph.add_node(node)
    return ControlFlowSubgraph(graph, node_id, exits=[node_id])


def get_nontrivial_nodes(graph):
    # returns ids of nodes that can possibly raise an exception
    nodes = []
    if sys.version_info >= (3, 3):
        try_cls = (ast.Try,)
    else:
        try_cls = (ast.TryExcept, ast.TryFinally)

    for node_id, node_obj in graph._nodes.items():
        node = node_obj.ast_node
        if type(node) not in ((ast.Break, ast.Continue, ast.Pass) + try_cls):
            nodes.append(node_id)
    return nodes


def _build_excepthandler_cfg(node):
    graph = Graph()
    enter = graph.add_node(node)

    cfg = _build_cfg(node.body)
    graph.update(cfg.graph)
    graph.add_edge(enter, cfg.enter)

    return ControlFlowSubgraph(graph, enter, exits=cfg.exits, jumps=cfg.jumps)


def _build_try_block_cfg(try_node, body, handlers, orelse):

    graph = Graph()
    enter = graph.add_node(try_node)

    body_cfg = _build_cfg(body)

    jumps = body_cfg.jumps
    jumps.raises = [] # raises will be connected to all the handlers anyway

    graph.update(body_cfg.graph)
    graph.add_edge(enter, body_cfg.enter)

    handler_cfgs = [_build_excepthandler_cfg(handler) for handler in handlers]
    for handler_cfg in handler_cfgs:
        graph.update(handler_cfg.graph)
        jumps = jumps.join(handler_cfg.jumps)

    # FIXME: is it correct in case of nested `try`s?
    body_ids = get_nontrivial_nodes(body_cfg.graph)
    if len(handler_cfgs) > 0:
        # FIXME: if there are exception handlers,
        # assuming that all the exceptions are caught by them
        for body_id in body_ids:
            for handler_cfg in handler_cfgs:
                graph.add_edge(body_id, handler_cfg.enter)
    else:
        # If there are no handlers, every statement can potentially raise
        # (otherwise they wouldn't be in a try block)
        jumps = jumps.join(Jumps(raises=body_ids))

    exits = body_cfg.exits

    if len(orelse) > 0 and len(body_cfg.exits) > 0:
        # FIXME: show warning about unreachable code if there's `orelse`, but no exits from body?
        orelse_cfg = _build_cfg(orelse)
        graph.update(orelse_cfg.graph)
        jumps = jumps.join(orelse_cfg.jumps)
        for exit in exits:
            graph.add_edge(exit, orelse_cfg.enter)
        exits = orelse_cfg.exits

    for handler_cfg in handler_cfgs:
        exits += handler_cfg.exits

    return ControlFlowSubgraph(graph, enter, exits=exits, jumps=jumps)


def _build_try_finally_block_cfg(try_node, body, handlers, orelse, finalbody):

    try_cfg = _build_try_block_cfg(try_node, body, handlers, orelse)

    if len(finalbody) == 0:
        return try_cfg

    # everything has to pass through finally
    final_cfg = _build_cfg(finalbody)
    graph = try_cfg.graph
    jumps = try_cfg.jumps
    graph.update(final_cfg.graph)

    #if len(handlers) == 0:
        # FIXME: is it correct in case of nested `try`s?
        #for body_id in get_nontrivial_nodes(try_cfg.graph):
        #    graph.add_edge(body_id, final_cfg.enter)

    for exit in try_cfg.exits:
        graph.add_edge(exit, final_cfg.enter)
    exits = final_cfg.exits

    def pass_through(jump_list):
        if len(jump_list) > 0:
            for jump_id in jump_list:
                graph.add_edge(jump_id, final_cfg.enter)
            return final_cfg.exits
        else:
            return []

    returns = pass_through(jumps.returns)
    raises = pass_through(jumps.raises)
    continues = pass_through(jumps.continues)
    breaks = pass_through(jumps.breaks)

    return ControlFlowSubgraph(
        graph, try_cfg.enter, exits=final_cfg.exits,
        jumps=Jumps(returns=returns, raises=raises, continues=continues, breaks=breaks))


def _build_try_finally_cfg(node):
    # Pre-Py3.3 try block with the `finally` part
    if type(node.body[0]) == ast.TryExcept:
        # If there are exception handlers, the body consists of a single TryExcept node
        return _build_try_finally_block_cfg(
            node, node.body[0].body, node.body[0].handlers, node.body[0].orelse, node.finalbody)
    else:
        # If there are no exception handlers, the body is just a sequence of statements
        return _build_try_finally_block_cfg(
            node, node.body, [], [], node.finalbody)


def _build_try_except_cfg(node):
    # Pre-Py3.3 try block without the `finally` part
    return _build_try_finally_block_cfg(node, node.body, node.handlers, node.orelse, [])


def _build_try_cfg(node):
    # Post-Py3.3 try block
    return _build_try_finally_block_cfg(node, node.body, node.handlers, node.orelse, node.finalbody)


def _build_node_cfg(node):
    handlers = {
        ast.If: _build_if_cfg,
        ast.For: _build_loop_cfg,
        ast.While: _build_loop_cfg,
        ast.With: _build_with_cfg,
        ast.Break: _build_break_cfg,
        ast.Continue: _build_continue_cfg,
        ast.Return: _build_return_cfg,
        }

    if sys.version_info >= (3, 3):
        handlers[ast.Try] = _build_try_cfg
    else:
        handlers[ast.TryFinally] = _build_try_finally_cfg
        handlers[ast.TryExcept] = _build_try_except_cfg

    if type(node) in handlers:
        handler = handlers[type(node)]
    else:
        handler = _build_statement_cfg

    return handler(node)


def _build_cfg(statements):

    enter = id(statements[0])

    exits = [enter]
    graph = Graph()

    jumps = Jumps()

    for i, node in enumerate(statements):

        cfg = _build_node_cfg(node)

        graph.update(cfg.graph)

        if i > 0:
            for exit in exits:
                graph.add_edge(exit, cfg.enter)

        exits = cfg.exits
        jumps = jumps.join(cfg.jumps)

        if type(node) in (ast.Break, ast.Continue, ast.Return):
            # Issue a warning about unreachable code?
            break

    return ControlFlowSubgraph(graph, enter, exits=exits, jumps=jumps)


def build_cfg(statements):
    cfg = _build_cfg(statements)
    assert len(cfg.jumps.breaks) == 0
    assert len(cfg.jumps.continues) == 0
    return ControlFlowGraph(
        cfg.graph, cfg.enter, cfg.exits + cfg.jumps.returns, raises=cfg.jumps.raises)
