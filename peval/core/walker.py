"""
A replacement for ``ast.Visitor`` and ``ast.NodeTransformer`` from the standard library,
featuring a functional interface, explicit state passing, non-mutating AST transformation
and various minor convenience functionality.
Inspired by the ``Walker`` class from ``macropy``.
"""

import ast
import types


def ast_walker(func):
    """
    A generic AST walker decorator.
    Decorates either a function or a class (if dispatching based on node type is required).

    Returns a callable with the signature

    ::

        def walker(node, state=None, ctx=None)

    :param node: an ``ast.AST`` object to traverse.
    :param state: a mutable object that will be passed to every handler call.
    :param ctx: a dictionary with the global context which will be passed to every handler call.
    :returns: a tuple ``(new_node, state)``, where ``state`` is the same object which was passed
        as the corresponding parameter.
        Does not mutate ``node``.

    If ``func`` is a function, it will be called for every node during the AST traversal
    (depth-first, pre-order).
    It must have the signature

    ::

        def handler(node, [state, ctx, prepend, visit_after, visiting_after,
            skip_fields, walk_field,] **kwds)

    The names of the optional arguments must be exactly as written here,
    but their order is not significant.

    :param state: a mutable state object passed during the initial call.
        Can be modified inside a handler.
    :param ctx: a (supposedly immutable) dictionary with the global context
        passed during the initial call.
        In addition to normal dictionary methods, its values can be alternatively
        accessed as attributes (e.g. either ``ctx['value']`` or ``ctx.value``).
        It should not be modified by handlers.
    :param prepend: a function ``prepend(lst)`` which, when called, prepends the list
        of ``ast.AST`` objects to whatever is returned by the handler of the closest
        statement block that includes the current node.
        These nodes are not traversed automatically.
    :param visit_after: a function of no arguments, which, when called,
        schedules to call the handler again on this node when all of its fields are traversed
        (providing that after calling it, the handler returns an ``ast.AST`` object
        and not a list or ``None``).
        During the second call this parameter is set to ``None``.
    :param visiting_after: set to ``False`` during the normal (pre-order) visit,
        and to ``True`` during the visit caused by ``visit_after()``.
    :param skip_fields: a function of no arguments, which, when called,
        orders the walker not to traverse this node's fields.
    :param walk_field: a function ``walk_field(value, block_context=False)``,
        which runs the traversal of the given field value.
        If the value contains a list of statements, ``block_context`` must be set to ``True``,
        so that ``prepend`` could work correctly.

        .. warnning::

            Note that ``state`` may be changed after a call to ``walk_field()``.

    :returns: must return one of:
        * ``None``, in which case the corresponding node will be removed from the parent list
          or the parent node field.
        * The passed ``node`` (unchanged).
          By default, its fields will be traversed (unless ``skip_fields()`` is called).
        * A new ``ast.AST`` object, which will replace the passed ``node`` in the AST.
          By default, its fields will not be traversed,
          and the handler must do it manually if needed
          (by calling ``walk_field()``).
        * If the current node is an element of a list,
          a list of ``ast.AST`` objects can be returned,
          which will be spliced in place of the node.
          Same as in the previous case, these new nodes
          will not be automatically traversed.

    If the decorator target is a class, it must contain several static methods
    with the signatures as above.
    During traversal, for a node with the type ``tp``, the call will be dispatched
    to the method with the name ``visit_<lowercase_tp>()`` if it exists
    (e.g., ``visit_functiondef()`` for ``ast.FunctionDef``),
    otherwise to the method ``visit()`` if it exists,
    otherwise to the built-in default function which just returns the node and does nothing.
    """
    return _Walker(func, transform=True, inspect=True)


def ast_transformer(func):
    return _Walker(func, transform=True)


def ast_inspector(func):
    return _Walker(func, inspect=True)


class _AttrDict(dict):

    def __getattr__(self, attr):
        return self[attr]


_BLOCK_FIELDS = ('body', 'orelse')


class _Walker:

    def __init__(self, callback, inspect=False, transform=False):

        if inspect and transform:
            self._call = self._transform_inspect
        elif inspect:
            self._call = self._inspect
        elif transform:
            self._call = self._transform

        self._dispatched_callback = not isinstance(callback, types.FunctionType)
        self._callback = callback
        self._current_block_stack = [[]]

    def _walk_list(self, lst, state, ctx, block_context=False):
        transformed = False
        new_lst = []

        if block_context:
            self._current_block_stack.append([])

        for node in lst:
            result = self._visit_node(node, state, ctx, list_context=True)

            if block_context and len(self._current_block_stack[-1]) > 0:
                transformed = True
                new_lst.extend(self._current_block_stack[-1])
                self._current_block_stack[-1] = []

            if isinstance(result, ast.AST):
                if result is not node:
                    transformed = True
                new_lst.append(result)
            elif isinstance(result, list):
                transformed = True
                new_lst.extend(result)
            elif result is None:
                transformed = True

        if block_context:
            self._current_block_stack.pop()

        if transformed:
            if block_context and len(new_lst) == 0:
                return [ast.Pass()]
            else:
                return new_lst
        else:
            return lst

    def _walk_field(self, value, state, ctx, block_context=False):
        if isinstance(value, ast.AST):
            return self._visit_node(value, state, ctx)
        elif isinstance(value, list):
            return self._walk_list(value, state, ctx, block_context=block_context)
        else:
            return value

    def _walk_fields(self, node, state, ctx):
        transformed = False
        new_fields = {}
        for field, value in ast.iter_fields(node):

            block_context = field in _BLOCK_FIELDS
            new_value = self._walk_field(value, state, ctx, block_context=block_context)

            new_fields[field] = new_value
            if new_value is not value:
                transformed = True

        if transformed:
            return type(node)(**new_fields)
        else:
            return node

    @staticmethod
    def _pass_through(node, **kwds):
        return node

    def _get_handler(self, node):

        if self._dispatched_callback:
            handler_name = 'visit_' + type(node).__name__.lower()
            if hasattr(self._callback, handler_name):
                return getattr(self._callback, handler_name)
            elif hasattr(self._callback, 'visit'):
                return self._callback.visit
            else:
                return self._pass_through
        else:
            return self._callback

    def _visit_node(self, node, state, ctx, list_context=False):

        def prepend(nodes):
            self._current_block_stack[-1].extend(nodes)

        visiting_after = [False]
        def visit_after():
            visiting_after[0] = True

        skipping_fields = [False]
        def skip_fields():
            skipping_fields[0] = True

        def walk_field(value, block_context=False):
            return self._walk_field(value, state, ctx, block_context=block_context)

        handler = self._get_handler(node)
        result = handler(
            node, state=state, ctx=ctx, prepend=prepend,
            visit_after=visit_after, visiting_after=False,
            skip_fields=skip_fields, walk_field=walk_field)

        if list_context:
            expected_types = (ast.AST, list)
            expected_str = "None, AST, list"
        else:
            expected_types = (ast.AST,)
            expected_str = "None, AST"

        if result is not None and not isinstance(result, expected_types):
            raise TypeError(
                "Expected callback return types in {context} are {expected}, got {got}".format(
                    context=("list context" if list_context else "field context"),
                    expected=expected_str,
                    got=type(result)))

        if isinstance(result, ast.AST) and result is node and not skipping_fields[0]:
            result = self._walk_fields(result, state, ctx)

        if visiting_after[0] and isinstance(result, ast.AST):
            result = handler(
                result, state=state, ctx=ctx, prepend=prepend,
                visit_after=None, visiting_after=True,
                skip_fields=skip_fields, walk_field=walk_field)

            if result is not None and not isinstance(result, expected_types):
                raise TypeError(
                    "Expected callback return types in {context} are {expected}, got {got}".format(
                        context=("list context" if list_context else "field context"),
                        expected=expected_str,
                        got=type(result)))

        return result

    def _transform_inspect(self, node, state=None, ctx=None):

        if ctx is not None:
            ctx = _AttrDict(ctx)

        if isinstance(node, ast.AST):
            wrapper_node = ast.Expr(value=node)
            new_wrapper_node = self._walk_fields(wrapper_node, state, ctx)
            new_node = new_wrapper_node.value
        elif isinstance(node, list):
            new_node = self._walk_list(node, state, ctx)
        else:
            raise TypeError("Cannot walk an object of type " + str(type(node)))

        return new_node, state

    def _transform(self, node, ctx=None):
        return self._transform_inspect(node, ctx=ctx)[0]

    def _inspect(self, node, state=None, ctx=None):
        new_node, state = self._transform_inspect(node, state=state, ctx=ctx)
        if new_node is not node:
            raise ValueError(
                "AST was transformed in the process of inspection. "
                "Run `transform_inspect` to retain the changed tree.")
        return state

    def __call__(self, *args, **kwds):
        # Redefining __call__ in __init__ does not work since Py3
        return self._call(*args, **kwds)
