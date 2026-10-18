"""What has the project cost? Month to date, by service, and against the $100 budget. Read-only.

Cost Management lags the meters by up to a day, so today's model calls may not show yet; each
run's receipt and the control room's workbook carry the live estimate.

    make costs
"""

import json
import sys
import time

from _azure import GROUP, AzureError, az, az_json


def query(scope: str, timeframe: str) -> list[tuple[str, float, str]]:
    body = {
        "type": "ActualCost",
        "timeframe": timeframe,
        "dataset": {
            "granularity": "None",
            "aggregation": {"cost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ServiceName"}],
        },
    }
    url = f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query"
    for attempt in range(1, 5):  # Cost Management allows only a few queries a minute
        try:
            result = az_json(
                "rest",
                "--method",
                "post",
                "--url",
                f"{url}?api-version=2023-11-01",
                "--body",
                json.dumps(body),
            )
            break
        except AzureError as error:
            if "429" not in str(error) or attempt == 4:
                raise
            print(f"  (Cost Management is busy; trying again in {20 * attempt} s)", file=sys.stderr)
            time.sleep(20 * attempt)
    columns = [c["name"] for c in result["properties"]["columns"]]
    rows = []
    for row in result["properties"]["rows"]:
        record = dict(zip(columns, row, strict=False))
        rows.append((record["ServiceName"], float(record["Cost"]), record.get("Currency", "USD")))
    return sorted(rows, key=lambda r: -r[1])


def main() -> int:
    subscription = az("account", "show", "--query", "id", "-o", "tsv")
    scope = f"/subscriptions/{subscription}/resourceGroups/{GROUP}"
    rows = query(scope, "MonthToDate")
    total = sum(cost for _, cost, _ in rows)
    currency = rows[0][2] if rows else "USD"
    print(f"{GROUP}, month to date (Cost Management, up to a day behind):")
    for service, cost, _ in rows:
        print(f"  {service:<36} {cost:>9.4f} {currency}")
    print(f"  {'total':<36} {total:>9.4f} {currency}")

    budget = az_json("consumption", "budget", "show", "--budget-name", "hudhud-credit")
    spent = float((budget.get("currentSpend") or {}).get("amount") or 0)
    amount = float(budget["amount"])
    print(
        f"\nbudget hudhud-credit: {spent:.2f} of {amount:.0f} {currency} spent this period "
        f"({spent / amount:.1%}); alerts at 25, 50, 75 and 90% actual, 100% forecast"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
