import ast
import re
import sys

import six
from six.moves import builtins


NUMBER_TYPES = six.integer_types + (float,)
STRING_TYPES = six.string_types + (six.text_type, six.binary_type)


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


def get_literal_node(value):
    ''' If value can be represented as literal value,
    return AST node for it. Literals are never mutable!
    '''
    if type(value) in NUMBER_TYPES:
        return ast.Num(value)
    elif type(value) in STRING_TYPES:
        return ast.Str(value)
    elif value in (False, True, None):
        if sys.version_info >= (3, 4, 0):
            return ast.NameConstant(value=value)
        else:
            return ast.Name(id=repr(value), ctx=ast.Load())


def get_node_value_if_known(node, constants):
    ''' Return tuple of boolean(value is known), and value itself
    '''
    known = lambda x: (True, x)
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        name = node.id
        if name in constants:
            return known(constants[name])
        else:
            if hasattr(builtins, name):
                return known(getattr(builtins, name))
    elif isinstance(node, ast.Num):
        return known(node.n)
    elif isinstance(node, ast.Str):
        return known(node.s)
    elif sys.version_info >= (3, 4, 0) and isinstance(node, ast.NameConstant):
        return known(node.value)
    return False, None
