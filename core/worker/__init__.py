"""Lazy public surface for Core worker modules.

Importing the old package eagerly loaded FFDec and started the JVM.  On
Windows the Loader UI is also imported by ``multiprocessing.spawn``; that
meant the UI process and its child could initialise JPype concurrently before
the child dispatcher had even started.
"""

from importlib import import_module


_MODULES = {
    "brawlhalla", "config", "dispatch", "gamefiles", "gameswf", "mod",
    "modloader", "basemod",
}

_ATTR_MODULES = (
    ".dispatch", ".mod", ".modloader", ".brawlhalla", ".gameswf",
    ".gamefiles", ".basemod",
)


def __getattr__(name):
    if name in _MODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module

    for module_name in _ATTR_MODULES:
        module = import_module(module_name, __name__)
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | _MODULES)
