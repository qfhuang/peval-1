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


def value_to_node(value, gen_sym, preferred_name=None):

    number_types = (int, float, complex) + (tuple() if sys.version_info >= (3,) else (long,))

    if value is True or value is False or value is None:
        if sys.version_info >= (3, 4):
            return ast.NameConstant(value=value), gen_sym, {}
        else:
            # Before Py3.4 these constants are not actually constants,
            # but just builtin variables, and can, therefore, be redefined.
            name, gen_sym = gen_sym(str(value))
            return ast.Name(id=str(value), ctx=ast.Load()), gen_sym, {name: value}
    elif type(value) == str or (sys.version_info < (3,) and type(value) == unicode):
        return ast.Str(s=value), gen_sym, {}
    elif sys.version_info >= (3,) and type(value) == bytes:
        return ast.Bytes(s=value), gen_sym, {}
    elif type(value) in number_types:
        return ast.Num(n=value), gen_sym, {}
    else:
        if preferred_name is None:
            name, gen_sym = gen_sym('temp')
        else:
            name = preferred_name
        return ast.Name(id=name, ctx=ast.Load()), gen_sym, {name: value}


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


def replace_fields(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
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
