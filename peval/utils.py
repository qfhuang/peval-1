import ast
import re
import sys

import six
from six.moves import builtins


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


def get_fn_arg_id(fn_arg_node):
    # In Py2 the node for a function argument is a ``Name`` node.
    # In Py3 it is a special ``arg`` node.
    if six.PY2:
        return fn_arg_node.id
    else:
        return fn_arg_node.arg


def replace_fields(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    for key, value in kwds.items():
        if value is not new_kwds[key]:
            break
    else:
        return node
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


def ast_equal(node1, node2):
    if type(node1) != type(node2):
        return False

    for attr, value1 in ast.iter_fields(node1):
        value2 = getattr(node2, attr)
        if type(value1) == list:
            if not all(ast_equal(elem1, elem2) for elem1, elem2 in zip(value1, value2)):
                return False
        elif isinstance(value1, ast.AST):
            if not ast_equal(value1, value2):
                return False
        elif value1 != value2:
            return False

    return True
