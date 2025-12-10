#!/usr/bin/env python3
"""DevOps-friendly automation script that emits a lightweight health report.

This script is distributed under the MIT License. It was designed so that it
can run inside the PCF Python base image without any third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class DiskStat:
    mount: str
    size: str
    used: str
    available: str
    percent: int


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except FileNotFoundError:
        return ""


def get_uptime_seconds() -> int:
    """Return uptime taken from /proc if available."""
    content = _read_file("/proc/uptime")
    if content:
        return int(float(content.split()[0]))
    # Fallback when /proc is unavailable
    result = run_command(["uptime", "-s"])
    if not result:
        return 0
    boot_time = datetime.fromisoformat(result.strip())
    return int((datetime.now(timezone.utc) - boot_time).total_seconds())


def run_command(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def format_timedelta(seconds: int) -> str:
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m"


def parse_df(max_percent: int) -> List[DiskStat]:
    output = run_command(["df", "-hP"])
    stats: List[DiskStat] = []
    if not output:
        return stats
    lines = [line for line in output.splitlines() if line]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        percent = int(parts[4].rstrip("%"))
        if percent >= max_percent:
            stats.append(
                DiskStat(
                    mount=parts[5],
                    size=parts[1],
                    used=parts[2],
                    available=parts[3],
                    percent=percent,
                )
            )
    return stats


def services_in_failed_state() -> List[str]:
    if shutil.which("systemctl") is None:
        return []
    output = run_command(["systemctl", "--failed", "--no-legend"])
    if not output:
        return []
    services = []
    for line in output.splitlines():
        unit = line.split()[0]
        if unit:
            services.append(unit)
    return services


def collect_report(max_disk_percent: int) -> Dict[str, Any]:
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    uptime_seconds = get_uptime_seconds()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "uptime_seconds": uptime_seconds,
        "uptime_human": format_timedelta(uptime_seconds),
        "load_average": {
            "1m": load_avg[0],
            "5m": load_avg[1],
            "15m": load_avg[2],
        },
        "disk_alerts": [asdict(entry) for entry in parse_df(max_disk_percent)],
        "failed_services": services_in_failed_state(),
    }


def render_text_report(data: Dict[str, Any]) -> str:
    report_lines = [
        f"Health report generated at {data['timestamp']} UTC",
        f"Hostname: {data['hostname']}",
        f"Platform: {data['platform']}",
        f"Python version: {data['python_version']}",
        f"Uptime: {data['uptime_human']} ({data['uptime_seconds']}s)",
        "Load average (1m/5m/15m): "
        f"{data['load_average']['1m']:.2f} / {data['load_average']['5m']:.2f} / {data['load_average']['15m']:.2f}",
    ]
    if data["disk_alerts"]:
        report_lines.append("\nDisks above threshold:")
        for alert in data["disk_alerts"]:
            report_lines.append(
                f"- {alert['mount']}: {alert['percent']}% used ({alert['used']} / {alert['size']})"
            )
    else:
        report_lines.append("\nDisk usage is within threshold.")
    if data["failed_services"]:
        report_lines.append("\nFailed systemd units:")
        report_lines.extend(f"- {svc}" for svc in data["failed_services"])
    else:
        report_lines.append("\nNo failed systemd units detected.")
    return "\n".join(report_lines) + "\n"


def persist_report(data: Dict[str, Any], path: Path, as_json: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_json:
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    else:
        path.write_text(render_text_report(data))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collects a server health report (uptime, load average, disk usage, "
            "and failed services) and prints JSON to stdout by default."
        )
    )
    parser.add_argument(
        "--max-disk-percent",
        type=int,
        default=80,
        help="Generate an alert when a mount is above this utilisation percentage.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Choose the output format to emit to stdout.",
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        help="Optional path to persist the report (JSON or text depending on --format).",
    )
    args = parser.parse_args(argv)

    report = collect_report(args.max_disk_percent)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text_report(report), end="")
    if args.write_report:
        persist_report(report, args.write_report, as_json=(args.format == "json"))

    # Return non-zero exit code if we have alerts to make automation flows fail fast.
    if report["disk_alerts"] or report["failed_services"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
