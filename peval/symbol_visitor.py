'''
Taken from Meta package to avoid depending on it, and rewritten using ast.NodeVisitor.
'''
import ast


class SymbolVisitor(ast.NodeVisitor):

    def __init__(self, ctx_types=(ast.Load, ast.Store)):

        if not isinstance(ctx_types, (list, tuple)):
            ctx_types = (ctx_types,)

        self.ctx_types = tuple(ctx_types)
        self.ids = set()

        super(SymbolVisitor, self).__init__()

    def visit_Name(self, node):
        if isinstance(node.ctx, self.ctx_types):
            self.ids.add(node.id)

    def visit_alias(self, node):

        name = node.asname if node.asname else node.name

        if '.' in name:
            name = name.split('.', 1)[0]

        if ast.Store in self.ctx_types:
            self.ids.add(name)


def get_symbols(node, ctx_types=(ast.Load, ast.Store)):
    '''
    Returns all symbols defined in an ast node.

    if ctx_types is given, then restrict the symbols to ones with that context.

    :param node: ast node
    :param ctx_types: type or tuple of types that may be found assigned to the `ctx` attribute of
                      an ast Name node.

    '''
    gen = SymbolVisitor(ctx_types)
    gen.visit(node)
    return gen.ids
