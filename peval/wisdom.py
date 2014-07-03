import types

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


def get_mutation_info(func, argtypes):


    pure_tag = is_pure(func)
    if pure_tag is None:


