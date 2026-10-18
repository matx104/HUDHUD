"""Telemetry: the agents' traces in Application Insights, signed in with Entra ID.

Agent Framework traces its own work (`invoke_agent` and `chat <model>` spans carrying gen_ai token
counts). The court adds a span per match (a consumer of the event stream, so Application Insights
lists it under requests) and a span per alert recording what became of it: aired verified,
detection-only or spiked, the attempts, and the Critic's rejection codes. Prompts and model output
are never recorded: Agent Framework's sensitive-data capture stays off.

With APPLICATIONINSIGHTS_CONNECTION_STRING unset nothing is configured, and every span is a no-op.
The resource has local auth disabled, so the exporter signs in with the project's Azure CLI and
needs Monitoring Metrics Publisher on it (docs/azure.md).

    pip install -e "apps/api[telemetry]"    # azure-monitor-opentelemetry, azure-identity
"""

import os

from opentelemetry import metrics, trace

from .config import product_name

tracer = trace.get_tracer("court")


def configure(service: str = "court") -> bool:
    """Export traces to Application Insights when a connection string is set. Call once."""
    connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection:
        return False
    from azure.identity import AzureCliCredential
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.sdk.resources import Resource

    configure_azure_monitor(
        connection_string=connection,
        credential=AzureCliCredential(tenant_id=os.environ.get("AZURE_TENANT_ID") or None),
        resource=Resource.create(
            {"service.name": service, "service.namespace": product_name().lower()}
        ),
        sampling_ratio=1.0,  # a match is a few hundred spans: keep them all
        enable_live_metrics=False,
        enable_performance_counters=False,
    )
    return True


def flush() -> None:
    """Send what's buffered before a short-lived process exits."""
    for provider in (trace.get_tracer_provider(), metrics.get_meter_provider()):
        if hasattr(provider, "force_flush"):
            provider.force_flush()
