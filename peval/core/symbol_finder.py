import ast
import six

from peval.core.walker import ast_inspector


if six.PY2:
    STORE_CTXS = (ast.Store, ast.Param)
else:
    STORE_CTXS = (ast.Store,)


@ast_inspector
class _find_symbol_creations:

    @staticmethod
    def visit_arg(node, state, **kwds):
        state.add(node.arg)
        return node

    @staticmethod
    def visit_name(node, state, **kwds):
        if isinstance(node.ctx, STORE_CTXS):
            state.add(node.id)
        return node

    @staticmethod
    def visit_classdef(node, state, **kwds):
        state.add(node.arg)
        return node

    @staticmethod
    def visit_alias(node, state, **kwds):
        name = node.asname if node.asname else node.name
        if '.' in name:
            name = name.split('.', 1)[0]
        state.add(name)
        return node


def find_symbol_creations(tree):
    ''' Return a set of all local variable names in ast tree
    '''
    return _find_symbol_creations(tree, state=set())


@ast_inspector
class _find_symbol_usages:

    @staticmethod
    def visit_name(node, state, **kwds):
        if isinstance(node.ctx, ast.Load):
            state.add(node.id)
        return node


def find_symbol_usages(tree):
    ''' Return a set of all variables used in ast tree
    '''
    return _find_symbol_usages(tree, state=set())
