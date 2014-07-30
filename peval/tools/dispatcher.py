import ast
import types


class Dispatcher:
    """
    A dispatcher that maps a call to a group of functions
    based on the type of the first argument
    (hardcoded to be an AST node at the moment).

    ``handler_obj`` can be either a function with the signature::

            def handler(node, *args, **kwds)

    or a class with the static methods::

        @staticmethod
        def handle_<tp>(node, *args, **kwds)

    where ``<tp>`` is the name of the type that this function will handle
    (e.g., ``handle_FunctionDef`` for ``ast.FunctionDef``).
    The class can also define the default handler::

        @staticmethod
        def handle(node, *args, **kwds)

    If it is not defined, the ``default_handler`` value will be used
    (which must be a function with the same signature as above).
    If neither ``handle`` exists or ``default_handler`` is provided,
    a ``ValueError`` is thrown.
    """

    def __init__(self, handler_obj, default_handler=None):
        if isinstance(handler_obj, types.FunctionType):
            self._handlers = {}
            self._default_handler = handler_obj
        else:
            handler_prefix = 'handle'
            if hasattr(handler_obj, handler_prefix):
                self._default_handler = getattr(handler_obj, handler_prefix)
            elif default_handler is not None:
                self._default_handler = default_handler
            else:
                raise ValueError("Default handler was not provided")

            self._handlers = {}
            attr_prefix = handler_prefix + '_'
            for attr in vars(handler_obj):
                if attr.startswith(attr_prefix):
                    typename = attr[len(attr_prefix):]
                    if hasattr(ast, typename):
                        self._handlers[getattr(ast, typename)] = getattr(handler_obj, attr)

    def __call__(self, node, *args, **kwds):
        handler = self._handlers.get(type(node), self._default_handler)
        return handler(node, *args, **kwds)
