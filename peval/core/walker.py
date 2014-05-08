import ast


class Walker:

    def __init__(self, callback):
        self._callback = callback

    def _walk_list(self, lst, state):
        transformed = False
        new_lst = []
        for node in lst:
            result = self._visit_node(node, state)
            if isinstance(result, ast.AST):
                if result is not node:
                    transformed = True
                new_lst.append(result)
            elif isinstance(result, list):
                transformed = True
                new_lst.extend(result)
            elif result is None:
                transformed = True
            else:
                raise TypeError("Unexpected callback return type: " + str(type(result)))

        if transformed:
            return new_lst
        else:
            return lst

    def _walk_fields(self, node, state):
        transformed = False
        new_fields = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                new_value = self._visit_node(value, state)
                if new_value is not None and not isinstance(new_value, ast.AST):
                    raise TypeError(
                        "Expected an AST or None from the callback, got " + str(type(new_value)))
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

    def _visit_node(self, node, state):

        new_node = self._callback(node, state=state)

        if new_node is node:
            # visit children
            new_node = self._walk_fields(node, state)

        return new_node

    def transform_inspect(self, node, state=None):
        if isinstance(node, ast.AST):
            new_node = self._visit_node(node, state)
        elif isinstance(node, list):
            new_node = self._walk_list(node, state)
        else:
            raise TypeError("Cannot walk an object of type " + str(type(node)))

        if type(new_node) != type(node):
            raise TypeError("Expected {expected} from the callback, got {got}".format(
                expected=type(new_node), got = type(node)))

        return new_node, state

    def transform(self, node):
        return self.transform_inspect(node)[0]

    def inspect(self, node, state=None):
        return self.transform_inspect(node, state=state)[1]
