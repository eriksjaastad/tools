#!/usr/bin/env python3
"""
Monarch Transaction Analyzer — CFO tool for tech/business spending.

Reads a Monarch CSV export and filters for software, AI, and infrastructure charges.
Outputs a structured spending report.

Usage:
    uv run monarch-analyzer.py <csv_file>
    uv run monarch-analyzer.py <csv_file> --months 3
    uv run monarch-analyzer.py <csv_file> --json
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Vendor patterns: (match_string, category, subcategory)
# Matched against both Merchant name and Original Statement (case-insensitive)
VENDOR_PATTERNS = [
    # AI Tools
    ("CLAUDE.AI SUBSCRIPTION", "AI", "Claude Max"),
    ("ANTHROPIC", "AI", "Anthropic API"),
    ("OPENAI", "AI", "OpenAI"),
    ("CURSOR", "AI", "Cursor"),
    ("STABILITY.AI", "AI", "Stability AI"),
    ("MIDJOURNEY", "AI", "Midjourney"),

    # Infrastructure
    ("DOPPLER", "Infrastructure", "Doppler"),
    ("VERCEL", "Infrastructure", "Vercel"),
    ("GOOGLE*CLOUD", "Infrastructure", "Google Cloud"),
    ("GOOGLE *CLOUD", "Infrastructure", "Google Cloud"),
    ("RAILWAY", "Infrastructure", "Railway"),
    ("GOOGLE *WORKSPACE", "Infrastructure", "Google Workspace"),
    ("GOOGLE*WORKSPACE", "Infrastructure", "Google Workspace"),
    ("Google Workspace", "Infrastructure", "Google Workspace"),
    ("NAME-CHEAP", "Infrastructure", "NameCheap"),
    ("NAMECHEAP", "Infrastructure", "NameCheap"),
    ("MAKE.COM", "Infrastructure", "Make.com"),
    ("CLOUDFLARE", "Infrastructure", "Cloudflare"),
    ("TURSO", "Infrastructure", "Turso"),
    ("GITHUB", "Infrastructure", "GitHub"),
    ("DIGITALOCEAN", "Infrastructure", "DigitalOcean"),
    ("HEROKU", "Infrastructure", "Heroku"),
    ("SUPABASE", "Infrastructure", "Supabase"),
    ("FLY.IO", "Infrastructure", "Fly.io"),

    # Storage
    ("GOOGLE *Google One", "Storage", "Google One"),
    ("GOOGLE *GOOGLE ONE", "Storage", "Google One"),
]


def classify_transaction(merchant, statement):
    """Return (category, subcategory) or None if not a tech charge."""
    text = f"{merchant} {statement}".lower()
    for pattern, category, subcategory in VENDOR_PATTERNS:
        if pattern.lower() in text:
            return category, subcategory
    return None, None


def parse_transactions(csv_path, months=None):
    """Parse Monarch CSV and return classified tech charges."""
    charges = []
    cutoff = None
    if months:
        cutoff = datetime.now() - timedelta(days=months * 30)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = float(row["Amount"]) if row["Amount"] else 0
            if amount >= 0:
                continue

            date = datetime.strptime(row["Date"], "%Y-%m-%d")
            if cutoff and date < cutoff:
                continue

            merchant = row["Merchant"]
            statement = row.get("Original Statement", "")
            category, subcategory = classify_transaction(merchant, statement)

            if category:
                charges.append({
                    "date": row["Date"],
                    "merchant": merchant,
                    "category": category,
                    "subcategory": subcategory,
                    "amount": abs(amount),
                    "statement": statement.strip()[:80],
                    "account": row.get("Account", ""),
                    "tags": row.get("Tags", ""),
                })

    return charges


def build_report(charges):
    """Build summary data from charges."""
    by_category = defaultdict(float)
    by_subcategory = defaultdict(lambda: {"total": 0.0, "count": 0, "category": ""})
    by_month = defaultdict(lambda: defaultdict(float))

    for c in charges:
        by_category[c["category"]] += c["amount"]
        key = c["subcategory"]
        by_subcategory[key]["total"] += c["amount"]
        by_subcategory[key]["count"] += 1
        by_subcategory[key]["category"] = c["category"]
        month = c["date"][:7]
        by_month[month][c["subcategory"]] += c["amount"]

    return by_category, by_subcategory, by_month


def print_report(charges, by_category, by_subcategory, by_month):
    """Print formatted spending report."""
    total = sum(by_category.values())
    date_range = f"{charges[-1]['date']} to {charges[0]['date']}" if charges else "N/A"

    print(f"\n{'='*60}")
    print(f"  CFO SPENDING REPORT — Tech & Infrastructure")
    print(f"  {date_range}  |  {len(charges)} charges  |  ${total:,.2f} total")
    print(f"{'='*60}\n")

    # By category
    print(f"{'Category':<20} {'Total':>12} {'% of Spend':>12}")
    print("-" * 46)
    for cat in sorted(by_category, key=by_category.get, reverse=True):
        pct = (by_category[cat] / total * 100) if total else 0
        print(f"{cat:<20} ${by_category[cat]:>10,.2f} {pct:>10.1f}%")
    print("-" * 46)
    print(f"{'TOTAL':<20} ${total:>10,.2f}\n")

    # By vendor
    print(f"{'Vendor':<22} {'Category':<18} {'Charges':>7} {'Total':>12} {'Avg':>10}")
    print("-" * 72)
    for sub in sorted(by_subcategory, key=lambda x: by_subcategory[x]["total"], reverse=True):
        d = by_subcategory[sub]
        avg = d["total"] / d["count"] if d["count"] else 0
        print(f"{sub:<22} {d['category']:<18} {d['count']:>7} ${d['total']:>10,.2f} ${avg:>8,.2f}")

    # Monthly trend
    months_sorted = sorted(by_month.keys())
    if len(months_sorted) > 1:
        print(f"\n{'Month':<10}", end="")
        all_subs = sorted({s for m in by_month.values() for s in m})
        for sub in all_subs:
            print(f" {sub[:12]:>13}", end="")
        print(f" {'TOTAL':>13}")
        print("-" * (10 + 14 * (len(all_subs) + 1)))
        for month in months_sorted:
            print(f"{month:<10}", end="")
            month_total = 0
            for sub in all_subs:
                val = by_month[month].get(sub, 0)
                month_total += val
                print(f" ${val:>11,.2f}" if val else f" {'—':>12}", end="")
            print(f" ${month_total:>11,.2f}")


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run monarch-analyzer.py <csv_file> [--months N] [--json]")
        sys.exit(1)

    csv_path = sys.argv[1]
    months = None
    output_json = "--json" in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == "--months" and i + 1 < len(sys.argv):
            months = int(sys.argv[i + 1])

    if not Path(csv_path).exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        sys.exit(1)

    charges = parse_transactions(csv_path, months)

    if not charges:
        print("No tech/infrastructure charges found.")
        sys.exit(0)

    if output_json:
        by_category, by_subcategory, by_month = build_report(charges)
        print(json.dumps({
            "charges": charges,
            "by_category": dict(by_category),
            "by_vendor": {k: dict(v) for k, v in by_subcategory.items()},
            "by_month": {k: dict(v) for k, v in by_month.items()},
            "total": sum(by_category.values()),
            "charge_count": len(charges),
        }, indent=2))
    else:
        by_category, by_subcategory, by_month = build_report(charges)
        print_report(charges, by_category, by_subcategory, by_month)


if __name__ == "__main__":
    main()
