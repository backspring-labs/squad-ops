"""
Factory for creating auth adapter instances from configuration (SIP-0062).

Maps provider strings to concrete adapter instances.
Called from startup/bootstrap code, not from core domain.
"""

from __future__ import annotations

from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort


def create_auth_provider(
    provider: str,
    *,
    secret_manager=None,
    **config,
) -> AuthPort:
    """Create an AuthPort instance for the given provider.

    Args:
        provider: Provider type ('keycloak').
        secret_manager: Optional SecretManager for resolving secret:// references
            (SIP-0062 Section 6.6 signature). Currently unused because the config
            loader resolves all secret:// references before this factory is called.
        **config: Provider-specific configuration.

    Returns:
        AuthPort instance.

    Raises:
        ValueError: If provider is 'disabled' or unknown.
    """
    if provider == "disabled":
        raise ValueError(
            "Cannot create auth provider for 'disabled'. "
            "Caller should handle disabled mode before calling factory."
        )
    if provider == "keycloak":
        from adapters.auth.keycloak.auth_adapter import KeycloakAuthAdapter

        return KeycloakAuthAdapter(**config)
    raise ValueError(f"Unknown auth provider: {provider}")


def create_authorization_provider(
    provider: str,
    **config,
) -> AuthorizationPort:
    """Create an AuthorizationPort instance for the given provider.

    Args:
        provider: Provider type ('keycloak').
        **config: Provider-specific configuration.

    Returns:
        AuthorizationPort instance.

    Raises:
        ValueError: If provider is 'disabled' or unknown.
    """
    if provider == "disabled":
        raise ValueError(
            "Cannot create authorization provider for 'disabled'. "
            "Caller should handle disabled mode before calling factory."
        )
    if provider == "keycloak":
        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter

        return KeycloakAuthzAdapter(**config)
    raise ValueError(f"Unknown auth provider: {provider}")


def create_service_token_client(
    service_name: str,
    service_config,
    oidc_config,
    secret_manager=None,
):
    """Create a ServiceTokenClient for service-to-service auth.

    Args:
        service_name: Logical name of the service.
        service_config: ServiceClientConfig with client_id and client_secret.
        oidc_config: OIDCConfig with issuer_url.
        secret_manager: Optional SecretManager for resolving secret:// references.

    Returns:
        ServiceTokenClient instance.

    Raises:
        ValueError: If secret resolution fails.
    """
    from squadops.auth.client_credentials import ServiceTokenClient

    client_secret = service_config.client_secret
    if secret_manager and client_secret.startswith("secret://"):
        client_secret = secret_manager.resolve(client_secret)

    token_endpoint = oidc_config.issuer_url.rstrip("/") + "/protocol/openid-connect/token"

    return ServiceTokenClient(
        token_endpoint=token_endpoint,
        client_id=service_config.client_id,
        client_secret=client_secret,
    )
