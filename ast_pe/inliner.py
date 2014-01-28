# -*- encoding: utf-8 -*-

import ast

from ast_pe.utils import new_var_name


class Inliner(ast.NodeTransformer):
    ''' Mangle all variable names, returns.
    '''
    def __init__(self, var_count_start, fn_locals):
        self._var_count = var_count_start
        self._locals = fn_locals
        self._mangled = {} # {original name -> mangled name}
        self._return_var = None
        super(Inliner, self).__init__()

    def get_var_count(self):
        return self._var_count

    def get_bindings(self):
        return self._mangled

    def get_return_var(self):
        return self._return_var

    def _visit_local(self, node):
        ''' Replacing known variables with literal values
        '''
        self.generic_visit(node)
        is_name = isinstance(node, ast.Name)

        node_id = node.id if is_name else node.arg
        if node_id in self._locals:
            if node_id in self._mangled:
                mangled_id = self._mangled[node_id]
            else:
                mangled_id = new_var_name(self)
                self._mangled[node_id] = mangled_id
            if is_name:
                return ast.Name(id=mangled_id, ctx=node.ctx)
            else:
                return ast.arg(arg=mangled_id, annotation=node.annotation)
        else:
            return node

    def visit_arg(self, node):
        return self._visit_local(node)

    def visit_Name(self, node):
        return self._visit_local(node)

    def visit_Return(self, node):
        ''' Substitute return with return variable assignment + break
        '''
        self.generic_visit(node)
        if self._return_var is None:
            self._return_var = new_var_name(self)
        return [ast.Assign(
                    targets=[ast.Name(id=self._return_var, ctx=ast.Store())],
                    value=node.value),
                ast.Break()]

