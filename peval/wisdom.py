import operator
import types
import sys

import funcsigs

from peval.tags import is_pure, is_mutating


"""
Policies:

- default_pure (True/False)
- default_mutating (True/False)
- unroll (syntactic/semantic) - can be used both for loops and for comprehensions


Tags:

- @macro - marks for expansion
- @inline - marks for inlining
- @pure - marks as pure (i.e., no side effects, not counting argument mutation)
- @impure - marks as having side effects
- @mutating(argnames) - marks as mutating some of the arguments
- @nonmutating(argnames)
- @immutable (for a class)


When evaluating a function:

- get pure tag
    - check if the function has the tag, if yes, use it
    - check if the function is known (e.g. a builtin), if yes, use the known tag
    - use default_pure value
- get the list of mutated args
    - check if the function has the tag, use it (the args that are not mentioned
      are assumed to have the opposite property)
    - check if the function is known, if yes, use the known tag
    - check if any of the types are immutable (have the tag, or are known),
      filter the list of mutations
    - if some unknowns are left, use default_mutating value
"""


KNOWN_SIGNATURES = {
    bool: funcsigs.signature(lambda obj: None),
    isinstance: funcsigs.signature(lambda obj, tp: None),
    getattr: funcsigs.signature(lambda obj, name, default=None: None),
    iter: funcsigs.signature(lambda obj: None),

    str.__getitem__: funcsigs.signature(lambda self, index: None),
    range: funcsigs.signature(lambda *args: None),
    repr: funcsigs.signature(lambda *obj: None),

    operator.pos: funcsigs.signature(lambda a: None),
    operator.neg: funcsigs.signature(lambda a: None),
    operator.not_: funcsigs.signature(lambda a: None),
    operator.invert: funcsigs.signature(lambda a: None),

    operator.add: funcsigs.signature(lambda a, b: None),
    operator.sub: funcsigs.signature(lambda a, b: None),
    operator.mul: funcsigs.signature(lambda a, b: None),
    operator.truediv: funcsigs.signature(lambda a, b: None),
    operator.floordiv: funcsigs.signature(lambda a, b: None),
    operator.mod: funcsigs.signature(lambda a, b: None),
    operator.pow: funcsigs.signature(lambda a, b: None),
    operator.lshift: funcsigs.signature(lambda a, b: None),
    operator.rshift: funcsigs.signature(lambda a, b: None),
    operator.or_: funcsigs.signature(lambda a, b: None),
    operator.xor: funcsigs.signature(lambda a, b: None),
    operator.and_: funcsigs.signature(lambda a, b: None),

    operator.eq: funcsigs.signature(lambda a, b: None),
    operator.ne: funcsigs.signature(lambda a, b: None),
    operator.lt: funcsigs.signature(lambda a, b: None),
    operator.le: funcsigs.signature(lambda a, b: None),
    operator.gt: funcsigs.signature(lambda a, b: None),
    operator.ge: funcsigs.signature(lambda a, b: None),
    operator.is_: funcsigs.signature(lambda a, b: None),
    operator.is_not: funcsigs.signature(lambda a, b: None),
}

if sys.version_info < (3,):
    KNOWN_SIGNATURES.update({
        operator.div: funcsigs.signature(lambda a, b: None),
    })


def get_signature(obj):
    if obj in KNOWN_SIGNATURES:
        return KNOWN_SIGNATURES[obj]

    if type(obj) == types.FunctionType:
        return funcsigs.signature(obj)
    elif type(obj) == types.MethodType:
        return funcsigs.signature(obj)
    elif type(obj) == type:
        if type(obj.__init__) == types.FunctionType:
            return funcsigs.signature(obj.__init__)
    elif hasattr(obj, '__call__') and type(obj.__call__) == types.MethodType:
        raise ValueError

    raise ValueError("Cannot get signature from", obj)


def get_mutation_info(func, argtypes):
    return True, []
