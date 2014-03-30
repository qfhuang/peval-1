# -*- encoding: utf-8 -*-

import re
import ast
import inspect
import unittest
import logging

import six


def get_fn_arg_id(fn_arg_node):
    # In Py2 the node for a function argument is a ``Name`` node.
    # In Py3 it is a special ``arg`` node.
    if six.PY2:
        return fn_arg_node.id
    else:
        return fn_arg_node.arg


def fn_to_ast(fn):
    ''' Return AST tree, parsed from fn
    '''
    source = shift_source(inspect.getsource(fn))
    return ast.parse(source)


def shift_source(source):
    ''' Shift source to the left - so that it starts with zero indentation
    '''
    source = source.rstrip()
    if source.startswith('\n'):
        source = source.lstrip('\n')
    if source.startswith(' '):
        n_spaces = len(re.match('^([ ]+)', source).group(0))
        source = '\n'.join(line[n_spaces:] for line in source.split('\n'))
    return source



def eval_ast(tree, globals_=None):
    ''' Evaluate AST tree, which sould contain only one root node
    '''
    assert isinstance(tree, ast.Module) and len(tree.body) == 1
    ast.fix_missing_locations(tree)
    code_object = compile(tree, '<nofile>', 'exec')
    locals_ = {}
    eval(code_object, globals_, locals_)
    return locals_[tree.body[0].name]


def get_logger(name, debug=False):
    logger = logging.getLogger(name=name)
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

