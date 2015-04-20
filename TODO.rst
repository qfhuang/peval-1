General
-------

* Add exports from ``core`` and ``components`` submodules to their ``__init__``'s.
* It seems to be common to compare two AST's before and after some function to check if there were any changes. If it takes much time, we can make walkers set some flag if they made a change in the AST and then just propagate it. Drawbacks: propagating an additional value; changes can take place outside of walkers.


core/value
----------

* ?FEATURE: extend the class of literals, adding non-trivial immutable objects, e.g. tuples and slices.
* ``value_to_node()`` can be called ``reify()`` (the opposite is "reflect", but I don't think I have a need for that --- the opposite operation is performed by ``peval``-prefixed functions).


core/walker
-----------

* BUG: the ``body`` field of ``Lambda`` or ``IfExp`` holds a single node, not a list --- need to take it into account when checking for returned types (but still replace it with ``Pass`` when a handler returns ``None``).
* FEATURE: make ``visit_after`` call do nothing if we are actually in the visiting-after stage (so that one does not have to write ``if not visiting_after: visit_after()``). Or even make it return ``visiting_after`` value, similarly to how ``fork`` works.


core/mangler
------------

* BUG: when encountering a nested function definition, run it through ``Function`` and check which closure variables it uses (inlcuding the function name itself).
  Then mangle only them, leaving the rest intact.


core/symbol_finder
------------------

* ?BUG: ``find_symbol_usages()`` must include other ways of using a symbol (if there are any).
* BUG: ``find_symbol_creations()`` must include symbols created by ``except Exception as e`` in the list.
  In Python3 ``e`` is just a plain string, so it is not caught by the current algorithm looking for ``ast.Store`` constructors.
* BUG: ``find_symbol_usages()`` (and probably ``find_symbol_creations()`` as well) must take into account temporary rebindings in comprehensions.


core/function
-------------

* FEATURE: implement "layered" context object to avoid copying massive globals dictionaries.


core/expression
---------------

* FEATURE: add partial evaluation of lambdas (and nested function/class definitions).
  Things to look out to:

    * Need to see which outer variables the lambda uses as closures.
      These we need to lock --- ``prune_assignments`` cannot remove them.
    * Mark it as impure and mutating by default, unless the user explicitly marks it otherwise.
    * Run its own partial evaluation for the nested function?

* FEATURE: in Py3 ``iter()`` of a ``zip`` object returns itself, so list comprehension evaluator considers it unsafe to iterate it.
  Perhaps comprehensions need the same kind of policies as loop unroller does, to force evaluation in such cases (also in cases of various generator functions that can reference global variables and so on).


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
  Need to run it through the safe call function from the expression evaluator.


components/inline
-----------------

* BUG: when inlining a function, we must mangle the globals too, in case it uses a different set from what the parent function uses.
* FEATURE: add support for inlining functions with varargs/kwargs.
  Probably just run the function through ``partial_apply`` before inlining?
* BUG: how does marking methods as inlineable work? Need to check and probably raise an exception.


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


(change) tools/immutable
------------------------

There are immutable data structure libraries that may be faster, e.g.:

* https://github.com/zhemao/funktown
* https://pythonhosted.org/pysistence/

Alternatively, the embedded implementation can be optimized to reuse data instead of just making copies every time.

Also, we can change ``update()`` and ``del_()`` to ``with_()`` and ``without()`` which better reflect the immutability of data structures.
