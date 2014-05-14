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
