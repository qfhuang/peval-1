# -*- encoding: utf-8 -*-

import ast

from ast_pe.utils import BaseTestCase, shift_source
from ast_pe.optimizer import Optimizer
from ast_pe.decorators import pure_function


class BaseOptimizerTestCase(BaseTestCase):
    def _test_optization(self, source, bindings, expected_source,
            expected_new_bindings=None):
        ''' Test that with given bindings, Optimizer transforms
        source to expected_source.
        It expected_new_bindings is given, we expect Optimizer to add
        them to bindings.
        '''
        self.assertASTEqual(
                Optimizer(bindings).visit(ast.parse(shift_source(source))),
                ast.parse(shift_source(expected_source)))
        if expected_new_bindings:
            for k in expected_new_bindings:
                self.assertEqual(bindings[k], expected_new_bindings[k])


class TestConstantPropagation(BaseOptimizerTestCase):
    def test_constant_propagation(self):
        self._test_optization(
                'a * n + (m - 2) * (n + 1)', dict(n=5),
                'a * 5 + (m - 2) * (5 + 1)')
        self._test_optization(
                'a * n + (m - 2) * (n + 1)', dict(n=5.0),
                'a * 5.0 + (m - 2) * (5.0 + 1)')
        self._test_optization(
                'foo[:5]', dict(foo="bar"),
                '"bar"[:5]')

    def test_constant_propagation_fail(self):
        ''' Test that constant propogation does not happen on primitive
        subclasses
        '''
        class Int(int): pass
        self._test_optization(
                'm * n', dict(m=Int(2)),
                'm * n')
        self._test_optization(
                'm * n', dict(m=Int(2), n=3),
                'm * 3')
        class Float(float): pass
        self._test_optization(
                'm * n', dict(m=Float(2.0)),
                'm * n')
        class String(str): pass
        self._test_optization(
                'm + n', dict(m=String('foo')),
                'm + n')
        class Unicode(unicode): pass
        self._test_optization(
                'm + n', dict(m=Unicode(u'foo')),
                'm + n')

class TestIf(BaseOptimizerTestCase):
    def test_if_true_elimination(self):
        ''' Eliminate if test, if the value is known at compile time
        '''
        true_values = [True, 1, 2.0, object(), "foo", int]
        self.assertTrue(all(true_values))
        for x in true_values:
            self._test_optization(
                    'if x: print "x is True"', dict(x=x),
                    'print "x is True"')
        self._test_optization('''
            if x:
                do_stuff()
            else:
                do_other_stuff()
            ''',
            dict(x=2),
            'do_stuff()')
    
    def test_if_no_elimination(self):
        ''' Test that there is no unneeded elimination of if test
        '''
        self._test_optization('''
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

    def test_if_false_elimination(self):
        ''' Eliminate if test, when test is false
        '''
        class Falsy(object): 
            def __nonzero__(self):
                return False
        false_values = [0, '', [], {}, set(), False, None, Falsy()]
        for x in false_values:
            self._test_optization('''
                if x:
                    do_stuff()
                else:
                    do_other_stuff()
                ''',
                dict(x=x),
                'do_other_stuff()')

    def test_if_empty_elimination(self):
        ''' Eliminate if completly, when corresponding clause is empty
        '''
        self._test_optization('if x: do_stuff()', dict(x=False), 'pass')
        self._test_optization('''
                if x:
                    pass
                else:
                    do_stuff()
                ''', 
                dict(x=object()),
                'pass')
        
    def test_if_visit_only_true_branch(self):
        pass # TODO


class TestFnEvaluation(BaseOptimizerTestCase):
    ''' Test function calling
    '''
    def test_call_no_args(self):
        @pure_function
        def fn():
            return 'Hi!'
        self._test_optization(
                'x = fn()', 
                dict(fn=fn), 
                'x = __ast_pe_var_1',
                dict(__ast_pe_var_1="Hi!"))

    def test_call_with_args(self):
        @pure_function
        def fn(x, y):
            return x + y
        self._test_optization(
                'z = fn(x, y)',
                dict(fn=fn, x=10),
                'z = fn(10, y)')
        self._test_optization(
                'z = fn(x, y)',
                dict(fn=fn, x=10, y=20.0),
                'z = __ast_pe_var_1',
                dict(__ast_pe_var_1=30.0))

    def test_call_with_starargs(self):
        pass # TODO
    
    def test_call_with_kwargs(self):
        pass #TODO

    def test_exception(self):
        ''' Test when called function raises an exception - 
        we want it to raise it in specialized function 
        '''
        @pure_function
        def fn():
            return 1 / 0
        self._test_optization('x = fn()', dict(fn=fn), 'x = fn()')


class TestBuiltinsEvaluation(BaseOptimizerTestCase):
    ''' Test that we can evaluate builtins
    '''
    def test_evaluate(self):
        self._test_optization(
                'isinstance(n, int)',
                dict(n=10),
                '__ast_pe_var_1',
                dict(__ast_pe_var_1=True))


class TestUnaryOp(BaseOptimizerTestCase):
    def test_not(self):
        self._test_optization(
                'not x', dict(x="s"), 
                '__ast_pe_var_1', dict(__ast_pe_var_1=False))
        self._test_optization(
                'not x', dict(x=0), 
                '__ast_pe_var_1', dict(__ast_pe_var_1=True))
