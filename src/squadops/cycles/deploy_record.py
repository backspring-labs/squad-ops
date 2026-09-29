"""What a deploy put in service: each service's image, and the model weights the profiles name (#1720).

#80 stamps a cycle with the runtime API's own commit. That names one service. On 1.8.2's deploy
A′ the agents ran another commit's images while every cycle recorded the runtime's, and nothing
on record could show it; a model re-pulled under the same tag is the same blind spot for the
weights. A deploy record is the Helm-style answer: each deploy writes one numbered record of
exactly what it put in service, and a cycle references the record current when it was created.

The deploy step writes it, because only the host can read a container's image: the runtime API
has no Docker access, and a container cannot reliably read its own image ID.
``rebuild_and_deploy.sh`` gathers each service's image and revision label and hands them to
``python -m squadops.api.runtime.record_deploy``, run in the runtime image, which adds the model
digests and writes through ``DeployRegistryPort``.

Unknown stays unknown: a service whose image carries no revision label, and a model the provider
reports without a digest, record ``None``, never a guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class DeployFactsError(ValueError):
    """The deploy step handed over facts the record cannot be built from."""


@dataclass(frozen=True)
class ServiceImage:
    """One service as the deploy left it running."""

    service: str
    image_id: str
    #: The image's ``org.opencontainers.image.revision`` label: #80's source hash, ``-dirty``
    #: from a modified tree, or ``None`` when the image carries none (not built by the script).
    revision: str | None


@dataclass(frozen=True)
class ModelWeights:
    """A model a squad profile names, and the weights the provider served under that name."""

    model: str
    #: ``None`` when the provider does not report a digest, or does not serve the model at all.
    digest: str | None


@dataclass(frozen=True)
class DeployRecord:
    deploy_id: str
    recorded_at: datetime
    #: What wrote it: the deploy script and its target, e.g. ``rebuild_and_deploy.sh all``.
    recorded_by: str
    #: The checkout the deploy built from (``source_hash.sh``), or ``None`` outside a checkout.
    source_revision: str | None
    services: tuple[ServiceImage, ...]
    models: tuple[ModelWeights, ...]

    def service(self, name: str) -> ServiceImage | None:
        return next((s for s in self.services if s.service == name), None)


def services_from_facts(facts: Mapping[str, Any]) -> tuple[ServiceImage, ...]:
    """The deploy step's ``services`` list, validated: every entry names a service and an image.

    Raises:
        DeployFactsError: no services, or an entry without a service name or image ID. A record
            that silently dropped a service would claim a deploy it did not describe.
    """
    raw = facts.get("services")
    if not isinstance(raw, list) or not raw:
        raise DeployFactsError("the deploy facts carry no services")
    services: list[ServiceImage] = []
    for entry in raw:
        name, image_id = entry.get("service"), entry.get("image_id")
        if not name or not image_id:
            raise DeployFactsError(f"a service entry lacks its name or image: {entry!r}")
        revision = (entry.get("revision") or "").strip()
        services.append(
            ServiceImage(
                service=name,
                image_id=image_id,
                revision=revision if revision and revision != "unknown" else None,
            )
        )
    return tuple(sorted(services, key=lambda s: s.service))


def model_weights(named: set[str], digests: Mapping[str, str | None]) -> tuple[ModelWeights, ...]:
    """Each model a profile names, with the digest the provider reported for it, if any."""
    return tuple(ModelWeights(model=m, digest=digests.get(m)) for m in sorted(named))
