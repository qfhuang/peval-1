import pytest

from peval.components.fold import fold

from tests.utils import check_component


def dummy(x):
    a = 1
    if a > 2:
        b = 3
        c = 4 + 6
    else:
        b = 2
        c = 3 + a
    return a + b + c + x


def test_fold():
    check_component(
        fold, dummy,
        expected_source="""
            def dummy(x):
                a = 1
                if True:
                    b = 3
                    c = 10
                else:
                    b = 2
                    c = 4
                return 1 + b + c + x
            """)


def test_if_visit_only_true_branch():

    # This optimization can potentially save some time during constant propagation
    # (by not evaluating the functions that will be eliminated anyway).
    # Not implemented at the moment.
    pytest.xfail()

    global_state = dict(cnt=0)

    @pure_function
    def inc():
        global_state['cnt'] += 1
        return True

    def if_body():
        if a:
            inc()

    def if_else():
        if a:
            dec()
        else:
            inc()

    check_component(
        fold, if_body, additional_bindings=dict(a=False, inc=inc),
        expected_source="""
            def if_body():
                if False:
                    inc()
            """)
    assert global_state['cnt'] == 0

    check_component(
        fold, if_else, additional_bindings=dict(a=False, inc=inc),
        expected_source="""
            def if_else():
                if False:
                    dec()
                else:
                    inc()
            """)
    assert global_state['cnt'] == 1


# Test that nodes whose values are known first but are mutated later
# are not substituted with values calculated at compile time.

def test_self_mutation_via_method():

    pytest.xfail()

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

    pytest.xfail()

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
