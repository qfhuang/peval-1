from peval.core.symbol_finder import find_symbol_creations


class GenSym(object):

    def __init__(self, tree=None):
        self._names = find_symbol_creations(tree) if tree is not None else set()
        self._counter = 0

    def _gen_name(self, tag):
        return '__' + tag + '_' + str(self._counter)

    def __call__(self, tag='peval_sym'):

        while True:
            self._counter += 1
            name = self._gen_name(tag)
            if name not in self._names:
                break

        self._names.add(name)
        return name

    def get_state(self):
        return self._counter, self._names

    def set_state(self, state):
        self._counter, self._names = state

    @classmethod
    def from_state(cls, state):
        gs = cls()
        gs.set_state(state)
        return gs
