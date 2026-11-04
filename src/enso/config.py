"""Typed view of config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"
SERIES_DIR = ROOT / "data" / "series"
DOCS_DIR = ROOT / "docs"

QUANTITIES = ("absolute", "anomaly", "record_mean")
CADENCES = {"monthly": "month"}  # cadence -> time step name used in units


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    unit: str


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    long_label: str
    group: Group
    quantity: str
    cadence: str
    source: dict

    @property
    def step(self) -> str:
        return CADENCES[self.cadence]

    @property
    def unit(self) -> str:
        return self.group.unit

    @property
    def rate_unit(self) -> str:
        return f"{self.unit}/{self.step}"


@dataclass(frozen=True)
class Event:
    label: str
    start: str          # "YYYY-MM", inclusive
    end: str | None     # None: still running, up to the latest month


@dataclass(frozen=True)
class CurrentEvent:
    label: str
    dataset: str
    threshold: float


@dataclass(frozen=True)
class FilterParams:
    HN1: float
    HN2: float
    NDOTS: int
    window_start: str | None
    window_end: str | None
    base_year: int
    provisional_months: int


@dataclass(frozen=True)
class Config:
    filter: FilterParams
    groups: dict[str, Group]
    datasets: list[Dataset]
    events: list[Event]
    current_event: CurrentEvent | None = None
    models: dict = field(default_factory=dict)
    site: dict = field(default_factory=dict)
    weekly: dict = field(default_factory=dict)

    def dataset(self, key: str) -> Dataset:
        for ds in self.datasets:
            if ds.key == key:
                return ds
        raise KeyError(f"unknown dataset {key!r}")


def load_config(path: Path | str = CONFIG_PATH) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    f = raw["filter"]
    w = f.get("window") or {}
    params = FilterParams(
        HN1=float(f["HN1"]),
        HN2=float(f["HN2"]),
        NDOTS=int(f["NDOTS"]),
        window_start=w.get("start"),
        window_end=w.get("end"),
        base_year=int(w.get("base_year", 1975)),
        provisional_months=int(f.get("provisional_months", 0)),
    )
    groups = {k: Group(k, v["label"], v["unit"]) for k, v in raw["groups"].items()}

    datasets = []
    seen = set()
    for d in raw["datasets"]:
        if d["key"] in seen:
            raise ValueError(f"duplicate dataset key {d['key']!r}")
        seen.add(d["key"])
        if d["quantity"] not in QUANTITIES:
            raise ValueError(f"{d['key']}: quantity must be one of {QUANTITIES}")
        if d.get("cadence", "monthly") not in CADENCES:
            raise ValueError(f"{d['key']}: cadence must be one of {tuple(CADENCES)}")
        datasets.append(Dataset(
            key=d["key"],
            label=d["label"],
            long_label=d.get("long_label", d["label"]),
            group=groups[d["group"]],
            quantity=d["quantity"],
            cadence=d.get("cadence", "monthly"),
            source=dict(d["source"]),
        ))

    events = [Event(e["label"], str(e["start"]), None if e.get("end") is None else str(e["end"]))
              for e in raw.get("events", [])]
    ce = raw.get("current_event")
    current = CurrentEvent(ce["label"], ce["dataset"], float(ce["threshold"])) if ce else None
    if current and current.label not in {e.label for e in events}:
        raise ValueError(f"current_event {current.label!r} is not listed under events")
    return Config(params, groups, datasets, events, current,
                  raw.get("models", {}), raw.get("site", {}), raw.get("weekly", {}))
