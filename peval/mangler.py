import ast

from peval.symbol_finder import find_symbol_creations
from peval.gensym import GenSym


class Mangler(ast.NodeTransformer):
    ''' Mangle all variable names, returns.
    '''
    def __init__(self, fn_locals, gen_sym):
        self._gen_sym = gen_sym
        self._locals = fn_locals
        self._mangled = {} # {original name -> mangled name}
        self._return_var = None
        super(Mangler, self).__init__()

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
                mangled_id = self._gen_sym('mangled')
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
            self._return_var = self._gen_sym('return')
        return [ast.Assign(
                    targets=[ast.Name(id=self._return_var, ctx=ast.Store())],
                    value=node.value),
                ast.Break()]


def mangle(node, gen_sym_state):
    locals_ = find_symbol_creations(node)
    gen_sym = GenSym.from_state(gen_sym_state)
    mangler = Mangler(locals_, gen_sym)
    new_node = mangler.visit(node)
    return_var = mangler.get_return_var()
    return new_node, gen_sym.get_state(), return_var
