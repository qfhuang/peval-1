def pure_function(fn):
    ''' Mark function as pure - it has no important for us side effects
    (does not mutate arguments, global state, do IO, etc.),
    and depends only on its arguments.
    '''
    fn._peval_is_pure = True
    return fn


def inline(fn):
    ''' Mark that it is safe to inline this function in all call sites
    '''
    fn._peval_inline = True
    return fn
