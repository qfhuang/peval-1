General
-------

* Add exports from ``core`` and ``components`` submodules to their ``__init__``'s.
* Replace ``isinstance`` with ``type(x) == y`` where possible.
* Check identity in ``replace_fields()`` and return the old node if all the replaced values are the same objects as the old ones.


core/symbol_finder
------------------

* ?BUG: ``find_symbol_usages()`` must include other ways of using a symbol (if there are any).
* BUG: ``find_symbol_creations()`` must include nested ``FunctionDef`` in the list (since they introduce new symbols, just as stores).
  But in ``Optimizer._inlined_fn()`` the whole outer function definition is passed to the mangler.
  As a result, it include the outer function name in the to-mangle list and mangles all its recursive calls, preventing the inliner from recognizing and inlining them.
* BUG: ``find_symbol_creations()`` must include symbols created by ``except Exception as e`` in the list.
  In Python3 ``e`` is just a plain string, so it is not caught by the current algorithm looking for ``ast.Store`` constructors.


core/function
-------------

* BUG: preserve __future__ imports when re-evaluating functions.
* BUG: builtins are located in a separate scope (``globals()['__builtins__']``) and currently cannot be resolved.
* BUG: when binding parameters, do not add them to globals, but instead put the assignments at the start of the function.
  This will result in a more correct behavior.


core/expression
---------------

* BUG: prior to Py3.4 ``None``, ``False`` and ``True`` are redefinable bindings.
  We need to keep it in mind in ``wrap_in_ast()`` and probably create a new binding instead of just returning an ``ast.Name``.


components/evaluate
-------------------

* BUG: if an expression is passed as an argument to a function (e.g. ``f(c * 2)``), one of the arguments of this expression can still be passed through and then mutated by ``f()``.
  This case must be handled somehow.
  Similarly, a method call can mutate a variable passed to the object earlier, for example ``Foo(x).transform()``, where ``x`` is a list.
  But this only applies to "bad" objects, because not taking a copy of a mutable argument and then mutate it silently is really error-prone.
* ?BUG: do we need to check for builtin redefinitions?
* ?BUG: ``_mark_mutated_node()`` needs to somehow propagate that information up the data flow graph.
* FEATURE: in ``handle_BinOp()``, we can apply binary operations to all objects that support them, not only to NUMBER_TYPES.
* ?FEATURE: base optimizations on the data flow graph, not on AST --- it is a higher level abstraction and has less details insignificant for the optimizer.
* FEATURE: add partial application for varargs and kwargs (see ``assert`` in ``_fn_result_node_if_safe()``).
* FEATURE: add support for varargs and kwargs in ``handle_Call()`` (see ``assert`` there)
* ?FEATURE: in ``handle_Compare()``, we may be able to evaluate the result if only some of the arguments are known.


components/prune_cfg
--------------------

* FEATURE: we can detect unconditional jumps in ``for`` loops as well, but in order to remove the loop, we need the loop unrolling functionality.
* BUG: evaluating ``bool(node.test)`` is potentially (albeint unlikely) unsafe (if it is some weird object with a weird ``__bool__()`` implementation).


components/inline
-----------------

* BUG: when inlining a function, we must mangle the globals too, in case it uses a different set from what the parent function uses.
* FEATURE: add support for inlining functions with varargs/kwargs (see ``assert`` in ``Optimizer._inlined_fn()``).
* FEATURE: if an argument is "simple" - literal or name, and is never assigned in the body of the inlined function, then do not make an assignment, just use it as is.
* FEATURE: need to check how argument mutations inside the inlined function are handled.
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
