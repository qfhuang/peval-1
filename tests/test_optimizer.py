from __future__ import print_function, division

import ast
import sys

import six

from peval.utils import unshift
from peval.optimizer import optimized_ast
from peval.decorators import pure_function, inline
from peval.function import Function

from .utils import assert_ast_equal, ast_to_string, ast_to_source


def check_opt(source, constants, expected_source=None, expected_new_bindings=None):
    ''' Test that with given constants, optimized_ast transforms
    source to expected_source.
    It :expected_new_bindings: is given, we check that they
    are among new bindings returned by optimizer.
    '''
    source = unshift(source)

    if expected_source is None:
        expected_source = source
    else:
        expected_source = unshift(expected_source)

    ast_tree = ast.parse(source)
    new_ast, bindings = optimized_ast(ast_tree, constants)
    assert_ast_equal(new_ast, ast.parse(expected_source))
    if expected_new_bindings:
        for k in expected_new_bindings:
            if k not in bindings:
                print('bindings:', bindings)

            binding = bindings[k]
            expected_binding = expected_new_bindings[k]

            # Python 3.2 defines equality for range objects incorrectly
            # (namely, the result is always False).
            # So we just test it manually.
            if (sys.version_info[0] == 3 and sys.version_info[1] <= 2 and
                    isinstance(expected_binding, range)):
                assert type(binding) == type(expected_binding)
                assert list(binding) == list(expected_binding)
            else:
                assert binding == expected_binding


def test_propagation_int():
    check_opt(
        'a * n + (m - 2) * (n + 1)', dict(n=5),
        'a * 5 + (m - 2) * 6')

def test_propagation_float():
    check_opt(
        'a * n + (m - 2) * (n + 1)', dict(n=5.0),
        'a * 5.0 + (m - 2) * 6.0')

def test_propagation_str():
    check_opt(
        'foo[:5]', dict(foo="bar"),
        '"bar"[:5]')

def test_propagation_named_constant():
    check_opt(
        'foo', dict(foo=False),
        'False')
    check_opt(
        'foo', dict(foo=True),
        'True')
    check_opt(
        'foo', dict(foo=None),
        'None')

def test_propagation_subclass():
    ''' Test that constant propogation does not happen on primitive
    subclasses
    '''
    class Int(int): pass
    check_opt(
        'm * n', dict(m=Int(2)),
        'm * n')
    check_opt(
        'm * n', dict(m=Int(2), n=3),
        'm * 3')

    class Float(float): pass
    check_opt(
        'm * n', dict(m=Float(2.0)),
        'm * n')

    class Text(six.text_type): pass
    check_opt(
        'm + n', dict(m=Text(six.u('foo'))),
        'm + n')

    class Binary(six.binary_type): pass
    check_opt(
        'm + n', dict(m=Binary(six.b('foo'))),
        'm + n')


def test_if_true_elimination():
    ''' Eliminate if test, if the value is known at compile time
    '''
    true_values = [True, 1, 2.0, object(), "foo", int]
    assert all(true_values)

    for x in true_values:
        check_opt(
            'if x: print("x is True")', dict(x=x),
            'print("x is True")')

    check_opt('''
        if x:
            do_stuff()
        else:
            do_other_stuff()
        ''',
        dict(x=2),
        'do_stuff()')


def test_if_no_elimination():
    ''' Test that there is no unneeded elimination of if test
    '''
    check_opt('''
        if x:
            do_stuff()
        else:
            do_other_stuff()
        ''',
        dict(y=2),
        '''
        if x:
            do_stuff()
        else:
            do_other_stuff()
        ''')


def test_if_false_elimination():
    ''' Eliminate if test, when test is false
    '''
    class Falsy(object):
        def __nonzero__(self):
            # For Python 2
            return False
        def __bool__(self):
            # For Python 3
            return False
    false_values = [0, '', [], {}, set(), False, None, Falsy()]

    for x in false_values:
        check_opt('''
            if x:
                do_stuff()
            else:
                do_other_stuff()
                if True:
                    do_someother_stuff()
                    and_more_stuff()
            ''',
            dict(x=x),
            '''
            do_other_stuff()
            do_someother_stuff()
            and_more_stuff()
            ''')


def test_if_empty_elimination():
    ''' Eliminate if completly, when corresponding clause is empty
    '''
    check_opt('if x: do_stuff()', dict(x=False), 'pass')
    check_opt('''
            if x:
                pass
            else:
                do_stuff()
            ''',
            dict(x=object()),
            'pass')


def test_if_visit_only_true_branch():
    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_opt('if a: inc()', dict(a=False, inc=inc), 'pass')
    assert global_state['cnt'] == 0

    check_opt('''
            if a:
                dec()
            else:
                inc()
            ''', dict(a=False, inc=inc), 'True')
    assert global_state['cnt'] == 1


def test_visit_all_branches():
    check_opt('''
            if x > 0:
                if True:
                    x += 1
            else:
                if False:
                    return 0
            ''',
            dict(),
            '''
            if x > 0:
                x += 1
            else:
                pass
            ''')


def test_call_no_args():
    @pure_function
    def fn():
        return 'Hi!'
    check_opt('x = fn()', dict(fn=fn), 'x = "Hi!"')


def test_call_with_args():
    @pure_function
    def fn(x, y):
        return x + [y]
    check_opt('z = fn(x, y)', dict(fn=fn, x=10), 'z = fn(10, y)')
    check_opt(
            'z = fn(x, y)',
            dict(fn=fn, x=[10], y=20.0),
            'z = __binding_1',
            dict(__binding_1=[10, 20.0]))


def test_exception():
    ''' Test when called function raises an exception -
    we want it to raise it in specialized function
    '''
    @pure_function
    def fn():
        return 1 / 0
    check_opt('x = fn()', dict(fn=fn), 'x = fn()')


def test_evaluate_builtins():
    ''' Test that we can evaluate builtins
    '''
    check_opt('isinstance(n, int)', dict(n=10), 'True')


def test_not():
    check_opt('not x', dict(x="s"), 'False')
    check_opt('not x', dict(x=0), 'True')
    check_opt('not 1', dict(), 'False')
    check_opt('not False', dict(), 'True')


def test_and():
    check_opt('a and b', dict(a=False), 'False')
    check_opt('a and b', dict(a=True), 'b')
    check_opt(
        'a and b()', dict(a=True, b=pure_function(lambda: True)),
        'True')
    check_opt(
        'a and b and c and d', dict(a=True, c=True),
        'b and d')

def test_and_short_circuit():
    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_opt('a and inc()', dict(a=False, inc=inc), 'False')
    assert global_state['cnt'] == 0

    check_opt('a and inc()', dict(a=True, inc=inc), 'True')
    assert global_state['cnt'] == 1


def test_or():
    check_opt('a or b', dict(a=False), 'b')
    check_opt('a or b', dict(a=True), 'True')
    check_opt('a or b', dict(a=False, b=False), 'False')
    check_opt(
            'a or b()', dict(a=False, b=pure_function(lambda: True)),
            'True')
    check_opt('a or b or c or d', dict(a=False, c=False), 'b or d')


def test_or_short_circuit():
    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    check_opt('a or inc()', dict(a=True, inc=inc), 'True')
    assert global_state['cnt'] == 0

    check_opt('a or inc()', dict(a=False, inc=inc), 'True')
    assert global_state['cnt'] == 1


def test_mix():
    check_opt(
        '''
        if not isinstance(n, int) or n < 0:
            foo()
        else:
            bar()
        ''',
        dict(n=0),
        'bar()')


def test_eq():
    check_opt('0 == 0', {}, 'True')
    check_opt('0 == 1', {}, 'False')
    check_opt('a == b', dict(a=1), '1 == b')
    check_opt('a == b', dict(b=1), 'a == 1')
    check_opt('a == b', dict(a=1, b=1), 'True')
    check_opt('a == b', dict(a=2, b=1), 'False')
    check_opt(
            'a == b == c == d', dict(a=2, c=2),
            '2 == b == 2 == d')


def test_mix():
    check_opt('a < b >= c', dict(a=0, b=1, c=1), 'True')
    check_opt('a <= b > c', dict(a=0, b=1, c=1), 'False')


def test_remove_pass():
    check_opt(
        '''
        def fn(x):
            x += 1
            pass
            return x
        ''',
        dict(),
        '''
        def fn(x):
            x += 1
            return x
        ''')


def test_remove_pass_if():
    check_opt(
        '''
        if x > 0:
            x += 1
            pass
        ''',
        dict(),
        '''
        if x > 0:
            x += 1
        ''')


def test_not_remove_pass():
    check_opt(
        '''
        if x > 0:
            pass
        ''',
        dict(),
        '''
        if x > 0:
            pass
        ''')


def test_remove_after_return():
    check_opt(
        '''
        def fn(x):
            x += 1
            return x
            x += 1
        ''',
        dict(),
        '''
        def fn(x):
            x += 1
            return x
        ''')


def test_remove_after_return_if():
    check_opt(
        '''
        if x > 0:
            x += 1
            return x
            x += 1
        ''',
        dict(),
        '''
        if x > 0:
            x += 1
            return x
        ''')


def test_if_on_stupid_power():
    source = '''
        def fn(x, n):
            if not isinstance(n, int) or n < 0:
                raise ValueError('Base should be a positive integer')
            else:
                if n == 0:
                    return 1
                if n == 1:
                    return x
                v = 1
                for _ in range(n):
                    v *= x
                return v
        '''
    check_opt(
        source, dict(n='foo'),
        '''
        def fn(x, n):
            raise ValueError('Base should be a positive integer')
        ''')
    check_opt(
        source, dict(n=0),
        '''
        def fn(x, n):
            return 1
        ''')
    check_opt(
        source, dict(n=1),
        '''
        def fn(x, n):
            return x
        ''')
    check_opt(
        source, dict(n=2),
        '''
        def fn(x, n):
            v = 1
            for _ in __binding_1:
                v *= x
            return v
        ''',
        dict(__binding_1=range(2)))


# Test that nodes whose values are known first but are mutated later
# are not substituted with values calculated at compile time.

def test_self_mutation_via_method():
    check_opt(
        '''
        if x:
            bar()
        ''',
        dict(x=object()),
        'bar()')
    check_opt(
        '''
        x.foo()
        if x:
            bar()
        ''',
        dict(x=object()))


def test_mutation_of_fn_args():
    check_opt(
        '''
        if x:
            bar()
        ''',
        dict(x=object()),
        'bar()')
    check_opt(
        '''
        foo(x)
        if x:
            bar()
        ''',
        dict(x=object()))


def test_arithmetic():
    check_opt('1 + 1', {}, '2')
    check_opt('1 + (1 * 67.0)', {}, '68.0')
    check_opt('1 / 2.0', {}, '0.5')
    check_opt('3 % 2', {}, '1')
    check_opt('x / y', dict(x=1, y=2.0), '0.5')


def test_division_default():
    check_opt('9 / 5', {}, '1' if six.PY2 else '1.8')


def test_division_truediv_in_constants():
    check_opt('9 / 5', dict(division=division), '1.8')


def test_division_truediv_in_source():
    # Several imports are necessary to check that the visitor will correctly discover
    # the division import.
    check_opt(
        'from __future__ import print_function, division\n9 / 5',
        {},
        'from __future__ import print_function, division\n1.8')


def test_no_opt():
    class NaN(object):
        def __init__(self, value):
            self.value = value
        def __add__(self, other):
            return NaN(self.value - other.value)
    check_opt('x + y', dict(x=NaN(1), y=NaN(2)))


# Test simple inlining

def test_simple_return():

    @inline
    def inlined(y):
        l = []
        for _ in xrange(y):
            l.append(y.do_stuff())
        return l

    check_opt(
        '''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
            a = b + inlined(x)
            return a
        ''',
        dict(inlined=inlined),
        '''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
            __mangled_2 = []
            for __mangled_3 in xrange(x):
                __mangled_2.append(x.do_stuff())
            a = (b + __mangled_2)
            return a
        ''')

def test_complex_return():

    @inline
    def inlined(y):
        l = []
        for i in iter(y):
            l.append(i.do_stuff())
        if l:
            return l
        else:
            return None

    check_opt(
        '''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
                a = inlined(x - 3) + b
            return a
        ''',
        dict(inlined=inlined),
        '''
        def outer(x):
            a = x.foo()
            if a:
                b = a * 10
                __mangled_1 = x - 3
                __while_5 = True
                while __while_5:
                    __while_5 = False
                    __mangled_2 = []
                    for __mangled_3 in iter(__mangled_1):
                        __mangled_2.append(__mangled_3.do_stuff())
                    if __mangled_2:
                        __return_4 = __mangled_2
                        break
                    else:
                        __return_4 = None
                        break
                a = __return_4 + b
            return a
        ''')


# Recursion inlining test

def test_no_inlining():
    check_opt(
        '''
        def power(x, n):
            if n == 0:
                return 1
            elif n % 2 == 0:
                v = power(x, n // 2)
                return v * v
            else:
                return x * power(x, n - 1)
        ''',
        dict(n=1),
        '''
        def power(x, n):
            return x * power(x, 0)
        ''')


def test_inlining_1():

    @inline
    def power(x, n):
        if n == 0:
            return 1
        elif n % 2 == 0:
            v = power(x, n // 2)
            return v * v
        else:
            return x * power(x, n - 1)

    source = ast_to_source(Function.from_object(power).tree)

    check_opt(source,
        dict(n=1, power=power),
        '''
        @inline
        def power(x, n):
            return (x * 1)
        ''')
    check_opt(source,
        dict(n=5, power=power),
        '''
        @inline
        def power(x, n):
            __return_11 = (x * 1)
            __return_7 = (__return_11 * __return_11)
            __return_3 = (__return_7 * __return_7)
            return x * __return_3
        ''')
