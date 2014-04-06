import sys
import ast
import inspect
from types import FunctionType

import funcsigs
import astunparse

from peval.utils import unshift


def eval_function_def(function_def, globals_=None):

    assert isinstance(function_def, ast.FunctionDef)

    module = ast.Module(body=[function_def])
    ast.fix_missing_locations(module)
    code_object = compile(module, '<nofile>', 'exec')
    locals_ = {}
    eval(code_object, globals_, locals_)
    return locals_[function_def.name]


def eval_function_def_as_closure(function_def, closure_names, globals_=None):

    if sys.version_info >= (3, 4):
        none = ast.NameConstant(value=None)
    else:
        none = ast.Name(id='None', ctx=ast.Load())

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

    fake_closure_vars = [
        ast.Assign(
            targets=[ast.Name(id=name, ctx=ast.Store())],
            value=none)
        for name in closure_names]

    wrapper = ast.FunctionDef(
        name='__wrapper',
        args=empty_args,
        decorator_list=[],
        body=(
            fake_closure_vars +
            [function_def] +
            [ast.Return(value=ast.Name(id=function_def.name, ctx=ast.Load()))]))

    wrapper = eval_function_def(wrapper, globals_=globals_)
    return wrapper()


def get_closure(func):
    freevars = func.__code__.co_freevars
    if hasattr(func, 'func_closure'):
        # For Py<=2.6 and PyPy2
        cells = func.func_closure
    else:
        cells = func.__closure__
    return freevars, cells


def filter_arglist(args, defaults, bound_argnames):

    get_arg_name = lambda arg: arg.id if sys.version_info < (3,) else arg.arg

    new_args = []
    new_defaults = []
    required_args = len(args) - len(defaults)
    for i, arg in enumerate(args):
        if get_arg_name(arg) not in bound_argnames:
            new_args.append(arg)
            if i >= required_args:
                new_defaults.append(defaults[i - required_args])

    return new_args, new_defaults


def filter_arguments(node, bound_argnames):

    assert isinstance(node, ast.arguments)

    new_params = dict(ast.iter_fields(node))

    new_params['args'], new_params['defaults'] = filter_arglist(
        node.args, node.defaults, bound_argnames)

    if sys.version_info >= (3,):
        new_params['kwonlyargs'], new_params['kw_defaults'] = filter_arglist(
            node.kwonlyargs, node.kw_defaults, bound_argnames)

    if sys.version_info < (3, 4):
        vararg_name = node.vararg
        kwarg_name = node.kwarg
    else:
        vararg_name = node.vararg.arg if node.vararg is not None else None
        kwarg_name = node.kwarg.arg if node.kwarg is not None else None

    if vararg_name is not None and vararg_name in bound_argnames:
        new_params['vararg'] = None
        if sys.version_info < (3, 4):
            new_params['varargannotation'] = None

    if kwarg_name is not None and kwarg_name in bound_argnames:
        new_params['kwarg'] = None
        if sys.version_info < (3, 4):
            new_params['kwargannotation'] = None

    return ast.arguments(**new_params)


def filter_function_def(node, bound_argnames):

    assert isinstance(node, ast.FunctionDef)

    # DOC: potential problem when the same symbol is used for an argument and for a decorator.
    # Since we are adding the fixed argument to globals, it will replace the value
    # of the decorator leading to errors.
    # On the other hand, this situation should be really rare since it's a bad coding style
    # (and easily noticeable).
    # We can just assert it.

    # names = find_loads(node.decorators)
    # assert not names.intersects(argnames)

    new_args = filter_arguments(node.args, bound_argnames)

    params = dict(
        name=node.name,
        args=new_args,
        body=node.body,
        decorator_list=node.decorator_list)
    if sys.version_info >= (3,):
        params.update(dict(
            returns=node.returns))

    return ast.FunctionDef(**params)


class Function:

    def __init__(self, tree, signature, globals_, closure_names, closure_cells):
        self.tree = tree
        self.globals = globals_
        self.closure_names = closure_names if closure_names is not None else tuple()
        self.closure_cells = closure_cells if closure_cells is not None else tuple()
        self.signature = signature

    @classmethod
    def from_object(cls, function):
        # DOC: Assuming here, that even if a decorator was applied to the function,
        # it is a "good" metadata-preserving decorator, e.g. created by ``wrapt``.
        if hasattr(function, '_peval_source'):
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
        bargs = self.signature.bind_partial(*args, **kwds)

        new_tree = filter_function_def(self.tree, set(bargs.arguments.keys()))

        new_globals = dict(self.globals)
        new_globals.update(bargs.arguments)

        new_signature = self.signature.replace(parameters=[
            param for param in self.signature.parameters.values()
            if param.name not in bargs.arguments])

        return Function(
            new_tree, new_signature, new_globals, self.closure_names, self.closure_cells)

    def eval(self):
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

            for attr in vars(func_fake_closure):
                if not hasattr(func, attr):
                    setattr(func, attr, getattr(func_fake_closure, attr))
        else:
            func = eval_function_def(self.tree, globals_=self.globals)

        vars(func)['_peval_source'] = astunparse.unparse(self.tree)

        return func

    def replace(self, tree=None, globals_=None):
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
