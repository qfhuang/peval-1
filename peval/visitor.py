import ast


class Visitor(ast.NodeTransformer):
    ''' Simplify AST, given information about what variables are known
    '''

    def __init__(self):
        super(Visitor, self).__init__()
        self._current_block = None # None, or a list of nodes that correspond
        # to currently visited code block

    def generic_visit(self, node):
        ''' Completly substite parent class "generic_visit", in order to
        be able to insert some code at the line before current expression
        (e.g. when inlining functions).
        Also do some logging.
        '''
        # copy-paste from ast.py, added self._current_block handling
        block_fields = ['body', 'orelse']
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                new_values = []
                if field in block_fields:
                    parent_block = self._current_block
                    self._current_block = new_values
                try:
                    for value in old_value:
                        if isinstance(value, ast.AST):
                            value = self.visit(value)
                            if value is None:
                                continue
                            elif not isinstance(value, ast.AST):
                                new_values.extend(value)
                                continue
                        new_values.append(value)
                    old_value[:] = new_values
                finally: # restore self._current_block
                    if field in block_fields:
                        self._current_block = parent_block
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        # end of copy-paste
        return node

    def _visit(self, node):
        ''' Similar to generic_visit - node can be a list, or an AST node.
        For list we visit all elements and collect results, also eliminating
        dead code.
        '''
        if isinstance(node, list):
            result = []
            parent_block = self._current_block
            self._current_block = result
            try:
                for n in node:
                    r = self.visit(n)
                    if isinstance(r, list):
                        result.extend(r)
                    else:
                        result.append(r)
                return result
            finally:
                self._current_block = parent_block
        else:
            return self.visit(node)
