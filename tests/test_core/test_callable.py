import types
import sys

from peval.core.callable import inspect_callable, Callable


def get_method_function(unbound_method):
    """
    Extracts a regular function object from an unbound method.
    """
    if sys.version_info >= (3,):
        return unbound_method
    else:
        # In Py2, `mystr2.__getitem__` is an unbound method,
        # which is a wrapper on top of a function, checking the type of its first argument.
        return unbound_method.__func__


def get_builtin_method_function(unbound_builtin_method):
    """
    In PyPy, naturally, builtin methods are regular methods.
    Since we can't (and/or don't want to) check for the Python implementation type,
    we check whether it is the case instead.
    """
    if type(unbound_builtin_method) == types.MethodType:
        return get_method_function(unbound_builtin_method)
    else:
        return unbound_builtin_method


def test_builtin_function():
    assert inspect_callable(isinstance) == Callable(isinstance)

def test_builtin_constructor():
    assert inspect_callable(str) == Callable(str, init=True)

def test_builtin_unbound_method():
    ref_func = get_builtin_method_function(str.__getitem__)
    assert inspect_callable(str.__getitem__) == Callable(ref_func)

def test_builtin_bound_method():
    ref_func = get_builtin_method_function(str.__getitem__)
    assert inspect_callable("a".__getitem__) == Callable(ref_func, self_obj="a")


class mystr1(str):
    pass


class mystr2(str):
    def __getitem__(self, idx):
        return str.__getitem__(self, idx)


def test_builtin_method_in_derived():
    s1 = mystr1("a")
    ref_func = get_builtin_method_function(str.__getitem__)
    assert (inspect_callable(s1.__getitem__) == Callable(ref_func, self_obj=s1))

def test_builtin_method_overloaded_in_derived():
    s2 = mystr2("a")
    ref_func = get_method_function(mystr2.__getitem__)
    assert (inspect_callable(s2.__getitem__) == Callable(ref_func, self_obj=s2))


def dummy():
    pass


class OldStyleDummyInit:

    def __init__(self):
        pass


class OldStyleDummy:

    def __call__(self):
        pass

    def method(self):
        pass

    @classmethod
    def classmethod(cls):
        pass

    @staticmethod
    def staticmethod():
        pass


class OldStyleDerivedDummy(OldStyleDummy):
    pass


class NewStyleDummy(object):

    def __call__(self):
        pass

    def method(self):
        pass

    @classmethod
    def classmethod(cls):
        pass

    @staticmethod
    def staticmethod():
        pass


class NewStyleDerivedDummy(NewStyleDummy):
    pass


def pytest_generate_tests(metafunc):
    if 'cls' in metafunc.funcargnames:
        clss = [{'base': NewStyleDummy, 'derived': NewStyleDerivedDummy}]
        ids = ['new style']

        if sys.version_info < (3,):
            clss.append({'base': OldStyleDummy, 'derived': OldStyleDerivedDummy})
            ids.append('old style')

        metafunc.parametrize('cls', clss, ids=ids)


def test_function():
    assert inspect_callable(dummy) == Callable(dummy)

def test_constructor(cls):
    assert inspect_callable(cls['base']) == Callable(cls['base'], init=True)

def test_unbound_method(cls):
    ref_func = get_method_function(cls['base'].method)
    assert inspect_callable(cls['base'].method) == Callable(ref_func)

def test_bound_method(cls):
    d = cls['base']()
    ref_func = get_method_function(cls['base'].method)
    assert inspect_callable(d.method) == Callable(ref_func, self_obj=d)

def test_bound_method_in_derived(cls):
    d = cls['derived']()
    ref_func = get_method_function(cls['base'].method)
    assert inspect_callable(d.method) == Callable(ref_func, self_obj=d)

def test_call_method(cls):
    d = cls['base']()
    ref_func = get_method_function(cls['base'].__call__)
    assert inspect_callable(d) == Callable(ref_func, self_obj=d)

def test_static_method(cls):
    d = cls['base']()
    assert inspect_callable(d.staticmethod) == Callable(cls['base'].staticmethod)

def test_class_method(cls):
    d = cls['base']()
    classmethod_func = cls['base'].classmethod.__func__
    assert inspect_callable(d.classmethod) == Callable(classmethod_func, self_obj=cls['base'])

def test_class_method_in_derived(cls):
    d = cls['derived']()
    classmethod_func = cls['base'].classmethod.__func__
    assert inspect_callable(d.classmethod) == Callable(classmethod_func, self_obj=cls['derived'])
