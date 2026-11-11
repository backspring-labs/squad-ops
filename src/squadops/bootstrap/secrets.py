"""The secrets provider the composition root hands the config loader (#154).

``load_config`` resolves ``secret://`` references through a ``SecretProvider`` it is GIVEN;
which provider that is — env, file, docker secret — is an adapter choice, and the loader
used to import ``adapters.secrets.factory`` to make it, a domain → adapters import. The
choice now lives here, in the bootstrap package, and the two composition roots that load
the framework config (the runtime API and the agent entrypoint) pass it in.
"""

from __future__ import annotations

from squadops.config.env_section import section_from_env
from squadops.config.schema import SecretsConfig
from squadops.core.secrets import SecretManager
from squadops.ports.secrets import SecretProvider

_SECRETS_PREFIX = "SQUADOPS__SECRETS__"


def secret_provider_for(secrets_config: SecretsConfig) -> SecretProvider:
    """The provider the ``secrets`` section selects."""
    from adapters.secrets.factory import create_provider

    return create_provider(
        provider=secrets_config.provider,
        env_prefix=secrets_config.env_prefix,
        file_dir=secrets_config.file_dir,
    )


def secret_manager_from_env() -> SecretManager | None:
    """The manager for the provider the ``SQUADOPS__SECRETS__*`` variables select, or ``None``
    when they select none (#1982).

    For a root that loads only its own config section (the sandbox service, the
    remote-execution worker). Only the provider's selection is read, so such a process resolves
    the references it is given and holds no other platform secret.
    """
    values = section_from_env(_SECRETS_PREFIX, SecretsConfig.model_fields)
    if not values:
        return None
    secrets = SecretsConfig.model_validate(values)
    return SecretManager(provider=secret_provider_for(secrets), name_map=secrets.name_map or {})
