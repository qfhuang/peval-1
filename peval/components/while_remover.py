import ast
import copy

from peval.core.walker import Walker


def while_remover(node, constants):
    node = WhileRemover.transform(node)
    return node, constants


@Walker
class WhileRemover:

    @staticmethod
    def visit_while(node, **kwds):

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
