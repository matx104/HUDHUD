"""One way to sign in to Azure, wherever the court runs. No keys anywhere.

In Azure (Container Apps sets IDENTITY_ENDPOINT, and AZURE_CLIENT_ID names the app's identity)
the court signs in as its managed identity. On a laptop it signs in as the project's Azure CLI,
pinned to the project's tenant, so a CLI signed in to another account fails loudly instead of
reaching the wrong subscription.
"""

import os
from typing import Any


def in_azure() -> bool:
    return bool(os.environ.get("IDENTITY_ENDPOINT") or os.environ.get("MSI_ENDPOINT"))


def credential(*, aio: bool = False) -> Any:
    """A token credential for Foundry, Cosmos DB and Application Insights."""
    if in_azure():
        if aio:
            from azure.identity.aio import ManagedIdentityCredential
        else:
            from azure.identity import ManagedIdentityCredential
        return ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID") or None)
    if aio:
        from azure.identity.aio import AzureCliCredential
    else:
        from azure.identity import AzureCliCredential
    return AzureCliCredential(tenant_id=os.environ.get("AZURE_TENANT_ID") or None)
