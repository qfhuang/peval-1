import ast
import six


def get_locals(tree):
    ''' Return a set of all local variable names in ast tree
    '''
    visitor = LocalsVisitor()
    visitor.visit(tree)
    return visitor.get_locals()


class LocalsVisitor(ast.NodeVisitor):
    def __init__(self):
        self._locals = set()
        self._locals_ctx = (ast.Store, ast.Param) if six.PY2 else ast.Store
        super(LocalsVisitor, self).__init__()

    def visit_arg(self, node):
        self.generic_visit(node)
        self._locals.add(node.arg)

    def visit_Name(self, node):
        self.generic_visit(node)
        if isinstance(node.ctx, self._locals_ctx):
            self._locals.add(node.id)

    def get_locals(self):
        return self._locals


class GenSym:

    def __init__(self, tree=None):
        self._names = get_locals(tree) if tree is not None else set()
        self._counter = 0

    def _gen_name(self, tag):
        return '__' + tag + '_' + str(self._counter)

    def __call__(self, tag='peval_sym'):

        while True:
            self._counter += 1
            name = self._gen_name(tag)
            if name not in self._names:
                break

        self._names.add(name)
        return name

    def get_state(self):
        return self._counter, self._names

    def set_state(self, state):
        self._counter, self._names = state

    @classmethod
    def from_state(cls, state):
        gs = cls()
        gs.set_state(state)
        return gs
