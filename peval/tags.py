import funcsigs


def pure(fn):
    """
    Marks the function as pure (not having any side effects, except maybe argument mutation).
    """
    fn._peval_pure = True
    return fn


def impure(fn):
    """
    Marks the function as not pure (having some side effects).
    """
    fn._peval_pure = False
    return fn


def is_pure(fn):
    return getattr(fn, '_peval_pure', None)


def mutating(fn, *argnames):
    """
    Marks the function as mutating some of its arguments.
    """
    sig = funcsigs.signature(fn)
    mutating = dict((name, None) for name in sig.parameters)
    for name in argnames:
        mutating[name] = True
    fn._peval_mutating = mutating
    return fn


def nonmutating(fn, *argnames):
    sig = funcsigs.signature(fn)
    mutating = dict((name, None) for name in sig.parameters)
    for name in argnames:
        mutating[name] = False
    fn._peval_mutating = mutating
    return fn


def is_mutating(fn, argname):
    if hasattr(fn, '_peval_mutating'):
        return fn._peval_mutating[argname]
    else:
        return None


def immutable(cls):
    """
    Marks the objects of this class as immutable.
    """
    cls._peval_immutable = True
    return cls


def inline(fn):
    """
    Marks the function for inlining.
    """
    if is_macro(fn):
        raise ValueError("A function cannot be marked for inlining and expansion at the same time")
    fn._peval_inline = True
    return fn


def is_inline(fn):
    return getattr(fn, '_peval_inline', None)


def macro(fn):
    """
    Marks the function for expansion.
    """
    if is_inline(fn):
        raise ValueError("A function cannot be marked for inlining and expansion at the same time")
    fn._peval_macro = True
    return fn


def is_macro(fn):
    return getattr(fn, '_peval_macro', None)


def unroll(seq):
    """
    Marks the sequence for unrolling (in a loop or in a comprehension).
    """
    return seq
