import ast
import types


class Walker:

    def __init__(self, callback):
        self._dispatched_callback = not isinstance(callback, types.FunctionType)
        self._callback = callback

    def _walk_list(self, lst, state):
        transformed = False
        new_lst = []
        for node in lst:
            result = self._visit_node(node, state, list_context=True)
            if isinstance(result, ast.AST):
                if result is not node:
                    transformed = True
                new_lst.append(result)
            elif isinstance(result, list):
                transformed = True
                new_lst.extend(result)
            elif result is None:
                transformed = True

        if transformed:
            return new_lst
        else:
            return lst

    def _walk_fields(self, node, state):
        transformed = False
        new_fields = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                new_value = self._visit_node(value, state, list_context=False)
            elif isinstance(value, list):
                new_value = self._walk_list(value, state)
            else:
                new_value = value

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

    def _visit_node(self, node, state, list_context=False):

        handler = self._get_handler(node)
        result = handler(node, state=state)

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

        if isinstance(result, ast.AST):
            result = self._walk_fields(result, state)

        return result

    def transform_inspect(self, node, state=None):
        if isinstance(node, ast.AST):
            wrapper_node = ast.Expr(value=node)
            new_wrapper_node = self._walk_fields(wrapper_node, state)
            new_node = new_wrapper_node.value
        elif isinstance(node, list):
            new_node = self._walk_list(node, state)
        else:
            raise TypeError("Cannot walk an object of type " + str(type(node)))

        return new_node, state

    def transform(self, node):
        return self.transform_inspect(node)[0]

    def inspect(self, node, state=None):
        new_node, state = self.transform_inspect(node, state=state)
        if new_node is not node:
            raise ValueError(
                "AST was transformed in the process of inspection. "
                "Run `transform_inspect` to retain the changed tree.")
        return state
