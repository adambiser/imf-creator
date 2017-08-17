import inspect

class Signal:
    """A simple event system.

    Based on: https://stackoverflow.com/posts/35957226/revisions
    """
    def __init__(self, **args):
        self._args = args
        self._argnames = set(args.keys())
        self._listeners = []

    def _args_string(self):
        if len(self._argnames) == 0:
            return "(no arguments)"
        return ", ".join(sorted(self._argnames))

    def __iadd__(self, listener):
        args = inspect.getargspec(listener).args
        if "self" in args:
            args.remove("self")
        if set(n for n in args) != self._argnames:
            raise ValueError("Listener must have these arguments: {}".format(self._args_string()))
        self._listeners.append(listener)
        return self

    def __isub__(self, listener):
        self._listeners.remove(listener)
        return self

    def __call__(self, *args, **kwargs):
        if args or set(kwargs.keys()) != self._argnames:
            raise ValueError("This Signal requires these arguments: {}".format(self._args_string()))
        for listener in self._listeners:
            listener(**kwargs)