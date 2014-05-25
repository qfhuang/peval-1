import ast
import sys


NUMBER_TYPES = (int, float, complex) + (tuple() if sys.version_info >= (3,) else (long,))


class KnownValue(object):

    def __init__(self, value, preferred_name=None):
        self.value = value
        self.preferred_name = preferred_name

    def __str__(self):
        return (
            "<" + str(self.value)
            + (" (" + self.preferred_name + ")" if self.preferred_name is not None else "")
            + ">")

    def __repr__(self):
        return "KnownValue({value}, preferred_name={name})".format(
            value=repr(self.value), name=repr(self.preferred_name))


def is_known_value(node_or_kvalue):
    return type(node_or_kvalue) == KnownValue


def kvalue_to_node(kvalue, gen_sym):

    value = kvalue.value

    if value is True or value is False or value is None:
        if sys.version_info >= (3, 4):
            return ast.NameConstant(value=value), gen_sym, {}
        else:
            # Before Py3.4 these constants are not actually constants,
            # but just builtin variables, and can, therefore, be redefined.
            name, gen_sym = gen_sym(str(value))
            return ast.Name(id=name, ctx=ast.Load()), gen_sym, {name: value}
    elif type(value) == str or (sys.version_info < (3,) and type(value) == unicode):
        return ast.Str(s=value), gen_sym, {}
    elif sys.version_info >= (3,) and type(value) == bytes:
        return ast.Bytes(s=value), gen_sym, {}
    elif type(value) in NUMBER_TYPES:
        return ast.Num(n=value), gen_sym, {}
    else:
        if kvalue.preferred_name is None:
            name, gen_sym = gen_sym('temp')
        else:
            name = kvalue.preferred_name
        return ast.Name(id=name, ctx=ast.Load()), gen_sym, {name: value}


def value_to_node(value, gen_sym):
    return kvalue_to_node(KnownValue(value), gen_sym)
