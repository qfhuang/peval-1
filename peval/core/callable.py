import types
import sys


WrapperDescriptorType = type(str.__getitem__)
MethodWrapperType = type("a".__getitem__)


class Callable:

    # Type of calls:
    # - function
    # - type + __init__
    # - type + normal method (same as function)
    # - type + static method
    # - type + class method
    # - object + method

    def __init__(self, func_obj, self_obj=None, init=False):
        self.func_obj = func_obj
        self.self_obj = self_obj
        self.init = init

    def __eq__(self, other):
        return (self.func_obj is other.func_obj
            and self.self_obj is other.self_obj
            and self.init == other.init)


def inspect_callable(obj):

    if type(obj) in (types.FunctionType, types.BuiltinFunctionType):
        return Callable(obj)

    if type(obj) == type or (sys.version_info < (3,) and type(obj) == types.ClassType):
        return Callable(obj, init=True)

    if type(obj) == types.MethodType:
        if sys.version_info > (3,):
            return Callable(obj.__func__, self_obj=obj.__self__)
        else:
            return Callable(obj.im_func, self_obj=obj.im_self)

    if type(obj) == MethodWrapperType:
        return Callable(
            getattr(obj.__objclass__, obj.__name__),
            self_obj=obj.__self__)

    if type(obj) == WrapperDescriptorType:
        return Callable(obj)

    if hasattr(obj, '__call__'):
        return inspect_callable(obj.__call__)

    raise AttributeError
