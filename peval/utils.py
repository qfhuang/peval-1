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
    source = unshift(inspect.getsource(fn))
    return ast.parse(source)


def unshift(source):
    ''' Shift source to the left - so that it starts with zero indentation
    '''
    source = source.rstrip("\n ").lstrip("\n")
    indent = re.match(r"([ \t])*", source).group(0)
    lines = source.split("\n")
    shifted_lines = []
    for line in lines:
        line = line.rstrip()
        if len(line) > 0:
            if not line.startswith(indent):
                raise ValueError("Inconsistent indent at line " + repr(line))
            shifted_lines.append(line[len(indent):])
        else:
            shifted_lines.append(line)
    return "\n".join(shifted_lines)


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

