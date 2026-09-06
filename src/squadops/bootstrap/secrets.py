"""The secrets provider the composition root hands the config loader (#154).

``load_config`` resolves ``secret://`` references through a ``SecretProvider`` it is GIVEN;
which provider that is — env, file, docker secret — is an adapter choice, and the loader
used to import ``adapters.secrets.factory`` to make it, a domain → adapters import. The
choice now lives here, in the bootstrap package, and the two composition roots that load
the framework config (the runtime API and the agent entrypoint) pass it in.
"""

from __future__ import annotations

from squadops.config.schema import SecretsConfig
from squadops.ports.secrets import SecretProvider


def secret_provider_for(secrets_config: SecretsConfig) -> SecretProvider:
    """The provider the ``secrets`` section selects."""
    from adapters.secrets.factory import create_provider

    return create_provider(
        provider=secrets_config.provider,
        env_prefix=secrets_config.env_prefix,
        file_dir=secrets_config.file_dir,
    )
