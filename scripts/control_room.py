"""The control room: deploy the HUDHUD workbook, and write the portal links for the local page.

The workbook (infra/monitor/hudhud-workbook.json) holds no IDs; this script binds it to the
Application Insights resource and deploys it under a fixed name, so a rerun updates it in place.
The links go to site/data/ops.local.js, which git ignores: they carry the subscription's IDs, and
they only open for someone signed in to it anyway. The showcase site shows its Control room page
only when served from this machine and that file exists.

    make control-room       # then: make site, and open http://localhost:8000/#/control
"""

import base64
import gzip
import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from _azure import GROUP, ROOT, az

WORKBOOK = ROOT / "infra" / "monitor" / "hudhud-workbook.json"
OUT = ROOT / "site" / "data" / "ops.local.js"
# A fixed name: Azure wants a GUID, and the same one each run updates the workbook in place.
WORKBOOK_NAME = str(uuid.uuid5(uuid.NAMESPACE_URL, "hudhud/control-room"))

ALERTS = """dependencies
| where name startswith "alert "
| project timestamp,
    minute = tostring(customDimensions["hudhud.minute"]),
    kind = tostring(customDimensions["hudhud.alert.kind"]),
    outcome = tostring(customDimensions["hudhud.outcome"]),
    attempts = toint(customDimensions["hudhud.attempts"]),
    refused_for = tostring(customDimensions["hudhud.rejection_codes"]),
    operation_Id
| order by timestamp desc"""

MODEL_CALLS = """dependencies
| where name startswith "chat "
| project timestamp, model = tostring(customDimensions["gen_ai.request.model"]),
    seconds = round(duration / 1000, 2),
    input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"]),
    reasoning_tokens = toint(customDimensions["gen_ai.usage.reasoning.output_tokens"]),
    success, operation_Id
| order by timestamp desc"""

MATCHES = """requests
| where name == "match"
| project timestamp, match = tostring(customDimensions["hudhud.match_id"]),
    narrator = tostring(customDimensions["hudhud.narrator"]),
    aired = toint(customDimensions["hudhud.aired"]),
    alerts = toint(customDimensions["hudhud.alerts"]),
    cost_usd = todouble(customDimensions["hudhud.cost_usd"]),
    seconds = round(duration / 1000, 1), operation_Id
| order by timestamp desc"""


def resource_id(*args: str) -> str:
    return az(*args, "-g", GROUP, "--query", "id", "-o", "tsv")


def deploy_workbook(subscription: str, insights_id: str, location: str) -> str:
    workbook = json.loads(WORKBOOK.read_text())
    workbook["fallbackResourceIds"] = [insights_id]
    path = f"/subscriptions/{subscription}/resourceGroups/{GROUP}"
    path += f"/providers/Microsoft.Insights/workbooks/{WORKBOOK_NAME}"
    body = {
        "location": location,
        "kind": "shared",
        "tags": {"project": "hudhud", "owner": "monarch"},
        "properties": {
            "displayName": "HUDHUD control room",
            "category": "workbook",
            "sourceId": insights_id.lower(),
            "serializedData": json.dumps(workbook),
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(body, handle)
    url = f"https://management.azure.com{path}?api-version=2023-06-01"
    az("rest", "--method", "put", "--url", url, "--body", f"@{handle.name}", "-o", "none")
    Path(handle.name).unlink()
    return path


def main() -> None:
    account = json.loads(az("account", "show", "-o", "json"))
    subscription, tenant = account["id"], account["tenantId"]
    domain = account.get("tenantDefaultDomain") or tenant
    insights = resource_id(
        "monitor", "app-insights", "component", "show", "--app", "hudhud-insights"
    )
    logs = resource_id("monitor", "log-analytics", "workspace", "show", "-n", "hudhud-logs")
    foundry = resource_id("cognitiveservices", "account", "show", "-n", "hudhud-foundry")
    cosmos = resource_id("cosmosdb", "show", "-n", "hudhud-audit")
    studio = resource_id("containerapp", "show", "-n", "hudhud-studio")
    fqdn = "properties.configuration.ingress.fqdn"
    studio_url = "https://" + az(
        "containerapp", "show", "-n", "hudhud-studio", "-g", GROUP, "--query", fqdn, "-o", "tsv"
    )
    location = az(
        "monitor",
        "app-insights",
        "component",
        "show",
        "--app",
        "hudhud-insights",
        "-g",
        GROUP,
        "--query",
        "location",
        "-o",
        "tsv",
    )
    workbook = deploy_workbook(subscription, insights, location)
    print(f"workbook deployed: HUDHUD control room ({WORKBOOK_NAME})")

    portal = f"https://portal.azure.com/#@{domain}"
    group = f"{portal}/resource/subscriptions/{subscription}/resourceGroups/{GROUP}"

    def res(resource: str, blade: str = "overview") -> str:
        return f"{portal}/resource{resource}/{blade}"

    def query(resource: str, kql: str) -> str:
        """A Logs link that opens with the query already run, as the portal's share links do."""
        packed = base64.b64encode(gzip.compress(kql.encode())).decode()
        return (
            f"{portal}/blade/Microsoft_OperationsManagementSuite_Workspace/Logs.ReactView"
            f"/resourceId/{quote(resource, safe='')}/source/LogsBlade.AnalyticsShareLinkToQuery"
            f"/q/{quote(packed, safe='')}/timespan/P1D"
        )

    groups = [
        (
            "The live studio",
            [
                ("Open the studio", "The live match the judges see", studio_url),
                ("Container app", "hudhud-studio: revision, replica, identity", res(studio)),
                ("App metrics", "Requests, CPU and memory of the studio", res(studio, "metrics")),
            ],
        ),
        (
            "The dashboard",
            [
                (
                    "HUDHUD control room",
                    "The workbook: outcomes, refusals, model cost and latency",
                    res(workbook, "workbook"),
                ),
                (
                    "Application map",
                    "The court, Foundry and Cosmos DB, and the calls between them",
                    res(insights, "applicationMap"),
                ),
            ],
        ),
        (
            "Money",
            [
                (
                    "Cost analysis",
                    "What rg-hudhud has cost, by service and day",
                    f"{group}/costanalysis",
                ),
                (
                    "Budget",
                    "The $100 credit budget and its alerts",
                    f"{portal}/resource/subscriptions/{subscription}/budgets",
                ),
                (
                    "Student credit",
                    "Azure for Students: credit left and expiry",
                    "https://portal.azure.com/#view/Microsoft_Azure_Education/EducationMenuBlade/~/overview",
                ),
                (
                    "Cost per match",
                    "Every match, its cues and its model cost",
                    query(insights, MATCHES),
                ),
            ],
        ),
        (
            "AI at work",
            [
                (
                    "Every model call",
                    "Model, seconds, input, output and reasoning tokens",
                    query(insights, MODEL_CALLS),
                ),
                (
                    "Every alert and its verdict",
                    "Aired, refused or spiked, and the Critic's reasons",
                    query(insights, ALERTS),
                ),
                ("Foundry resource", "hudhud-foundry: deployments, keys off", res(foundry)),
                (
                    "Model metrics",
                    "Requests, tokens and latency as Foundry counts them",
                    res(foundry, "metrics"),
                ),
                (
                    "Foundry portal",
                    "The project, its models and traces",
                    f"https://ai.azure.com/?tid={tenant}",
                ),
            ],
        ),
        (
            "App health",
            [
                ("Performance", "Match and model-call durations", res(insights, "performance")),
                ("Failures", "Every failed call, grouped", res(insights, "failures")),
                ("Logs", "Application Insights logs, to write any query", res(insights, "logs")),
            ],
        ),
        (
            "Data",
            [
                ("Audit trail", "hudhud-audit: Cosmos DB, free tier, keys off", res(cosmos)),
                (
                    "Data Explorer",
                    "Browse the audit records, match by match",
                    res(cosmos, "dataExplorer"),
                ),
                (
                    "Microsoft Fabric",
                    "The workspace that mirrors the audit trail",
                    "https://app.fabric.microsoft.com/home",
                ),
                ("Log Analytics", "hudhud-logs: retention and the daily cap", res(logs)),
            ],
        ),
        (
            "Everything",
            [
                ("Resource group", "rg-hudhud: every resource in one list", f"{group}/overview"),
                (
                    "Code and CI",
                    "The repository's tests and deploys",
                    "https://github.com/matx104/HUDHUD/actions",
                ),
            ],
        ),
    ]
    data = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "groups": [
            {
                "title": title,
                "links": [{"label": label, "detail": d, "href": h} for label, d, h in links],
            }
            for title, links in groups
        ],
    }
    header = "// Generated by scripts/control_room.py. Git-ignored: the links carry the IDs.\n"
    OUT.write_text(f"{header}window.OPS = {json.dumps(data, indent=2)};\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {sum(len(g['links']) for g in data['groups'])} links")


if __name__ == "__main__":
    main()
