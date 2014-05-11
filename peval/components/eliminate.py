import ast
import copy

from peval.core.walker import ast_transformer


def eliminate(node, constants):
    return _eliminate(node), constants


def replace_fields(node, **kwds):
    new_kwds = dict(ast.iter_fields(node))
    new_kwds.update(kwds)
    return type(node)(**new_kwds)


@ast_transformer
def _eliminate(node, walk_field, **kwds):
    for attr in ('body', 'orelse'):
        if hasattr(node, attr):
            old_list = getattr(node, attr)
            new_list = _filter(old_list)
            if new_list is not old_list:
                new_list = walk_field(new_list, block_context=True)
                kwds = {attr: new_list}
                node = replace_fields(node, **kwds)
    return node


def _filter(node_list):
    ''' Dead code elimination - remove "pass", code after return
    '''
    if len(node_list) == 1 and isinstance(node_list[0], ast.Pass):
        return node_list

    new_list = []
    for i, node in enumerate(node_list):
        if isinstance(node, ast.Pass):
            continue
        if isinstance(node, ast.Return):
            return new_list + [node]
        new_list.append(node)
    if len(new_list) == len(node_list):
        return node_list
    else:
        return new_list
