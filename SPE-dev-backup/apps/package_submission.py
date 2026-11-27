"""Package the seven submission folders from the current working tree."""
import argparse
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
import os
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT = Path(__file__).resolve().parent.parent
FOLDERS = (
    PROJECT.name, "The Phase 1 submission", "Architecture and class diagrams",
    "A description of the workload", "A description of the experiments",
    "Validation and evaluation", "A user manual",
)
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}


def package(group, output=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", group):
        raise ValueError("GROUP must contain only ASCII letters, numbers, '_' or '-'")
    required = [ROOT / 'The Phase 1 submission' / f'Spe-Ass-Spec-{group}.pdf',
                PROJECT / 'design' / 'design.ipynb']
    required += [ROOT / folder / 'README.md' for folder in FOLDERS[2:]]
    required.extend(PROJECT / "results" / "phase1_design" / name for name in
                    ["report.html", "runtime_validation.csv", "verification.csv", "tandem.csv", "slo.csv",
                     *(f"design_E{i}_{kind}.csv" for i in range(1, 7) for kind in ("raw", "summary"))])
    missing = [str(p) for p in required if not p.is_file() or not p.stat().st_size]
    if missing:
        raise FileNotFoundError("Missing required submission files: " + ", ".join(missing))
    name = f'Spe-Ass-final-{group}'
    archive = Path(output).resolve() if output else ROOT / f'{name}.zip'
    files = []
    for folder in FOLDERS:
        for base, dirs, names in os.walk(ROOT / folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                       and not (Path(base)/d).is_symlink() and not (Path(base)/d/"pyvenv.cfg").exists()]
            if Path(base) == PROJECT:
                dirs[:] = [d for d in dirs if d != "docs"]
            if Path(base) == PROJECT / "results":
                dirs[:] = [d for d in dirs if d == "phase1_design"]
                continue
            for filename in names:
                path = Path(base)/filename
                if (filename in {"LICENSE", "Makefile", "requirements.txt"} or
                    path.suffix.lower() in {".md", ".py", ".pdf", ".ipynb", ".svg", ".png", ".csv", ".html", ".json"}):
                    if not filename.startswith(".") and path.is_file() and not path.is_symlink():
                        files.append(path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=archive.parent, suffix='.tmp', delete=False) as temp:
        staged = Path(temp.name)
    try:
        with ZipFile(staged, 'w', compression=ZIP_DEFLATED) as bundle:
            for path in sorted(files):
                bundle.write(path, (Path(name) / path.relative_to(ROOT)).as_posix())
        with ZipFile(staged) as bundle:
            if bad := bundle.testzip():
                raise RuntimeError(f'ZIP CRC check failed: {bad}')
        staged.replace(archive)
    finally:
        staged.unlink(missing_ok=True)
    return archive, len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', default=os.environ.get('PACK_GROUP', 'YY9B'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    archive, count = package(args.group, args.output)
    print(f'{archive} ({count} files)')


if __name__ == '__main__':
    main()
