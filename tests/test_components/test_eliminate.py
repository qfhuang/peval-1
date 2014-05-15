import pytest


def test_if_true_elimination():
    ''' Eliminate if test, if the value is known at compile time
    '''

    pytest.xfail()

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

    pytest.xfail()

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

    pytest.xfail()

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

    pytest.xfail()

    check_opt('if x: do_stuff()', dict(x=False), 'pass')
    check_opt('''
            if x:
                pass
            else:
                do_stuff()
            ''',
            dict(x=object()),
            'pass')


def test_visit_all_branches():

    pytest.xfail()

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



def test_remove_pass():

    pytest.xfail()

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

    pytest.xfail()

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

    pytest.xfail()

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

    pytest.xfail()

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

    pytest.xfail()

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
