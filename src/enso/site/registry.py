"""Pages, panels and their controls.

A page is a list of panels. A panel names:

* ``kind``: which renderer in static/site.js draws it (e.g. "phase-linked");
  a new panel of an existing kind needs no JavaScript
* ``controls``: the selectors above it; their values form the data path
* ``data``: a path template such as "data/phase/{ds}.json"
* ``build``: a Python function that returns the JSON for one choice of
  control values

The builder (enso.build) calls ``build`` for every combination of the
control values the ``data`` template names, page-level controls included,
and writes each result to its path. A panel that needs another layout of
files (Compare: one file per dataset, combined in the browser) gives
``files`` instead. Adding a dataset to a selector is adding an Option;
adding a panel is adding a Panel to a page; adding a page is adding a module
to enso.site.pages and listing it in PAGE_MODULES there.
"""

from __future__ import annotations

import itertools
import string
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
    play: bool = False      # a play button steps through the options

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
    build: Callable[..., dict] | None = None
    controls: list[Control] = field(default_factory=list)
    caption: str = ""
    files: Callable[[], dict[str, Callable[[], dict]]] | None = None

    def placeholders(self) -> list[str]:
        return [name for _, name, _, _ in string.Formatter().parse(self.data) if name]

    def choices(self, page_controls: list[Control] = ()):
        """Every combination of the control values the data path uses."""
        used = set(self.placeholders())
        controls = [c for c in [*page_controls, *self.controls] if c.name in used]
        missing = used - {c.name for c in controls}
        if missing:
            raise ValueError(f"panel {self.id!r}: no control for {sorted(missing)}")
        names = [c.name for c in controls]
        for combo in itertools.product(*[[o.value for o in c.options] for c in controls]):
            yield dict(zip(names, combo))

    def path_for(self, choice: dict) -> str:
        return self.data.format(**choice)

    def outputs(self, page_controls: list[Control] = ()) -> dict[str, Callable[[], dict]]:
        """Relative path -> function returning that file's JSON."""
        if self.files is not None:
            return self.files()
        return {self.path_for(c): (lambda c=c: self.build(**c)) for c in self.choices(page_controls)}


@dataclass
class Page:
    slug: str           # output file stem; "index" for the landing page
    title: str
    nav_label: str
    intro: str
    panels: list[Panel]
    template: str = "page.html"
    notes_html: str = ""   # longer explanation, shown collapsed
    controls: list[Control] = field(default_factory=list)  # shared by all panels
    attrs: dict = field(default_factory=dict)              # extra data-* on <main>

    @property
    def filename(self) -> str:
        return f"{self.slug}.html"
