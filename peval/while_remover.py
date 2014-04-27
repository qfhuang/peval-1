import ast
import copy

from peval.visitor import Visitor


def while_remover(node, _):
    node = copy.deepcopy(node)
    visitor = WhileRemover()
    visitor.visit(node)
    return node, _


class WhileRemover(Visitor):
    ''' Simplify AST, given information about what variables are known
    '''
    def visit_While(self, node):
        ''' Make a call, if it is a pure function,
        and handle mutations otherwise.
        Inline function if it is marked with @inline.
        '''
        self.generic_visit(node)

        for idx, e in enumerate(node.body):
            if isinstance(e, ast.Break):
                break
        else:
            idx = -1

        if idx != -1:
            if idx == 0:
                new_body = [ast.Pass()]
            else:
                new_body = node.body[:idx]
            return ast.If(test=node.test, body=new_body, orelse=node.orelse)
        else:
            return node
