"""Is everything as it should be? A read-only check of the whole setup, top to bottom.

The sign-in and subscription, every Azure resource and its guardrails (keys off, free tier, caps),
the studio's identity and health, the showcase site and CI. Prints a checklist; exits 1 if any
check fails, so it can gate a recording session or the submission. --publish also writes the
checklist to site/data/doctor.js, the public proof on the showcase site's Control room page, with
any email address replaced.

    make doctor
    .venv/bin/python scripts/doctor.py --publish    # then commit site/data/doctor.js
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime

from _azure import GROUP, ROOT, SITE_URL, STUDIO_APP, az, az_json, studio_url

# What must never reach the published proof: anything like an account, an email or an ID.
SUSPICIOUS = re.compile(r"@|#ext#|onmicrosoft|[0-9a-f]{8}-[0-9a-f]{4}|[0-9a-f]{16,}", re.I)

results: list[tuple[str, str, str]] = []  # (mark, check, detail)


def check(name: str, ok: bool, detail: str = "", *, warn: bool = False) -> None:
    results.append(("✔" if ok else "!" if warn else "✘", name, detail))


def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status, response.read().decode()
    except Exception as error:  # a failed check, not a crash
        return 0, str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--publish", action="store_true", help="write site/data/doctor.js too")
    publish = parser.parse_args().publish
    account = az_json("account", "show")
    check(
        "Signed in to the student subscription",
        account["name"] == "Azure for Students",
        f"{account['user']['name']} on {account['name']}",
    )

    resources = {r["name"]: r for r in az_json("resource", "list", "-g", GROUP)}
    for name in (
        "hudhud-foundry",
        "hudhud-audit",
        "hudhud-insights",
        "hudhud-logs",
        "hudhudstudio",
        "hudhud-studio-id",
        "hudhud-env",
        STUDIO_APP,
    ):
        check(f"{name} exists", name in resources, resources.get(name, {}).get("location", ""))

    foundry = az_json("cognitiveservices", "account", "show", "-n", "hudhud-foundry", "-g", GROUP)
    check("Foundry: keys off", foundry["properties"].get("disableLocalAuth") is True)
    deployments = {
        d["name"]: d["properties"]["provisioningState"]
        for d in az_json(
            "cognitiveservices",
            "account",
            "deployment",
            "list",
            "-n",
            "hudhud-foundry",
            "-g",
            GROUP,
        )
    }
    for model in ("gpt-4.1-mini", "gpt-5-mini"):
        check(f"Foundry: {model} deployed", deployments.get(model) == "Succeeded")

    cosmos = az_json("cosmosdb", "show", "-n", "hudhud-audit", "-g", GROUP)
    check("Cosmos DB: free tier", cosmos.get("enableFreeTier") is True)
    check("Cosmos DB: keys off", cosmos.get("disableLocalAuth") is True)
    raw = az_json(
        "rest",
        "--method",
        "get",
        "--url",
        f"https://management.azure.com{cosmos['id']}?api-version=2024-11-15",
    )
    limit = (raw["properties"].get("capacity") or {}).get("totalThroughputLimit")
    check("Cosmos DB: capped at the free 1,000 RU/s", limit == 1000, f"limit {limit}")

    insights = az_json("resource", "show", "--ids", resources["hudhud-insights"]["id"])
    check("Application Insights: keys off", insights["properties"].get("DisableLocalAuth") is True)
    logs = az_json(
        "monitor", "log-analytics", "workspace", "show", "-n", "hudhud-logs", "-g", GROUP
    )
    cap = logs["workspaceCapping"]["dailyQuotaGb"]
    check(
        "Log Analytics: daily cap inside the free 5 GB a month", 0 < cap <= 0.16, f"{cap} GB a day"
    )

    registry = az_json("acr", "show", "-n", "hudhudstudio", "-g", GROUP)
    check("Registry: admin user off", registry["adminUserEnabled"] is False)

    app = az_json("containerapp", "show", "-n", STUDIO_APP, "-g", GROUP)
    image = app["properties"]["template"]["containers"][0]["image"]
    # The image is tagged with the commit it was built from (scripts/deploy-studio). It's current
    # when nothing the image is built from has changed since, whatever else has been committed.
    tag = image.rsplit(":", 1)[-1]
    built_from = ["apps", "packages", "Dockerfile", ".dockerignore"]
    current = (
        subprocess.run(
            ["git", "diff", "--quiet", tag, "HEAD", "--", *built_from], cwd=ROOT
        ).returncode
        == 0
    )
    check("Studio: running", app["properties"].get("runningStatus") == "Running")
    check("Studio: built from the latest code", current, tag, warn=True)
    env = {e["name"]: e.get("value") for e in app["properties"]["template"]["containers"][0]["env"]}
    check(
        "Studio: no secrets in its settings",
        not any("KEY" in k or "SECRET" in k or "PASSWORD" in k for k in env),
    )

    principal = az(
        "identity",
        "show",
        "-n",
        "hudhud-studio-id",
        "-g",
        GROUP,
        "--query",
        "principalId",
        "-o",
        "tsv",
    )
    roles = set(
        az(
            "role",
            "assignment",
            "list",
            "--assignee",
            principal,
            "--all",
            "--query",
            "[].roleDefinitionName",
            "-o",
            "tsv",
        ).split("\n")
    )
    for role in ("AcrPull", "Cognitive Services User", "Monitoring Metrics Publisher"):
        check(f"Studio identity: {role}", role in roles)
    cosmos_roles = az_json(
        "cosmosdb", "sql", "role", "assignment", "list", "-a", "hudhud-audit", "-g", GROUP
    )
    check(
        "Studio identity: Cosmos DB Data Contributor",
        any(r["principalId"] == principal for r in cosmos_roles),
    )

    url = studio_url()
    status, _ = fetch(url + "healthz")
    check("Studio: healthy", status == 200, url)
    status, body = fetch(url + "api/config")
    config = json.loads(body) if status == 200 else {}
    check(
        "Studio: models connected",
        config.get("models") is True,
        f"{config.get('model_matches_left', '?')} model matches left today",
    )

    budget = az_json("consumption", "budget", "show", "--budget-name", "hudhud-credit")
    check(
        "Budget: hudhud-credit",
        float(budget.get("amount", 0)) == 100,
        f"${float(budget['amount']):.0f} a year",
    )

    status, body = fetch(SITE_URL + "config.js")
    check("Showcase site: up", status == 200, SITE_URL)
    # The site may link the studio by a short address that redirects: follow it to the studio.
    linked = re.search(r'studioUrl: "([^"]+)"', body)
    reached, _ = fetch(linked[1].rstrip("/") + "/healthz") if linked else (0, "")
    check(
        "Showcase site: links the live studio",
        reached == 200,
        linked[1] if linked else "no studioUrl in config.js",
    )

    runs = subprocess.run(
        ["gh", "run", "list", "--limit", "1", "--workflow", "ci", "--json", "conclusion,headSha"],
        capture_output=True,
        text=True,
    )
    latest = json.loads(runs.stdout or "[{}]")[0] if runs.returncode == 0 else {}
    check(
        "CI: latest run green",
        latest.get("conclusion") == "success",
        (latest.get("headSha") or "")[:7],
        warn=runs.returncode != 0,
    )

    if publish:
        checks = [
            {"ok": mark != "✘", "warn": mark == "!", "check": name, "detail": detail}
            for mark, name, detail in results
        ]
        checks[0]["detail"] = "the project's own account, on Azure for Students"  # never the name
        if leaks := [c["detail"] for c in checks if SUSPICIOUS.search(c["detail"])]:
            raise SystemExit(f"refusing to publish: details look like accounts or IDs: {leaks}")
        record = {"checked": datetime.now(UTC).isoformat(timespec="minutes"), "checks": checks}
        out = ROOT / "site" / "data" / "doctor.js"
        header = (
            "// Generated by scripts/doctor.py --publish: the environment's checks, as proof.\n"
        )
        out.write_text(
            f"{header}window.DOCTOR = {json.dumps(record, indent=2, ensure_ascii=False)};\n"
        )
    width = max(len(name) for _, name, _ in results)
    for mark, name, detail in results:
        print(f" {mark} {name:<{width}}  {detail}")
    failed = sum(mark == "✘" for mark, _, _ in results)
    print(
        f"\n{len(results) - failed} of {len(results)} checks pass"
        + (f", {failed} fail" if failed else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
