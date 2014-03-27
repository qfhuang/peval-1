import ast
import six


class LocalsVisitor(ast.NodeVisitor):

    def __init__(self):
        self._locals = set()
        self._ctxs = (ast.Store, ast.Param) if six.PY2 else ast.Store
        super(LocalsVisitor, self).__init__()

    def visit_arg(self, node):
        self.generic_visit(node)
        self._locals.add(node.arg)

    def visit_Name(self, node):
        self.generic_visit(node)
        if isinstance(node.ctx, self._ctxs):
            self._locals.add(node.id)

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        self._locals.add(node.name)

    def visit_alias(self, node):
        self.generic_visit(node)

        name = node.asname if node.asname else node.name

        if '.' in name:
            name = name.split('.', 1)[0]

        self._locals.add(name)

    def get_locals(self):
        return self._locals


def find_symbol_creations(tree):
    ''' Return a set of all local variable names in ast tree
    '''
    visitor = LocalsVisitor()
    visitor.visit(tree)
    return visitor.get_locals()
