"""Shared by the utility scripts: the project's Azure CLI, and the names of what it runs.

Every script signs in the way scripts/az does: the Linux CLI with its own config folder, never the
machine's default az. The Azure SDKs inside the court use the same sign-in through this module.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GROUP = "rg-hudhud"
STUDIO_APP = "hudhud-studio"
CONFIG = (ROOT / "site" / "config.js").read_text()
# The showcase site's address, from the one place it's set (site/config.js, siteUrl).
SITE_URL = re.search(r'siteUrl: "([^"]+)"', CONFIG)[1]
# The studio's address for people, behind the wall (studioUrl). Its Azure address refuses them.
STUDIO_URL = re.search(r'studioUrl: "([^"]+)"', CONFIG)[1]
# The Access service token that lets scripts and MCP clients through the wall, kept on the owner's
# machine only (docs/azure.md, "The wall").
ACCESS_TOKEN = Path.home() / ".config" / "hudhud" / "access-token.json"


class AzureError(RuntimeError):
    """An az command failed; the message is what Azure said."""


def az(*args: str) -> str:
    done = subprocess.run([str(ROOT / "scripts" / "az"), *args], capture_output=True, text=True)
    if done.returncode:
        said = [line for line in done.stderr.splitlines() if line.strip() and "WARNING" not in line]
        raise AzureError(
            f"az {args[0]} {args[1] if len(args) > 1 else ''}: " + " ".join(said)[-500:]
        )
    return done.stdout.strip()


def az_json(*args: str) -> Any:
    return json.loads(az(*args, "-o", "json") or "null")


def use_project_cli() -> None:
    """Point the Azure SDKs' CLI credential at the project's sign-in, tenant pinned."""
    os.environ.setdefault("AZURE_CONFIG_DIR", str(Path.home() / ".azure-hudhud"))
    os.environ["PATH"] = f"{Path.home() / '.local' / 'bin'}:{os.environ['PATH']}"
    os.environ.setdefault(
        "AZURE_TENANT_ID", az("account", "show", "--query", "tenantId", "-o", "tsv")
    )


def studio_url() -> str:
    """The studio's address: its own domain once one is bound, else the one Azure gave it."""
    ingress = az_json(
        "containerapp", "show", "-n", STUDIO_APP, "-g", GROUP,
        "--query", "properties.configuration.ingress",
    )  # fmt: skip
    bound = [
        d["name"] for d in ingress.get("customDomains") or [] if d.get("bindingType") != "Disabled"
    ]
    return f"https://{bound[0] if bound else ingress['fqdn']}/"


def through_the_wall() -> dict[str, str]:
    """Request headers that get a script past Cloudflare Access: the service token, and a name,
    since Cloudflare turns away Python's default User-Agent."""
    token = json.loads(ACCESS_TOKEN.read_text())
    return {
        "CF-Access-Client-Id": token["client_id"],
        "CF-Access-Client-Secret": token["client_secret"],
        "User-Agent": "hudhud-scripts",
    }
