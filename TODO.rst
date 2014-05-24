General
-------

* Add exports from ``core`` and ``components`` submodules to their ``__init__``'s.


core/walker
-----------

* BUG: the ``body`` field of ``Lambda`` or ``IfExp`` holds a single node, not a list --- need to take it into account when checking for returned types (but still replace it with ``Pass`` when a handler returns ``None``).


core/mangler
------------

* BUG: when encountering a nested function definition, run it through ``Function`` and check which closure variables it uses (inlcuding the function name itself).
  Then mangle only them, leaving the rest intact.


core/symbol_finder
------------------

* ?BUG: ``find_symbol_usages()`` must include other ways of using a symbol (if there are any).
* BUG: ``find_symbol_creations()`` must include symbols created by ``except Exception as e`` in the list.
  In Python3 ``e`` is just a plain string, so it is not caught by the current algorithm looking for ``ast.Store`` constructors.


core/expression
---------------

* FEATURE: add support for varargs and kwargs in ``handle_Call()`` (see ``assert`` there)
* BUG: evaluating ``bool()`` in handling ``IfExp`` or ``BoolOp`` is potentially (albeit unlikely) unsafe (if it is some weird object with a weird ``__bool__()`` implementation).


mutation detection (in expressions)
-----------------------------------

* BUG: if an expression is passed as an argument to a function (e.g. ``f(c * 2)``), one of the arguments of this expression can still be passed through and then mutated by ``f()``.
  This case must be handled somehow.
  Similarly, a method call can mutate a variable passed to the object earlier, for example ``Foo(x).transform()``, where ``x`` is a list.
  But this only applies to "bad" objects, because not taking a copy of a mutable argument and then mutate it silently is really error-prone.


components/fold
---------------

* BUG: take into account ``division`` feature when evaluating expressions.


components/prune_assignments
----------------------------

* BUG: need to keep the variables that are used as closures in nested functions.


components/prune_cfg
--------------------

* FEATURE: we can detect unconditional jumps in ``for`` loops as well, but in order to remove the loop, we need the loop unrolling functionality.
* BUG: evaluating ``bool(node.test)`` is potentially (albeit unlikely) unsafe (if it is some weird object with a weird ``__bool__()`` implementation).


components/inline
-----------------

* BUG: when inlining a function, we must mangle the globals too, in case it uses a different set from what the parent function uses.
* FEATURE: add support for inlining functions with varargs/kwargs.
  Probably just run the function through ``partial_apply`` before inlining?
* BUG: a function is inlined by replacing it with a ``while True`` loop and using variable assignment and ``break`` instead of ``return``.
  But if the ``return`` is inside another loop, this will lead to unexpected behavior.


(new) components/unroll
-----------------------

Conditionally unroll loops.
Possible policies:

* based on a *keyword* ``unroll`` (that is, look for a ``ast.Name(id='unroll')``);
* based on a *function* ``unroll`` (check if the iterator in a loop is the unrolling iterator);
* based on heuristics (unroll range iterators, lists, tuples or dicts with less than N entries).


(new) components/macro
----------------------

Macros are similar to inlines, but the expressions passed to the function are substituted in its body without any changes and the resulting body is used to replace the macro call.
If the function was called in an expression context, check that the body contains only one ``ast.Expr`` and substitute its value.

::

    @macro
    def mad(x, y, z):
        x * y + z

    a = mad(b[1], c + 10, d.value)
    # --->
    # a = b[1] * (c + 10) + d.value


(new) automatic specializer
---------------------------

Make the library make all the bookkeeping for you, creating specialized versions and using them as needed by the following decorator

::

    @peval.specialize_on('n', globals(), locals())
    def power(x, n):
        ...

But in this case the arguments we specialize on must be hashable. It they
are not, you will have to dispatch to specialized function yourself.
