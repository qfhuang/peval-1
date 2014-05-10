core/walker
-----------

* FEATURE: provide arguments to a callback based on it signature (same as ``py.test`` does), instead of extracting them from ``**kwds``.
* ?FEATURE: redesign ``state`` and ``ctx`` passing. Can we join them?
* ?BUG: are ``body`` and ``orelse`` the only fields that can contain a list of statements?
* ?BUG: if we are saving an empty list to a ``body`` field, need to replace it with a single ``Pass``.


core/symbol_finder
------------------

* ?BUG: ``find_symbol_usages()`` must include other ways of using a symbol (if
there are any).
* BUG: ``find_symbol_creations()`` must include nested ``FunctionDef`` in the list (since they introduce new symbols, just as stores).
  But in ``Optimizer._inlined_fn()`` the whole outer function definition is passed to the mangler.
  As a result, it include the outer function name in the to-mangle list and mangles all its recursive calls, preventing the inliner from recognizing and inlining them.
* BUG: ``find_symbol_creations()`` must include symbols created by ``except Exception as e`` in the list.
  In Python3 ``e`` is just a plain string, so it is not caught by the current algorithm looking for ``ast.Store`` constructors.


core/function
-------------

* BUG (function): preserve __future__ imports when re-evaluating functions.
* BUG (function): when PyPy bug 1729 is fixed, in ``eval_function_def`` deepcopy ``function_def`` before ``ast.fix_missing_locations``.


core/mangler
------------

* BUG (mangler): a function is inlined by replacing it with a ``while True`` loop and using variable assignment and ``break`` instead of ``return``.
  But if the ``return`` is inside another loop, this will lead to unexpected behavior.



* ?BUG: are there other attributes in AST that contain blocks, in addition to ``body`` and ``orelse``? If yes, ``block_fields`` in ``Optimizer.generic_visit()`` must be extended.
* BUG (optimizer): in ``Optimizer.visit_Call()``, if an expression is passed as an argument to a function (e.g. ``f(c * 2)``), one of the arguments of this expression can still be passed through and then mutated by ``f()``.
  This case must be handled somehow.
  Similarly, a method call can mutate a variable passed to the object earlier, for example ``Foo(x).transform()``, where ``x`` is a list.
  But this only applies to "bad" objects, because not taking a copy of a mutable argument and then mutate it silently is really error-prone.
* ?BUG (optimizer): do we need to check for builtin redefinitions?
* ?BUG (optimizer): ``Optimizer._mark_mutated_node()`` needs to somehow propagated that information up the data flow graph.
* BUG (inline): when inlining a function, we must mangle the globals too, in case it uses a different set from what the parent function uses.

* FEATURE (optimizer): in ``Optimizer.visit_BinOp``, we can apply binary operations to all objects that support them, not only to NUMBER_TYPES.
* ?FEATURE (optimizer): base optimizations on the data flow graph, not on AST --- it is a higher level abstraction and has less details insignificant for the optimizer.
* FEATURE: add partial application for varargs and kwargs (see ``assert`` in ``Optimizer._fn_result_node_if_safe()``).
* FEATURE: in ``test_optimizer/test_inlining_1``, we can eliminate the ``n`` argument to the function, since it has been applied.
* FEATURE: Make the library make all the bookkeeping for you, creating specialized versions and using them as needed by the following decorator

  ::

      @peval.specialize_on('n', globals(), locals())
      def power(x, n):
          ...

  But in this case the arguments we specialize on must be hashable. It they
  are not, you will have to dispatch to specialized function yourself.
* FEATURE: add loop unrolling functionality to the optimizer
* FEATURE (optimizer): add support for varargs and kwargs in ``Optimizer.visit_Call()`` (see ``assert`` there)
* ?FEATURE (optimizer): in ``Optimizer.visit_Compare()``, we may be able to evaluate the result if only some of the arguments are known.
* FEATURE (optimizer): add support for inlining functions with varargs/kwargs (see ``assert`` in ``Optimizer._inlined_fn()``).
* FEATURE (optimizer): in ``Optimizer._inlined_fn()``, if an argument is "simple" - literal or name, and is never assigned in the body of the inlined function, then do not make an assignment, just use it as is.
* FEATURE (optimizer): in ``Optimizer._inlined_fn()``, need to check how argument mutations inside the inlined function are handled.
