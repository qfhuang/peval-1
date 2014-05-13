def pure_update(d, *args, **kwds):
    if len(kwds) == 0 and len(args) == 0:
        return d

    if len(args) > 0:
        if isinstance(args[0], dict):
            new_vals = args[0]
        else:
            new_vals = dict(args)
    else:
        new_vals = {}

    new_vals.update(kwds)

    for kwd, value in new_vals.items():
        if d.get(kwd) is not value:
            break
    else:
        return d

    d = d.copy()
    d.update(new_vals)
    return d


def pure_add(s, elem):
    if elem in s:
        return s
    s = s.copy()
    s.add(elem)
    return s
