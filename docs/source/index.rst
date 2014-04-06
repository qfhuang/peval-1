*********************************
Partial evaluation of Python code
*********************************

Under construction.


Known limitations
=================

In the process of partial evaluation, the target function needs to be discovered in the source code, parsed, optimized and re-evaluated by the interpreter.
Due to the way the discovery of function code and metadata is implemented in Python, in some scenarios ``peval`` may lack necessary information and therefore fail to restore the function correctly.
Fortunately, these scenarios are not very common, but one still needs to be aware of them.


Decorators
----------

* **Problem:** If the target function is decorated, the decorators must preserve the function metadata, in particular, closure variables, globals, and reference to the source file where it was defined.

  **Workaround:** One must either take care of the metadata manually, or use a metadata-aware decorator builder library like `wrapt <https://pypi.python.org/pypi/wrapt>`_.

* **Problem:** Consider a function decorated inside another function:

  ::

      def outer():
          arg1 = 1
          arg2 = 2

          @decorator(arg1, arg2)
          def innner():
              # code_here

          return inner

  The variables used in the decorator declaration (``arg1``, ``arg2``) are not included neither in globals nor in closure variables of ``inner``.
  When the returned ``inner`` function is partially evaluated, it is not possible to restore the values of ``arg1`` and ``arg2``, and the final evaluation will fail.

  **Workaround:** Make sure all the variables used in the decorator declarations for target functions (including the decorators themselves) belong to the global namespace.

* **Problem:** When the target function is re-evaluated, the decorators associated with it are applied to the new function.
  This may lead to unexpected behavior if the decorators have side effects, or rely on some particular function arguments (which may disappear after partial application).

  **Workaround:** Make sure that the second application of the decorators does not lead to undesired consequences, and that they can handle changes in the function signature.


********
Contents
********

.. toctree::
   :maxdepth: 2



