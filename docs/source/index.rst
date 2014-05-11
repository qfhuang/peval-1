*********************************
Partial evaluation of Python code
*********************************

This library allows one to perform code specialization at run-time, turning this::

    @inline
    def power(x, n):
        if n == 0:
            return 1
        elif n % 2 == 0:
            v = power(x, n // 2)
            return v * v
        else:
            return x * power(x, n - 1)

with ``n`` set to, say, 27, into this::

    def power_27(x):
        _pow_2 = x * x
        _pow_3 = _pow_2 * x
        _pow_6 = _pow_3 * _pow_3
        _pow_12 = _pow_6 * _pow_6
        _pow_13 = _pow_12 * x
        _pow_26 = _pow_13 * _pow_13
        _pow_27 = _pow_26 * x
        return _pow_27

(variable names are truncated for readability).
The resulting code runs 10 times faster under CPython.

Generaly, partial evaluation is beneficial if inputs of some function (or a set of functions, or methods) can be decomposed into *static* (seldom changing) and *dynamic*.
Then we create a specialied version of the algorithm for each encoutered static input, and use it to process the dynamic input.
For example, for an interpreter *static input* is the program, and *dynamic input* is the input to that program.
Partial evaluation thus turns this interpreter into an executable, which runs much faster (this is the so called first Futamura projection).

The API is identical to that of ``functools.partial()``::

    import peval
    power_27 = peval.partial_apply(power, n=27)

You must mark the functions that you want inlined (maybe recursively) with ``peval.decorators.inline``.
If some function or method operates on your static input, you can benefit from marking it as pure
using ``peval.decorators.pure_fn`` (if it is really pure).

Under the hood the library simplifies AST by performing common compiler optimizations, using known variable values:

* constant propagation
* constant folding
* dead-code elimination
* function inlining

... and so on.

But here this optimizations can really make a difference, because your function can heavily depend on a known input, and therefore the specialized function might have quite different control flow,
as in the ``power(x, n)`` example.

Variable mutation and assigment is handled gracefully (in simple cases where no direct namespace manipulation is involved).


Tests
=====

Run the test suite with `PyTest <http://pytest.org/latest/>`_::

    py.test

Run a specific test or test group with::

    py.test -k "test_core"


.. _known-limitations:

Known limitations
=================

In the process of partial evaluation, the target function needs to be discovered in the source code, parsed, optimized and re-evaluated by the interpreter.
Due to the way the discovery of function code and metadata is implemented in Python, in some scenarios ``peval`` may lack necessary information and therefore fail to restore the function correctly.
Fortunately, these scenarios are not very common, but one still needs to be aware of them.

And, of course, there is a whole group of problems arising due to the highly dynamical nature of Python.


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

* **Problem:** Consider a case when a decorator uses the same symbol as one of the function arguments:

  ::

      @foo
      def test(foo, bar):
          return foo, bar

  If we bind the ``foo`` argument to some value, this value will be added to the globals and, therefore, will replace the value used for the ``foo`` decorator.
  Consequently, the evaluation of such partially applied function will fail
  (in fact, an assertion within ``Function.bind_partial()`` will fire before that).

  **Workaround:** Avoid using the same symbols in function argument lists and in the decorator declarations applied to these functions (which is usually a good general coding practice).


Mutation and variable assigment
-------------------------------

There are several cases when initially known variable can be changed,
and we can no longer assume it is known.

Variable assigment::

    @specialize_on('n')
    def fn(n, x):
        n += x  # here n is no longer known

Variable mutation (is ``some_method`` is not declared as pure_fn, we can not
assume that it does not mutate ``foo``)::

    @specialize_on('foo')
    def fn(foo, x):
        foo.some_method()

It can become more complex if other variables are envolved::

    @specialize_on('foo')
    def fn(foo, x):
        a = foo.some_pure_method()
        a.some_method()

Here not only we can not assume ``a`` to be constant, but the call to
``some_method`` could have mutated ``a``, that can hold a reference to
``foo`` or some part of it, so that mutating ``a`` changes ``foo`` too.

Another case that needs to be handled is variable escaping from
the function via return statement (usually indirectly)::


    @specialize_on('foo')
    def fn(foo, x):
        a = foo.some_pure_method()
        return a

Here we have no garanty that ``a`` wont be mutated by the called of ``fn``,
so we can not compute ``foo.some_pure_method()`` once - we need a fresh
copy every time ``fn`` is called to preserve semantics.

To handle it in a sane way:

* we need to know the data flow inside the function - how variables
  depend on each other
* we need to know which variables might be mutated, and propagete this
  information up the data flow
* we need to do the same for variables that leave the function
* we need to know which variables are rebound via assigment, and mark them
  as not being constant


********
Contents
********

.. toctree::
   :maxdepth: 2



