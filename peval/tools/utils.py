import ast
import re
import sys

import six
from six.moves import builtins


def unindent(source):
    """
    Shift source to the left so that it starts with zero indentation.
    """
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
    """
    Get the identifier (symbol) for an AST node representing a function argument.
    """
    # In Py2 the node for a function argument is a ``Name`` node.
    # In Py3 it is a special ``arg`` node.
    if six.PY2:
        return fn_arg_node.id
    else:
        return fn_arg_node.arg


def replace_fields(node, **kwds):
    """
    Return a node with several of its fields replaced by the given values.
    """
    new_kwds = dict(ast.iter_fields(node))
    for key, value in kwds.items():
        if value is not new_kwds[key]:
            break
    else:
        return node
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


def ast_equal(node1, node2):
    """
    Test two AST nodes or two lists of AST nodes for equality.
    """
    if type(node1) != type(node2):
        return False

    if type(node1) == list:
        if len(node1) != len(node2):
            return False
        for elem1, elem2 in zip(node1, node2):
            if not ast_equal(elem1, elem2):
                return False
    elif isinstance(node1, ast.AST):
        for attr, value1 in ast.iter_fields(node1):
            value2 = getattr(node2, attr)
            if not ast_equal(value1, value2):
                return False
    else:
        if node1 != node2:
            return False

    return True
