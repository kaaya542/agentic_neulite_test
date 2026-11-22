#!/usr/bin/env python3
"""Copy the distributable source tree into a new directory, without Git history."""

import argparse
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ".gitignore", "AGENTS.md", "CLAUDE.md", "COPYING", "LOCAL_ENV.md.example",
    "README.md", "VERSION", "requirements.txt", "upstream.json",
)
DIRECTORIES = (
    ".agents/skills", ".claude/skills", "bionetlite", "docs", "examples",
    "flavors", "helper", "kernel", "test", "tools",
)
IGNORE = shutil.ignore_patterns(
    ".DS_Store", "__pycache__", "*.pyc", "*.o", "*.so", "*.dylib", "nl",
    ".git", ".venv", "_runs", ".env", ".env.*", "settings.local.json",
)


def export_repository(output, root=ROOT):
    root = Path(root).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Output already exists: {output}. Choose a new directory.")
    resolved_output = output.resolve()
    for name in DIRECTORIES:
        source = root / name
        if resolved_output == source or source in resolved_output.parents:
            raise ValueError(f"Output must be outside the exported source directories: {source}")
    for name in FILES + DIRECTORIES:
        if not (root / name).exists():
            raise ValueError(f"Required source is missing: {root / name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Assemble beside the destination so an incomplete copy is never returned.
    with tempfile.TemporaryDirectory(prefix=".neulite-export-", dir=output.parent) as temporary:
        staged = Path(temporary) / "source"
        staged.mkdir()
        for name in FILES:
            shutil.copy2(root / name, staged / name)
        for name in DIRECTORIES:
            shutil.copytree(root / name, staged / name, symlinks=True, ignore=IGNORE)
        for link in staged.rglob("*"):
            if link.is_symlink():
                target = link.resolve()
                if not target.exists() or staged not in target.parents:
                    raise ValueError(f"Exported link must resolve inside the copy: {link.relative_to(staged)}")
        if output.exists() or output.is_symlink():
            raise ValueError(f"Output appeared during export: {output}")
        staged.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = export_repository(args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Exported source: {output}")


if __name__ == "__main__":
    main()
