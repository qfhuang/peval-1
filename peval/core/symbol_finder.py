import ast
import six

from peval.core.immutable import immutableset
from peval.core.walker import ast_inspector


if six.PY2:
    STORE_CTXS = (ast.Store, ast.Param)
else:
    STORE_CTXS = (ast.Store,)


@ast_inspector
class _find_symbol_creations:

    @staticmethod
    def handle_arg(node, state, **kwds):
        return state.update(names=state.names.add(node.arg))

    @staticmethod
    def handle_Name(node, state, **kwds):
        if type(node.ctx) in STORE_CTXS:
            return state.update(names=state.names.add(node.id))
        else:
            return state

    @staticmethod
    def handle_ClassDef(node, state, **kwds):
        return state.update(names=state.names.add(node.name))

    @staticmethod
    def handle_alias(node, state, **kwds):
        name = node.asname if node.asname else node.name
        if '.' in name:
            name = name.split('.', 1)[0]
        return state.update(names=state.names.add(name))


def find_symbol_creations(tree):
    ''' Return a set of all local variable names in ast tree
    '''
    state = _find_symbol_creations(tree, state=dict(names=immutableset()))
    return state.names


@ast_inspector
class _find_symbol_usages:

    @staticmethod
    def handle_Name(node, state, **kwds):
        if type(node.ctx) == ast.Load:
            return state.update(names=state.names.add(node.id))
        else:
            return state


def find_symbol_usages(tree):
    ''' Return a set of all variables used in ast tree
    '''
    state = _find_symbol_usages(tree, state=dict(names=immutableset()))
    return state.names
