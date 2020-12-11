"""A simple event system."""
import inspect


class Signal:
    """A simple event system.

    Based on: https://stackoverflow.com/posts/35957226/revisions
    """

    def __init__(self, **args):
        self._args = args
        self._arg_names = set(args.keys())
        self._listeners = []

    def _args_string(self):
        if len(self._arg_names) == 0:
            return "(no arguments)"
        return ", ".join([f"{a}: {self._args[a].__name__}" for a in sorted(self._arg_names)])

    def add_handler(self, listener: callable):
        args = inspect.getfullargspec(listener).args
        if "self" in args:
            args.remove("self")
        if set(n for n in args) != self._arg_names:
            raise ValueError(f"Listener must have these arguments: {self._args_string()}")
        self._listeners.append(listener)

    def remove_handler(self, listener):
        self._listeners.remove(listener)

    def trigger(self, *args, **kwargs):
        if args or set(kwargs.keys()) != self._arg_names:
            raise ValueError(f"Signal trigger must have these arguments: {self._args_string()}")
        for listener in self._listeners:
            listener(**kwargs)

    def __call__(self, *args, **kwargs):
        self.trigger(*args, **kwargs)
