"""Browse the audit trail: the recent runs, or every record of one run. Read-only.

.venv/bin/python scripts/audit.py runs                 # the last ten runs, newest first
.venv/bin/python scripts/audit.py runs --match syn-000021
.venv/bin/python scripts/audit.py show 20261018T023908-1523c8 [--out run.json]
"""

import argparse
import json
import sys
from pathlib import Path

from _azure import use_project_cli

ENDPOINT = "https://hudhud-audit.documents.azure.com:443/"


def container():
    use_project_cli()
    from azure.cosmos import CosmosClient

    from court.identity import credential

    client = CosmosClient(ENDPOINT, credential=credential())
    return client.get_database_client("hudhud").get_container_client("audit")


def runs(audit, match: str | None, limit: int) -> None:
    where = "c.type = 'summary'" + (" AND c.matchId = @match" if match else "")
    query = (
        f"SELECT TOP {limit} c.runId, c.matchId, c.recordedAt, c.stats, c.cost_usd FROM c "
        f"WHERE {where} ORDER BY c.recordedAt DESC"
    )
    params = [{"name": "@match", "value": match}] if match else []
    rows = audit.query_items(query, parameters=params, enable_cross_partition_query=True)
    for r in rows:
        stats = r.get("stats") or {}
        cost = f"${r['cost_usd']:.4f}" if r.get("cost_usd") is not None else "  offline"
        print(
            f"{r['runId']}  {r['matchId']}  {r['recordedAt'][:19]}  {cost}  "
            f"aired {stats.get('aired', 0)}, refused {stats.get('rejected', 0)}"
        )


def show(audit, run_id: str, out: Path | None) -> None:
    query = "SELECT * FROM c WHERE c.runId = @run ORDER BY c.seq"
    rows = list(
        audit.query_items(
            query, parameters=[{"name": "@run", "value": run_id}], enable_cross_partition_query=True
        )
    )
    records = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    if out:
        out.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {len(records)} records to {out}")
        return
    for r in records:
        line = r.get("text") or (r.get("claim") or {}).get("text") or r.get("detail") or ""
        print(f"{r['seq']:>3} {r['type']:<11} {r.get('minute', ''):>6}  {line[:110]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("runs")
    r.add_argument("--match", help="a match id, such as syn-000021")
    r.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("show")
    s.add_argument("run_id")
    s.add_argument("--out", type=Path, help="write the records as JSON instead")
    args = parser.parse_args()
    audit = container()
    if args.cmd == "runs":
        runs(audit, args.match, args.limit)
    else:
        show(audit, args.run_id, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
