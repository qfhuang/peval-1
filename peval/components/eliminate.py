import ast
import copy

from peval.core.visitor import Visitor


def eliminate(node, _):
    node = copy.deepcopy(node)
    visitor = Eliminator()
    visitor.visit(node)
    return node, _


def replace_node(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


class Eliminator(Visitor):
    ''' Simplify AST, given information about what variables are known
    '''
    def visit_FunctionDef(self, node):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        Inline function if it is marked with @inline.
        '''
        self.generic_visit(node)
        return replace_node(node, body=_eliminate(node.body))


def _eliminate(node_list):
    ''' Dead code elimination - remove "pass", code after return
    '''
    for i, node in enumerate(list(node_list)):
        if isinstance(node, ast.Pass) and len(node_list) > 1:
            node_list.remove(node)
        if isinstance(node, ast.Return):
            return node_list[:i+1]
    return node_list
