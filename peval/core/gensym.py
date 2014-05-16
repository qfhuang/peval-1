from peval.core.symbol_finder import find_symbol_creations


class GenSym(object):

    def __init__(self, taken_names=None, counter=1):
        self._taken_names = taken_names if taken_names is not None else set()
        self._counter = counter

    @classmethod
    def for_tree(cls, tree=None):
        taken_names = find_symbol_creations(tree) if tree is not None else None
        return cls(taken_names=taken_names)

    def __call__(self, tag='peval_sym'):
        while True:
            name = '__' + tag + '_' + str(self._counter)
            self._counter += 1
            if name not in self._taken_names:
                break

        return name, GenSym(taken_names=self._taken_names, counter=self._counter)
