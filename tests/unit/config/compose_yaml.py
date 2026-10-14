"""Compose files as compose reads them, for the tests that parse them. Not a test module.

``!override`` and ``!reset`` say how an overlay's value merges with the file before it, not what the
value is. ``yaml.safe_load`` refuses an unknown tag outright, so a guard that reads every
``docker-compose*.yml`` would stop at the first overlay that uses one (docker-compose.tensorfold.yml).
"""

from __future__ import annotations

from pathlib import Path

import yaml


class ComposeLoader(yaml.SafeLoader):
    """A safe loader that reads compose's merge tags as the value they carry."""


def _value(loader: yaml.SafeLoader, node: yaml.Node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


for _tag in ("!override", "!reset"):
    ComposeLoader.add_constructor(_tag, _value)


def load_compose(text: str) -> dict:
    return yaml.load(text, Loader=ComposeLoader) or {}


def compose_services(path: Path) -> dict:
    return load_compose(path.read_text()).get("services") or {}
