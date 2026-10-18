"""Shared by the utility scripts: the project's Azure CLI, and the names of what it runs.

Every script signs in the way scripts/az does: the Linux CLI with its own config folder, never the
machine's default az. The Azure SDKs inside the court use the same sign-in through this module.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GROUP = "rg-hudhud"
STUDIO_APP = "hudhud-studio"
SITE_URL = "https://matx104.github.io/HUDHUD/"


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
    fqdn = az(
        "containerapp",
        "show",
        "-n",
        STUDIO_APP,
        "-g",
        GROUP,
        "--query",
        "properties.configuration.ingress.fqdn",
        "-o",
        "tsv",
    )
    return f"https://{fqdn}/"
