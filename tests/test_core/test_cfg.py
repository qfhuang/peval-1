import ast
import inspect
import os, os.path
import subprocess

from astunparse import unparse

from peval.core.cfg import build_cfg

from tests.utils import print_diff


RENDER_GRAPHS = False


def make_label(node):
    return unparse(node.ast_node).split("\n")[1]


def get_edges(cfg):
    edges = []
    for node_id in cfg.graph._nodes:
        for child_id in cfg.graph.children_of(node_id):
            edges.append((node_id, child_id))
    return edges


def get_labeled_edges(cfg):
    edges = []
    todo_list = [cfg.enter]
    visited = set()

    while len(todo_list) > 0:
        src_id = todo_list.pop()
        if src_id in visited:
            continue
        visited.add(src_id)

        src_label = make_label(cfg.graph._nodes[src_id])

        dests = [
            (dest_id, make_label(cfg.graph._nodes[dest_id]))
            for dest_id in cfg.graph.children_of(src_id)]
        dests = sorted(dests, key=lambda pair: pair[1])

        for dest_id, dest_label in dests:
            edges.append((src_label, dest_label))
            todo_list.append(dest_id)

    return edges


def render_cfg(cfg, fname):
    from astunparse import unparse

    node_str = lambda node_id, label: (
        '    {node_id} [label="{label}"]'.format(node_id=node_id, label=label))
    edge_str = lambda node1, node2: '    {node1} -> {node2}'.format(node1=node1, node2=node2)

    directives = []

    directives.append(node_str('enter', 'enter'))
    directives.append(node_str('exit', 'exit'))

    for node_id, node in cfg.graph._nodes.items():
        directives.append(node_str(node_id, make_label(node)))

    directives.append(edge_str('enter', cfg.enter))
    for exit in cfg.exits:
        directives.append(edge_str(exit, 'exit'))

    for node_id in cfg.graph._nodes:
        for child_id in cfg.graph.children_of(node_id):
            directives.append(edge_str(node_id, child_id))

    base, ext = os.path.splitext(os.path.abspath(fname))
    dotfile = base + '.dot'

    with open(dotfile, 'w') as f:
        f.write("\n".join(
            ["strict digraph {",
            "    node [label=\"\\N\"];"]
            + directives
            + ["}"]
            ))

    picfile = base + ext
    subprocess.check_call(['dot', '-T' + ext[1:], dotfile, '-o', picfile])
    os.remove(dotfile)


def get_body(function):
    src = inspect.getsource(function)
    return ast.parse(src).body[0].body


def assert_edges_equal(cfg, expected_edges):
    test_edges = get_labeled_edges(cfg)
    equal = (test_edges == expected_edges)
    if not equal:
        make_str = lambda edges: "\n".join(src + " --> " + dest for src, dest in edges)
        test_str = make_str(test_edges)
        expected_str = make_str(expected_edges)
        print_diff(test_str, expected_str)
    assert equal


def check_cfg(function, expected_edges):
    statements = get_body(function)
    cfg = build_cfg(statements)

    print()
    for src, dest in get_labeled_edges(cfg):
        print(repr((src, dest)) + ",")

    assert_edges_equal(cfg, expected_edges)

    if RENDER_GRAPHS:
        render_cfg(cfg, 'test_' + function.__name__ + '.pdf')


def func_if():
    a = 1
    b = 2
    if a > 2:
        do_stuff()
        do_smth_else()
        return 3
    elif a > 4:
        foo()
    else:
        bar()

    return b


def test_func_if():
    check_cfg(func_if, [
        ('a = 1', 'b = 2'),
        ('b = 2', 'if (a > 2):'),
        ('if (a > 2):', 'do_stuff()'),
        ('if (a > 2):', 'if (a > 4):'),
        ('if (a > 4):', 'bar()'),
        ('if (a > 4):', 'foo()'),
        ('foo()', 'return b'),
        ('bar()', 'return b'),
        ('do_stuff()', 'do_smth_else()'),
        ('do_smth_else()', 'return 3')])


def func_for():
    a = 1

    for i in range(5):
        b = 2
        if i > 4:
            break
        elif i > 2:
            continue
        else:
            foo()
    else:
        c = 3

    return b


def test_func_for():
    check_cfg(func_for, [
        ('a = 1', 'for i in range(5):'),
        ('for i in range(5):', 'b = 2'),
        ('b = 2', 'if (i > 4):'),
        ('if (i > 4):', 'break'),
        ('if (i > 4):', 'if (i > 2):'),
        ('if (i > 2):', 'continue'),
        ('if (i > 2):', 'foo()'),
        ('foo()', 'c = 3'),
        ('foo()', 'for i in range(5):'),
        ('c = 3', 'return b'),
        ('continue', 'for i in range(5):'),
        ('break', 'return b')])


def func_try():
    a = 1

    for i in range(5):
        try:
            do()
            if i > 3:
                break
            stuff()
        except Exception:
            foo()
        except ValueError:
            bar()
        else:
            do_else()

    return b


def test_func_try():
    check_cfg(func_try, [
        ('a = 1', 'for i in range(5):'),
        ('for i in range(5):', 'try:'),
        ('try:', 'do()'),
        ('do()', 'except Exception:'),
        ('do()', 'except ValueError:'),
        ('do()', 'if (i > 3):'),
        ('if (i > 3):', 'break'),
        ('if (i > 3):', 'except Exception:'),
        ('if (i > 3):', 'except ValueError:'),
        ('if (i > 3):', 'stuff()'),
        ('stuff()', 'do_else()'),
        ('stuff()', 'except Exception:'),
        ('stuff()', 'except ValueError:'),
        ('except ValueError:', 'bar()'),
        ('bar()', 'for i in range(5):'),
        ('bar()', 'return b'),
        ('except Exception:', 'foo()'),
        ('foo()', 'for i in range(5):'),
        ('foo()', 'return b'),
        ('do_else()', 'for i in range(5):'),
        ('do_else()', 'return b'),
        ('break', 'return b')])


def func_try_finally():
    a = 1

    try:
        do()
        stuff()
        return c
    except Exception:
        foo()
    else:
        do_else()
    finally:
        do_finally()

    return b


def test_func_try_finally():
    check_cfg(func_try_finally, [
        ('a = 1', 'try:'),
        ('try:', 'do()'),
        ('do()', 'except Exception:'),
        ('do()', 'stuff()'),
        ('stuff()', 'except Exception:'),
        ('stuff()', 'return c'),
        ('return c', 'do_finally()'),
        ('return c', 'except Exception:'),
        ('except Exception:', 'foo()'),
        ('foo()', 'do_finally()'),
        ('do_finally()', 'return b')])
