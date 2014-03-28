* BUG (mangler): a function is inlined by replacing it with a ``while True`` loop and using variable assignment and ``break`` instead of ``return``.
  But if the ``return`` is inside another loop, this will lead to unexpected behavior.
* BUG (optimizer): ``find_symbol_creations()`` must include nested ``FunctionDef`` in the list (since they introduce new symbols, just as stores).
  But in ``Optimizer._inlined_fn()`` the whole outer function definition is passed to the mangler.
  As a result, it include the outer function name in the to-mangle list and mangles all its recursive calls, preventing the inliner from recognizing and inlining them.
* BUG (optimizer): ``find_symbol_creations()`` must include symbols created by ``except Exception as e`` in the list.
  In Python3 ``e`` is just a plain string, so it is not caught by the current algorithm looking for ``ast.Store`` constructors.
