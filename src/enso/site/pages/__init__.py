"""Page modules, in navigation order. Each exposes ``page(cfg) -> Page``.

To add a page: write a module here with a ``page`` function and append it
to PAGE_MODULES.
"""

from enso.site.pages import compare, duffing, phase

PAGE_MODULES = [phase, compare, duffing]


def all_pages(cfg):
    return [m.page(cfg) for m in PAGE_MODULES]
