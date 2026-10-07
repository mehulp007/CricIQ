"""Model groups: which competitions one set of models learns from and serves.

Each group (``config/model_groups.yaml``) trains only on its own competitions,
from a copy of the warehouse holding just them, and serves only them: the IPL,
the other T20 leagues together, T20 internationals and ODIs each have models of
their own. The pipeline builds each group's copy; the models package trains,
scores and reports one group at a time (``criciq_ml.formats.use_group``).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from criciq_core import paths


class ModelGroup(BaseModel):
    id: str
    format: str
    competitions: list[str]
    copy_name: str
    models: str
    config: str
    pointer: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _defaults(cls, data: dict[str, object]) -> dict[str, object]:
        data = dict(data)
        data["copy_name"] = data.pop("copy", None) or str(data["id"]).upper()
        data.setdefault("models", data["id"])
        data.setdefault("config", data["id"])
        return data

    def covers(self, competitions: list[str] | set[str]) -> bool:
        """Whether every one of ``competitions`` belongs to this group."""
        return bool(competitions) and set(competitions) <= set(self.competitions)


class ModelGroups(BaseModel):
    groups: list[ModelGroup]

    @model_validator(mode="after")
    def _distinct(self) -> ModelGroups:
        ids = [g.id for g in self.groups]
        if len(set(ids)) != len(ids):
            raise ValueError("model group ids must be distinct")
        owners: dict[str, str] = {}
        for g in self.groups:
            for c in g.competitions:
                if c in owners:
                    raise ValueError(f"{c} is in two model groups ({owners[c]}, {g.id})")
                owners[c] = g.id
        return self

    def get(self, group_id: str) -> ModelGroup:
        for g in self.groups:
            if g.id == group_id.lower():
                return g
        raise KeyError(f"unknown model group {group_id!r}")

    def of(self, competition: str) -> ModelGroup | None:
        """The group serving ``competition`` (None if no group does)."""
        for g in self.groups:
            if competition.upper() in g.competitions:
                return g
        return None


def load_model_groups(path: Path | None = None) -> ModelGroups:
    source = path or paths.config_dir() / "model_groups.yaml"
    return ModelGroups.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))


@cache
def model_groups() -> ModelGroups:
    return load_model_groups()


def group(group_id: str) -> ModelGroup:
    return model_groups().get(group_id)


def group_of(competition: str) -> ModelGroup | None:
    return model_groups().of(competition)
