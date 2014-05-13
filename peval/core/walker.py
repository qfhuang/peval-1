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
    to the method with the name ``visit_<tp>()`` if it exists
    (e.g., ``visit_FunctionDef()`` for ``ast.FunctionDef``),
    otherwise to the method ``visit()`` if it exists,
    otherwise to the built-in default function which just returns the node and does nothing.
    """
    return _Walker(func, transform=True, inspect=True)


def ast_transformer(func):
    """
    A shortcut for ``ast_walker()`` with no state.
    Returns only the transformed AST.
    """
    return _Walker(func, transform=True)


def ast_inspector(func):
    """
    A shortcut for ``ast_walker()`` which does not transform the tree, but only collects data.
    Returns only the state object.
    """
    return _Walker(func, inspect=True)


class _AttrDict(dict):

    def __getattr__(self, attr):
        return self[attr]


# The AST node fields which contain lists of statements
_BLOCK_FIELDS = ('body', 'orelse')


class _Walker:

    def __init__(self, callback, inspect=False, transform=False):

        self._transform = transform
        self._inspect = inspect
        if not (self._transform or self._inspect):
            raise ValueError("At least one of `transform` and `inspect` should be set")

        self._current_block_stack = [[]]

        self._callbacks = {}

        # These method have different signatures depending on
        # whether transform and inspect are on,
        # so for the sake of performance we're using specialized versions of them.
        if self._transform and self._inspect:
            self._walk_field_user = self._transform_inspect_field
            self._default_callback = lambda node, state, **kwds: (node, state)
        elif self._transform:
            self._walk_field_user = self._transform_field
            self._default_callback = lambda node, **kwds: node
        elif self._inspect:
            self._walk_field_user = self._inspect_field
            self._default_callback = lambda node, state, **kwds: state

        # Fill the callbacks map.
        # Use the same naming scheme as ast.Visitor and ast.NodeTransformer do.
        if isinstance(callback, types.FunctionType):
            self._default_callback = callback
        else:
            if hasattr(callback, 'visit'):
                self._default_callback = getattr(callback, 'visit')
            for attr in vars(callback):
                if attr.startswith('visit_'):
                    typename = attr[6:]
                    if hasattr(ast, typename):
                        self._callbacks[getattr(ast, typename)] = getattr(callback, attr)

    def _walk_list(self, lst, state, ctx, block_context=False):
        """
        Traverses a list of AST nodes.
        If ``block_context`` is ``True``, the list contains statements
        (and therefore is a target for ``prepend()`` calls in nested handlers).
        """

        if self._transform:
            transformed = False
            new_lst = []

            if block_context:
                self._current_block_stack.append([])

        new_state = state

        for node in lst:
            new_node, new_state = self._walk_node(node, new_state, ctx, list_context=True)

            if self._transform and block_context and len(self._current_block_stack[-1]) > 0:
            # ``prepend()`` was called during ``_walk_node()``
                transformed = True
                new_lst.extend(self._current_block_stack[-1])
                self._current_block_stack[-1] = []

            if self._transform:
                if isinstance(new_node, ast.AST):
                    if new_node is not node:
                        transformed = True
                    new_lst.append(new_node)
                elif isinstance(new_node, list):
                    transformed = True
                    new_lst.extend(new_node)
                elif new_node is None:
                    transformed = True

        if self._transform:
            if block_context:
                self._current_block_stack.pop()

            if transformed:
                if block_context and len(new_lst) == 0:
                # If we're in the block context, we can't just return an empty list.
                # Returning a single ``pass`` instead.
                    new_lst = [ast.Pass()]
        else:
            new_lst = lst

        return new_lst, new_state

    def _walk_field(self, value, state, ctx, block_context=False):
        """
        Traverses a single AST node field.
        """
        if isinstance(value, ast.AST):
            return self._walk_node(value, state, ctx)
        elif isinstance(value, list):
            return self._walk_list(value, state, ctx, block_context=block_context)
        else:
            return value, state

    def _transform_field(self, ctx, value, block_context=False):
        return self._walk_field(value, None, ctx, block_context=block_context)[0]

    def _inspect_field(self, ctx, value, state, block_context=False):
        return self._walk_field(value, state, ctx, block_context=block_context)[1]

    def _transform_inspect_field(self, ctx, value, state, block_context=False):
        return self._walk_field(value, state, ctx, block_context=block_context)

    def _walk_fields(self, node, state, ctx):
        """
        Traverses all fields of an AST node.
        """
        if self._transform:
            transformed = False
            new_fields = {}

        new_state = state
        for field, value in ast.iter_fields(node):

            block_context = field in _BLOCK_FIELDS
            new_value, new_state = self._walk_field(
                value, new_state, ctx, block_context=block_context)

            if self._transform:
                new_fields[field] = new_value
                if new_value is not value:
                    transformed = True

        if self._transform and transformed:
            return type(node)(**new_fields), new_state
        else:
            return node, new_state

    def _unpack_result(self, result, node, state):
        if self._transform and self._inspect:
            return result[0], result[1]
        elif self._transform:
            return result, state
        elif self._inspect:
            return node, result

    def _visit_node(self, handler, node, state, ctx, list_context=False, visiting_after=False):

        def prepend(nodes):
            self._current_block_stack[-1].extend(nodes)

        to_visit_after = [False]
        def visit_after():
            to_visit_after[0] = True

        to_skip_fields = [False]
        def skip_fields():
            to_skip_fields[0] = True

        def walk_field(*args, **kwds):
            return self._walk_field_user(ctx, *args, **kwds)

        result = handler(
            node, state=state, ctx=ctx,
            prepend=prepend,
            visit_after=None if visiting_after else visit_after,
            visiting_after=visiting_after,
            skip_fields=skip_fields,
            walk_field=walk_field)
        new_node, new_state = self._unpack_result(result, node, state)

        if self._transform:
            if list_context:
                expected_types = (ast.AST, list)
                expected_str = "None, AST, list"
            else:
                expected_types = (ast.AST,)
                expected_str = "None, AST"

            if new_node is not None and not isinstance(new_node, expected_types):
                raise TypeError(
                    "Expected callback return types in {context} are {expected}, got {got}".format(
                        context=("list context" if list_context else "field context"),
                        expected=expected_str,
                        got=type(new_node)))

        return new_node, new_state, to_visit_after[0], to_skip_fields[0]

    def _walk_node(self, node, state, ctx, list_context=False):
        """
        Traverses an AST node and its fields.
        """

        handler = self._callbacks.get(type(node), self._default_callback)
        new_node, new_state, to_visit_after, to_skip_fields = self._visit_node(
            handler, node, state, ctx, list_context=list_context, visiting_after=False)

        if isinstance(new_node, ast.AST) and new_node is node and not to_skip_fields:
            new_node, new_state = self._walk_fields(new_node, new_state, ctx)

        if isinstance(new_node, ast.AST) and to_visit_after:
            new_node, new_state, _, _ = self._visit_node(
                handler, new_node, new_state, ctx, list_context=list_context, visiting_after=True)

        return new_node, new_state

    def __call__(self, node, ctx=None, state=None):

        if not self._inspect and state is not None:
            raise ValueError("Pure transformation walker cannot have a state")

        if ctx is not None:
            ctx = _AttrDict(ctx)

        if isinstance(node, ast.AST):
            new_node, new_state = self._walk_node(node, state, ctx)
        elif isinstance(node, list):
            new_node, new_state = self._walk_list(node, state, ctx)
        else:
            raise TypeError("Cannot walk an object of type " + str(type(node)))

        if self._transform and self._inspect:
            return new_node, new_state
        elif self._transform:
            return new_node
        elif self._inspect:
            return new_state
