"""Pages, panels and their controls.

A page is a list of panels. A panel names:

* ``kind``: which renderer in static/site.js draws it (e.g. "phase-linked");
  a new panel of an existing kind needs no JavaScript
* ``controls``: the selectors above it; their values form the data path
* ``data``: a path template such as "data/phase/{ds}.json"
* ``build``: a Python function that returns the JSON for one choice of
  control values

The builder (enso.build) calls ``build`` for every combination of control
values and writes the result to ``data``. Adding a dataset to a selector is
adding an Option; adding a panel is adding a Panel to a page; adding a page
is adding a module to enso.site.pages and listing it in PAGES there.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    group: str = ""     # <optgroup> label; options with the same group sit together


@dataclass(frozen=True)
class Control:
    name: str           # URL query key and data path placeholder
    label: str
    options: list[Option]
    default: str

    def __post_init__(self):
        values = [o.value for o in self.options]
        if len(set(values)) != len(values):
            raise ValueError(f"control {self.name!r} has duplicate option values")
        if self.default not in values:
            raise ValueError(f"control {self.name!r}: default {self.default!r} is not an option")

    def groups(self) -> list[tuple[str, list[Option]]]:
        """Options grouped for <optgroup>, in first-seen group order."""
        out: dict[str, list[Option]] = {}
        for o in self.options:
            out.setdefault(o.group, []).append(o)
        return list(out.items())


@dataclass
class Panel:
    id: str
    kind: str
    title: str
    data: str
    build: Callable[..., dict]
    controls: list[Control] = field(default_factory=list)
    caption: str = ""

    def choices(self):
        """Every combination of control values, as dicts."""
        names = [c.name for c in self.controls]
        for combo in itertools.product(*[[o.value for o in c.options] for c in self.controls]):
            yield dict(zip(names, combo))

    def path_for(self, choice: dict) -> str:
        return self.data.format(**choice)


@dataclass
class Page:
    slug: str           # output file stem; "index" for the landing page
    title: str
    nav_label: str
    intro: str
    panels: list[Panel]
    template: str = "page.html"
    notes_html: str = ""   # longer explanation, shown collapsed

    @property
    def filename(self) -> str:
        return f"{self.slug}.html"
