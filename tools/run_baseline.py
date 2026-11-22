#!/usr/bin/env python3
"""Build an isolated vanilla copy and run one cell from the bundled test data."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_logged(command, cwd, log):
    with Path(log).open("w") as handle:
        subprocess.run(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, check=True)


def voltage_summary(path):
    low, high, rows = math.inf, -math.inf, 0
    with Path(path).open() as handle:
        for line in handle:
            values = [float(x) for x in line.split()]
            if len(values) != 2 or not all(math.isfinite(x) for x in values):
                raise ValueError(f"Invalid single-cell output at row {rows}: {path}")
            low, high = min(low, values[1]), max(high, values[1])
            rows += 1
    if rows == 0:
        raise ValueError(f"Empty voltage output: {path}")
    return {"samples": rows, "v_min_mV": low, "v_max_mV": high}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_runs/baseline")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT / "kernel", output / "kernel",
                    ignore=shutil.ignore_patterns("*.o", "nl", "*.dat"))
    shutil.copytree(ROOT / "test/kernel-test/data", output / "data")
    (output / "p.csv").write_text(
        "# One Scnn1a cell, bundled kernel-test inputs; not a regenerated Allen fit.\n"
        "1,3682,Scnn1a,data/Scnn1a_473845048_m_c.swc,data/472363762.csv\n")
    (output / "c.csv").write_text("# No synapses for this baseline.\n")
    before = {str(p.relative_to(ROOT)): sha256(p) for p in (ROOT / "kernel").rglob("*")
              if p.is_file() and p.suffix != ".o" and p.name != "nl"}
    started = time.perf_counter()
    run_logged(["make", "-j2"], output / "kernel", output / "build.log")
    run_logged(["./kernel/nl", "p.csv", "c.csv"], output, output / "run.log")
    # A source export may live below another checkout or have no Git history.
    commit = "Git revision unavailable (source export or checkout without commits)"
    try:
        revision = subprocess.run(["git", "rev-parse", "--show-toplevel", "HEAD"],
                                  cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        fields = revision.stdout.strip().splitlines()
        if revision.returncode == 0 and len(fields) == 2 and Path(fields[0]).resolve() == ROOT:
            commit = fields[1]
    except FileNotFoundError:
        pass  # Git is optional for the baseline simulation.
    report = {
        "purpose": "Unmodified vanilla single-cell regression baseline, not scientific validation",
        "neulite_commit": commit,
        "platform": platform.platform(), "python": platform.python_version(),
        "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "elapsed_seconds": time.perf_counter() - started,
        "kernel_sha256": before,
        "input_sha256": {p: sha256(output / p) for p in
                         ["p.csv", "c.csv", "data/472363762.csv", "data/Scnn1a_473845048_m_c.swc"]},
        "voltage": voltage_summary(output / "v.dat"),
        "spikes": len((output / "s.dat").read_text().splitlines()),
        "output_sha256": {name: sha256(output / name) for name in ["v.dat", "s.dat"]},
    }
    assert report["voltage"]["samples"] == 20000, "Expected bundled config: 2000 ms / 0.1 ms"
    assert all(sha256(ROOT / path) == digest for path, digest in before.items()), "vanilla changed"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["neulite_commit", "voltage", "spikes", "elapsed_seconds"]}, indent=2))
    print(f"Full inputs, build, logs and report: {output}")


if __name__ == "__main__":
    main()
