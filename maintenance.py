#!/usr/bin/env python3
"""
Toggle RateMyHusky maintenance mode and set the estimated downtime.

Usage:
  python maintenance.py -on          # enable (no ETA shown)
  python maintenance.py -on -10      # enable, ~10 minutes
  python maintenance.py -on -2h      # enable, ~2 hours
  python maintenance.py -off         # disable
"""

import sys
import json
import re
import os

ROOT          = os.path.dirname(os.path.abspath(__file__))
VERCEL_JSON   = os.path.join(ROOT, "frontend", "vercel.json")
MAINTENANCE_HTML = os.path.join(ROOT, "frontend", "public", "maintenance.html")


def set_routing(on: bool):
    with open(VERCEL_JSON) as f:
        data = json.load(f)

    rewrites = data.get("rewrites")
    if rewrites is None:
        rewrites = []
        data["rewrites"] = rewrites
    if not isinstance(rewrites, list):
        raise RuntimeError(
            "Invalid frontend/vercel.json: 'rewrites' must be a list. "
            "Maintenance routing was not changed."
        )

    dest = "/maintenance.html" if on else "/index.html"
    for route in data.get("routes", []):
        if route.get("src") == "/(.*)":
            route["dest"] = dest
    with open(VERCEL_JSON, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def set_est_time(time_str: str):
    with open(MAINTENANCE_HTML) as f:
        content = f.read()

    est_time_pattern = (
        r"(var MAINTENANCE_EST_TIME\s*=\s*)"
        r"(?:\"(?:\\\\.|[^\"\\\\])*\"|'(?:\\\\.|[^'\\\\])*')"
    )
    matches = re.findall(est_time_pattern, content)
    if len(matches) != 1:
        raise RuntimeError(
            "Invalid frontend/public/maintenance.html: expected exactly one "
            "MAINTENANCE_EST_TIME assignment. Maintenance ETA was not changed."
        )

    safe_time_literal = json.dumps(time_str)
    content = re.sub(
        est_time_pattern,
        lambda m: f"{m.group(1)}{safe_time_literal}",
        content,
        count=1,
    )

    with open(MAINTENANCE_HTML, "w") as f:
        f.write(content)


def parse_time(arg: str) -> str:
    arg = arg.lstrip("-").strip()
    if re.fullmatch(r"\d+h", arg):
        n = int(arg[:-1])
        return f"~{n} hour{'s' if n != 1 else ''}"
    if re.fullmatch(r"\d+m", arg):
        n = int(arg[:-1])
        return f"~{n} minute{'s' if n != 1 else ''}"
    if re.fullmatch(r"\d+", arg):
        n = int(arg)
        return f"~{n} minute{'s' if n != 1 else ''}"
    return arg  # raw string passthrough


def usage():
    print(__doc__)
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("-on", "-off"):
        usage()

    if args[0] == "-on":
        set_routing(True)
        eta = parse_time(args[1]) if len(args) > 1 else ""
        set_est_time(eta)
        label = f"ETA: {eta}" if eta else "no ETA"
        print(f"[maintenance] ON  ({label})")
        print(
            "Commit + push frontend/vercel.json and "
            "frontend/public/maintenance.html to apply."
        )

    elif args[0] == "-off":
        set_routing(False)
        print("[maintenance] OFF")
        print("Commit + push frontend/vercel.json to apply.")


if __name__ == "__main__":
    main()
