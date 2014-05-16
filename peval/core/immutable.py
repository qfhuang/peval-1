"""
Immutable data structures.

The classes in this module have the prefix 'immutable' to avoid confusion
with the built-in ``frozenset``, which does not have any modification methods,
even pure ones.
"""


class immutabledict(dict):
    """
    An immutable version of ``dict``.

    Mutating syntax (``del d[k]``, ``d[k] = v``) is prohibited,
    pure methods ``del_`` and ``set`` are available instead.
    Mutating methods are overridden to return the new dictionary
    (or a tuple ``(value, new_dict)`` where applicable)
    without mutating the source dictionary.
    If a mutating method does not change the dictionary,
    the source dictionary itself is returned as the new dictionary.
    """

    def clear(self):
        return padict()

    def copy(self):
        return self

    def pop(self, *args):
        new_dict = self.__class__(self)
        value = dict.pop(new_dict, *args)
        return value, new_dict

    def popitem(self):
        new_dict = self.__class__(self)
        value = dict.popitem(new_dict)
        return value, new_dict

    def setdefault(self, *args):
        key = args[0]
        if key not in self:
            new_dict = self.__class__(self)
            value = dict.setdefault(new_dict, *args)
            return value, new_dict
        else:
            return self[key], self

    def __delitem__(self, key, item):
        raise AttributeError("Pure dict does not support mutating item deletion")

    def del_(self, key):
        if key in self:
            new_dict = self.__class__(self)
            dict.__delitem__(new_dict, key, value)
            return new_dict
        else:
            return self

    def __setitem__(self, key, item):
        raise AttributeError("Pure dict does not support mutating item setting")

    def set(self, key, value):
        if key in self and self[key] is value:
            return self
        else:
            new_dict = self.__class__(self)
            dict.__setitem__(new_dict, key, value)
            return new_dict

    def update(self, *args, **kwds):

        if len(kwds) == 0 and len(args) == 0:
            return self

        if len(args) > 0:
            if isinstance(args[0], dict):
                new_vals = args[0]
            else:
                new_vals = dict(args)
        else:
            new_vals = {}

        new_vals.update(kwds)

        for kwd, value in new_vals.items():
            if self.get(kwd, None) is not value:
                break
        else:
            return self

        new_dict = self.__class__(self)
        dict.update(new_dict, new_vals)
        return new_dict

    def __repr__(self):
        return "immutabledict(" + dict.__repr__(self) + ")"


class immutableadict(immutabledict):
    """
    A subclass of ``immutabledict`` with values being accessible as attributes
    (e.g. ``d['a']`` is equivalent to ``d.a``).
    """

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr):
        raise AttributeError("Pure dict does not support mutating attribute setting")

    def __repr__(self):
        return "immutableadict(" + dict.__repr__(self) + ")"


class immutableset(set):
    """
    An immutable version of ``set``.

    Mutating methods are overridden to return the new set
    (or a tuple ``(value, new_set)`` where applicable)
    without mutating the source set.
    If a mutating method does not change the set,
    the source set itself is returned as the new set.
    """

    def add(self, elem):
        if elem in self:
            return self
        else:
            new_set = self.__class__(self)
            set.add(new_set, elem)
            return new_set

    def clear(self):
        return self.__class__()

    def copy(self):
        return self
