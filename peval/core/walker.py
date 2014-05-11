import ast
import types


class AttrDict(dict):

    def __getattr__(self, attr):
        return self[attr]


BLOCK_FIELDS = set(['body', 'orelse'])


def ast_transformer(func):
    return Walker(func, transform=True)


def ast_inspector(func):
    return Walker(func, inspect=True)


def ast_walker(func):
    return Walker(func, transform=True, inspect=True)


class Walker:

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

            block_context = field in BLOCK_FIELDS
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

        if isinstance(result, ast.AST) and not skipping_fields[0]:
            result = self._walk_fields(result, state, ctx)

        if visiting_after[0] and isinstance(result, ast.AST):
            result = handler(
                result, state=state, ctx=ctx, prepend=prepend,
                visit_after=None, visiting_after=True)

            if result is not None and not isinstance(result, expected_types):
                raise TypeError(
                    "Expected callback return types in {context} are {expected}, got {got}".format(
                        context=("list context" if list_context else "field context"),
                        expected=expected_str,
                        got=type(result)))

        return result

    def _transform_inspect(self, node, state=None, ctx=None):

        if ctx is not None:
            ctx = AttrDict(ctx)

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
