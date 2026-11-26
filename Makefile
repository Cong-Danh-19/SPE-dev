.PHONY: install test run-exp plot all-pipeline pack clean

install:
	python -m pip install -r requirements.txt

test:
	python -X utf8 -m pytest -v tests

run-exp:
	python -X utf8 -u -m apps.benchmark_experiments_app

plot:
	python -X utf8 -m apps.plotting_app

all-pipeline: test run-exp plot

GROUP ?= YY9B
override GROUP := $(value GROUP)
pack: export PACK_GROUP := $(value GROUP)
pack clean: export SPE_MAKEFILE := $(lastword $(MAKEFILE_LIST))

# The report files and Python entry points are fixed. exam/ and bkitevsim/ can contain additional material.
define PROJECT_TREE
import os
from pathlib import Path

source = Path(os.environ["SPE_MAKEFILE"]).resolve().parent
root = source.parent
skip = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".tox", ".ipynb_checkpoints",
        ".idea", ".vscode", ".mypy_cache", ".ruff_cache"}
def walk(folder):
    for current, dirs, names in os.walk(folder):
        base = Path(current)
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".report-")
                   and (base/d).resolve() == base/d and not (base/d/"pyvenv.cfg").is_file()]
        yield base, names
endef

define PACK_ZIP
$(PROJECT_TREE)
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

group = os.environ["PACK_GROUP"]
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", group):
    raise SystemExit("Invalid GROUP: use ASCII letters, digits, underscores or hyphens.")
name = "Spe-Ass-final-" + group
phase1 = "The Phase 1 submission/Spe-Ass-Spec-YY9B.pdf"
reports = [
    phase1, "Architecture and class diagrams/Architecture-and-class-diagrams.pdf",
    "A description of the workload/Workload.pdf", "A description of the experiments/Experiments.pdf",
    "Validation and evaluation/Validation-and-evaluation.pdf", "A user manual/User-manual.pdf",
]
layout = {
    ".": "LICENSE Makefile README.md requirements.txt",
    "apps": "__init__.py benchmark_experiments_app.py distributed_sequential_app.py plotting_app.py simulator_app.py synchronous_sequential_app.py",
    "bkitevsim": ".gitkeep",
    "bkitevsim/core": "__init__.py event.py logical_coProcess.py logical_process.py simulation.py",
    "bkitevsim/dispatchers": "__init__.py sequential_eventdispatcher.py",
    "bkitevsim/queues": "__init__.py ladder_queue.py priority_queue.py",
    "design": "design.ipynb Spe-Ass-Spec-YY9B.pdf",
    "docs": "architecture.md user_manual.md",
    "docs/diagrams": ".gitkeep architecture.svg classes.svg",
    "exam": ".gitkeep",
    "scenarios": "__init__.py analytical.py async_runtime_lps.py config.py",
    "tests": "__init__.py test_invariants.py test_models.py",
    "results": (".gitkeep e1_throughput_curves.csv e2_capacity_delay.csv e3_loom_vs_bun_sensitivity.csv "
                "e4_closed_loop.csv e5_special_scenarios.csv raw_seed_runs.csv verification_summary.csv"),
    "results/figures": ".gitkeep",
}
figures = ["fig1_e1_throughput", "fig2_e2_capacity_delay", "fig3_e3_sensitivity", "fig4a_e4_closed_loop", "fig4b_e5_bottlenecks"]
files = [root / item for item in [".gitignore", "README.md", *reports]]
files.extend(source / folder / item for folder, items in layout.items() for item in items.split())
files.extend(source / "results/figures" / f"{stem}.{ext}" for stem in figures for ext in ("png", "pdf"))
for path in files:
    if not path.is_file() or path.resolve() != path or (not path.stat().st_size and path.name not in {".gitkeep", "__init__.py"}):
        raise SystemExit(f"Missing or invalid submission file: {path}")
for folder in ("exam", "bkitevsim"):
    for base, names in walk(source / folder):
        for item in names:
            path = base / item
            if (item not in {"Thumbs.db", ".DS_Store", "desktop.ini", ".coverage"} and not item.startswith("~$$")
                    and path.suffix.lower() not in {".pyc", ".pyo", ".zip"} and path.is_file() and not path.is_symlink()):
                files.append(path)
files = sorted(set(files))
archive = root.parent / (name + ".zip")
with TemporaryDirectory(dir=archive.parent) as temp:
    staged = Path(temp) / archive.name
    with ZipFile(staged, "w", compression=ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, f"{name}/{path.relative_to(root).as_posix()}")
    with ZipFile(staged) as bundle:
        if damaged := bundle.testzip():
            raise SystemExit(f"ZIP CRC check failed: {damaged}")
        for pdf in reports:
            with bundle.open(f"{name}/{pdf}") as stream:
                if stream.read(5) != b"%PDF-":
                    raise SystemExit(f"Invalid PDF: {pdf}")
        if bundle.read(f"{name}/{phase1}") != bundle.read(f"{name}/{source.name}/design/{Path(phase1).name}"):
            raise SystemExit("Update the PDF in design/ to match the submitted Phase 1 PDF.")
    staged.replace(archive)
print(f"{archive} ({len(files)} files)")
endef

pack: export SPE_PACK := $(PACK_ZIP)
pack:
	@python -X utf8 -c "import os; exec(os.environ['SPE_PACK'])"

define CLEAN_SOURCE
$(PROJECT_TREE)
from itertools import chain
import shutil

for folder in chain([root], (base for base, _ in walk(source))):
    for name in ("__pycache__", ".pytest_cache"):
        cache = folder / name
        if cache.is_dir() and cache.resolve() == cache:
            shutil.rmtree(cache)
for archive in source.glob("*.zip"):
    if archive.is_file():
        archive.unlink()
endef

clean: export SPE_CLEAN := $(CLEAN_SOURCE)
clean:
	@python -X utf8 -c "import os; exec(os.environ['SPE_CLEAN'])"
