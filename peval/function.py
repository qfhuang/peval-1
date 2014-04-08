import sys
import ast
import copy
import inspect
from types import FunctionType

import funcsigs
import astunparse

from peval.utils import unshift, get_fn_arg_id
from peval.symbol_finder import find_symbol_usages


def eval_function_def(function_def, globals_=None):
    """
    Evaluates an AST of a function definition with an optional dictionary of globals.
    Returns a callable function (a ``types.FunctionType`` object).
    """

    assert isinstance(function_def, ast.FunctionDef)

    # Should be done after deepcopy() (since it mutates `function_def`),
    # but it does not work in PyPy because of bug 1729.
    ast.fix_missing_locations(function_def)

    # Need to copy `function_def` because in PyPy `compile()` may mutate the tree
    # (see PyPy bug 1728).
    module = ast.Module(body=[copy.deepcopy(function_def)])

    code_object = compile(module, '<nofile>', 'exec')
    locals_ = {}
    eval(code_object, globals_, locals_)
    return locals_[function_def.name]


def eval_function_def_as_closure(function_def, closure_names, globals_=None):
    """
    Evaluates an AST of a function definition inside a closure with the variables
    from the list of ``closure_names`` set to ``None``,
    and an optional dictionary of globals.
    Returns a callable function (a ``types.FunctionType`` object).

    .. warning::

        Before the returned function can be actually called, the "fake" closure cells
        (filled with ``None``) must be substituted by actual closure cells
        that will be used during the call.
    """

    assert isinstance(function_def, ast.FunctionDef)

    if sys.version_info >= (3, 4):
        none = ast.NameConstant(value=None)
    else:
        none = ast.Name(id='None', ctx=ast.Load())

    # We can't possibly recreate ASTs of existing closure variables
    # (because all we have are their values).
    # So we create fake closure variables for the function to attach to,
    # and then substitute the closure cells with the ones obtained from
    # the "prototype" of this function (a ``types.FunctionType`` object
    # from which this tree was extracted).
    fake_closure_vars = [
        ast.Assign(
            targets=[ast.Name(id=name, ctx=ast.Store())],
            value=none)
        for name in closure_names]

    if sys.version_info < (3,):
        empty_args = ast.arguments(
            args=[],
            vararg=None,
            kwarg=None,
            defaults=[])
    else:
        empty_args = ast.arguments(
            args=[],
            vararg=None,
            kwonlyargs=[],
            kwarg=None,
            defaults=[],
            kw_defaults=[])

    wrapper_def = ast.FunctionDef(
        name='__peval_wrapper',
        args=empty_args,
        decorator_list=[],
        body=(
            fake_closure_vars +
            [function_def] +
            [ast.Return(value=ast.Name(id=function_def.name, ctx=ast.Load()))]))

    wrapper = eval_function_def(wrapper_def, globals_=globals_)
    return wrapper()


def get_closure(func):
    """
    Extracts names and values of closure variables from a function.
    Returns a tuple ``(names, cells)``, where ``names`` is a tuple of strings
    and ``cells`` is a tuple of ``Cell`` objects (containing the actual value
    in the attribute ``cell_contents``).
    """
    # Can't use OrderedDict here because we want to support Py2.6.
    freevars = func.__code__.co_freevars
    if hasattr(func, 'func_closure'):
        # For Py<=2.6 and PyPy2
        cells = func.func_closure
    else:
        cells = func.__closure__
    return freevars, cells


def filter_arglist(args, defaults, bound_argnames):
    """
    Filters a list of function argument nodes (``ast.Name`` in Py2, ``ast.arg`` in Py3)
    and corresponding defaults to exclude all arguments with the names
    present in ``bound_arguments``.
    Returns a pair of new arguments and defaults.
    """
    new_args = []
    new_defaults = []
    required_args = len(args) - len(defaults)
    for i, arg in enumerate(args):
        if get_fn_arg_id(arg) not in bound_argnames:
            new_args.append(arg)
            if i >= required_args:
                new_defaults.append(defaults[i - required_args])

    return new_args, new_defaults


def filter_arguments(arguments, bound_argnames):
    """
    Filters a node containing function arguments (an ``ast.arguments`` object)
    to exclude all arguments with the names present in ``bound_arguments``.
    Returns the new ``ast.arguments`` node.
    """

    assert isinstance(arguments, ast.arguments)

    new_params = dict(ast.iter_fields(arguments))

    new_params['args'], new_params['defaults'] = filter_arglist(
        arguments.args, arguments.defaults, bound_argnames)

    if sys.version_info >= (3,):
        new_params['kwonlyargs'], new_params['kw_defaults'] = filter_arglist(
            arguments.kwonlyargs, arguments.kw_defaults, bound_argnames)

    if sys.version_info < (3, 4):
        vararg_name = arguments.vararg
        kwarg_name = arguments.kwarg
    else:
        vararg_name = arguments.vararg.arg if arguments.vararg is not None else None
        kwarg_name = arguments.kwarg.arg if arguments.kwarg is not None else None

    if vararg_name is not None and vararg_name in bound_argnames:
        new_params['vararg'] = None
        if sys.version_info >= (3,) and sys.version_info < (3, 4):
            new_params['varargannotation'] = None

    if kwarg_name is not None and kwarg_name in bound_argnames:
        new_params['kwarg'] = None
        if sys.version_info >= (3,) and sys.version_info < (3, 4):
            new_params['kwargannotation'] = None

    return ast.arguments(**new_params)


def filter_function_def(function_def, bound_argnames):
    """
    Filters a node containing a function definition (an ``ast.FunctionDef`` object)
    to exclude all arguments with the names present in ``bound_arguments``.
    Returns the new ``ast.arguments`` node.
    """

    assert isinstance(function_def, ast.FunctionDef)

    new_args = filter_arguments(function_def.args, bound_argnames)

    params = dict(
        name=function_def.name,
        args=new_args,
        body=function_def.body,
        decorator_list=function_def.decorator_list)
    if sys.version_info >= (3,):
        params.update(dict(
            returns=function_def.returns))

    return ast.FunctionDef(**params)


class Function(object):
    """
    A wrapper for functions providing transformations to and from AST
    and simplifying operations with associated global and closure variables.
    """

    def __init__(self, tree, signature, globals_, closure_names, closure_cells):
        self.tree = tree
        self.globals = globals_
        self.closure_names = closure_names if closure_names is not None else tuple()
        self.closure_cells = closure_cells if closure_cells is not None else tuple()
        self.signature = signature

    def get_external_variables(self):
        """
        Returns a unified dictionary of external variables for this function
        (both globals and closure variables).
        """

        result = dict(self.globals)

        for name, val in zip(self.closure_names, self.closure_cells):
            result[name] = val.cell_contents

        return result

    @classmethod
    def from_object(cls, function):
        """
        Creates a ``Function`` object from an evaluated function.
        See :ref:`Known Limitations <known-limitations>` section for
        details about restrictions on the function.
        """

        if hasattr(function, '_peval_source'):
            # An attribute created in ``Function.eval()``
            src = getattr(function, '_peval_source')
        else:
            src = unshift(inspect.getsource(function))

        tree = ast.parse(src).body[0]

        signature = funcsigs.signature(function)
        globals_ = function.__globals__
        globals_[function.__name__] = function
        closure_names, closure_cells = get_closure(function)

        return cls(tree, signature, globals_, closure_names, closure_cells)

    def bind_partial(self, *args, **kwds):
        """
        Binds the provided positional and keyword arguments
        and returns a new ``Function`` object with an updated signature.
        """

        bargs = self.signature.bind_partial(*args, **kwds)

        # Remove the bound arguments from the function AST
        bound_argnames = set(bargs.arguments.keys())
        new_tree = filter_function_def(self.tree, bound_argnames)

        # Check for cases when the same symbol is used for an argument
        # being bound, and somewhere inside a decorator.
        # Since we are adding the bound argument to globals,
        # they will replace the value the decorator used, leading to errors.
        decorator_symbols = find_symbol_usages(self.tree.decorator_list)
        assert decorator_symbols.isdisjoint(bound_argnames)

        new_globals = dict(self.globals)
        new_globals.update(bargs.arguments)

        new_signature = self.signature.replace(parameters=[
            param for param in self.signature.parameters.values()
            if param.name not in bargs.arguments])

        return Function(
            new_tree, new_signature, new_globals, self.closure_names, self.closure_cells)

    def eval(self):
        """
        Evaluates and returns a callable function.
        """
        if len(self.closure_names) > 0:
            func_fake_closure = eval_function_def_as_closure(
                self.tree, self.closure_names, globals_=self.globals)

            func = FunctionType(
                func_fake_closure.__code__,
                self.globals,
                func_fake_closure.__name__,
                func_fake_closure.__defaults__,
                self.closure_cells)

            for attr in ('__kwdefaults__', '__annotations__'):
                if hasattr(func_fake_closure, attr):
                    setattr(func, attr, getattr(func_fake_closure, attr))
        else:
            func = eval_function_def(self.tree, globals_=self.globals)

        # A regular function contains a file name and a line number
        # pointing to the location of its source.
        # I we wanted to trick ``inspect.getsource()`` into working with
        # this newly generated function, we could create a temporary file and write it there.
        # But it leads to other complications, and is unnecessary at this stage.
        # So we just save the source into an attribute for ``Function.from_object()``
        # to discover if we ever want to create a new ``Function`` object
        # out of this function.
        vars(func)['_peval_source'] = astunparse.unparse(self.tree)

        return func

    def replace(self, tree=None, globals_=None):
        """
        Replaces the AST and/or globals and returns a new ``Function`` object.
        If some closure variables are not used by a new tree,
        adjusts the closure cells accordingly.
        """
        if tree is None:
            tree = self.tree
        if globals_ is None:
            globals_ = self.globals

        if len(self.closure_cells) > 0:
            func_fake_closure = eval_function_def_as_closure(
                tree, self.closure_names, globals_=globals_)

            new_closure_names, _ = get_closure(func_fake_closure)
            closure_dict = dict(zip(self.closure_names, self.closure_cells))
            new_closure_cells = tuple(closure_dict[name] for name in new_closure_names)
        else:
            new_closure_names = self.closure_names
            new_closure_cells = self.closure_cells

        return Function(tree, self.signature, globals_, new_closure_names, new_closure_cells)
