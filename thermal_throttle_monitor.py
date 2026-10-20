"""Log Linux CPU0 frequency and an explicitly named thermal zone.

High temperature alone is not evidence of thermal throttling.
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import time


def scaled(path):
    try:
        return float(Path(path).read_text().strip()) / 1000
    except (OSError, ValueError):
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="thermal_metrics.csv")
    parser.add_argument("--zone", default="/sys/class/thermal/thermal_zone0")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--samples", type=int, default=0, help="0 means until Ctrl+C")
    args = parser.parse_args()
    if args.interval <= 0 or args.samples < 0:
        parser.error("interval must be positive and samples nonnegative")
    zone = Path(args.zone)
    try:
        label = (zone / "type").read_text().strip()
    except OSError:
        label = "unavailable"
    with open(args.out, "x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp_utc", "cpu0_frequency_mhz", "thermal_zone_type", "temperature_c"])
        count = 0
        try:
            while True:
                temp = scaled(zone / "temp")
                writer.writerow([datetime.now(timezone.utc).isoformat(),
                    scaled("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"), label, temp])
                stream.flush()
                if temp != "" and temp > 85:
                    print(f"High temperature in {label}: {temp:.1f} C (not proof of throttling)")
                count += 1
                if args.samples and count >= args.samples:
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
