.PHONY: install test run-exp plot all-pipeline pack clean

install:
	pip install -r requirements.txt

test:
	pytest -v

run-exp:
	python -m apps.benchmark_experiments_app

plot:
	python -m apps.plotting_app --input-dir results --output-dir results/figures --formats png,pdf

all-pipeline: test run-exp plot

GROUP ?= GroupName
override GROUP := $(value GROUP)
pack: export PACK_GROUP := $(value GROUP)

# Keep the recipe portable across GNU Make with cmd.exe or a POSIX shell.
define PACK_SCRIPT
import os
import re
from fnmatch import fnmatch
from pathlib import Path
from tempfile import NamedTemporaryFile
from unicodedata import normalize
from zipfile import ZIP_DEFLATED, ZipFile

group = os.environ["PACK_GROUP"]
if not group.strip() or any(ch in '<>:"/\\|?*' or ord(ch) < 32 for ch in group):
    raise SystemExit("GROUP must be a valid filename component.")

report = f"design/Spe-Ass-Spec-{group}.pdf"
files = {}
ignored_dirs = {".venv", "venv", "env", ".git", "__pycache__", ".pytest_cache",
                ".ipynb_checkpoints", ".idea", ".vscode", ".mypy_cache", ".ruff_cache", "tmp", "temp"}
ignored_files = ("*.py[cod]", "*~", "~*", "*.sw?", "*.tmp", "*.temp", "*.bak", "*.orig",
                 "*.rej", "*.log", "*.zip", ".DS_Store", "Thumbs.db", ".coverage", ".#*")
for root in ("scenarios", "apps", "tests", "bkitevsim", "results", "docs", "design"):
    for directory, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for name in names:
            path = Path(directory, name)
            entry = path.as_posix()
            if root == "design" and name != ".gitkeep" and path.suffix.lower() != ".ipynb" and entry != report:
                continue
            if root == "results" and name != ".gitkeep" and path.suffix.lower() != ".csv" and not entry.startswith("results/figures/"):
                continue
            if path.is_file() and not path.is_symlink() and not any(fnmatch(name, p) for p in ignored_files):
                files[entry] = path
for name in ("Makefile", "requirements.txt", "README.md", "LICENSE"):
    if Path(name).is_file():
        files[name] = Path(name)
    else:
        print("WARNING - missing submission file:", name)

present = {n for n, p in files.items() if p.stat().st_size}
def check(condition, component):
    if not condition:
        print("WARNING - no submission evidence found:", component)

check(any(n.startswith("design/") and n.endswith(".ipynb") for n in present), "design notebook")
check(report in present, "Phase 1 report " + report)
def plain(text):
    return normalize("NFKD", text.casefold().replace(chr(0x111), "d")).encode("ascii", "ignore").decode()

def uml_evidence(path):
    suffix = path.suffix.lower()
    if suffix in {".puml", ".uml", ".plantuml", ".uxf"}:
        return True
    if suffix not in {".mmd", ".drawio", ".svg", ".png", ".jpg", ".jpeg", ".pdf"}:
        return False
    stem = re.sub(r"[_-]+", " ", plain(path.stem))
    if re.search(r"\b(uml|class(?:es)?|sequence|use case|so do lop|tuan tu)\b", stem):
        return True
    if suffix in {".mmd", ".drawio", ".svg"}:
        source = plain(path.read_text(encoding="utf-8-sig", errors="replace"))
        return any(marker in source for marker in ("uml", "classdiagram", "sequencediagram",
                   "statediagram", "class diagram", "so do lop", "so do tuan tu"))
    return False

check(any(uml_evidence(files[n]) for n in present if n.startswith("docs/diagrams/")),
      "UML diagram in docs/diagrams/ (source, label or filename)")

# Look for populated report sections as well as the CSVs that support them.
topics, written = set(), set()
for name in sorted(n for n in present if n.startswith("docs/")):
    path = files[name]
    if path.suffix.lower() == ".pdf":
        topics.add(plain(path.stem))
    if path.suffix.lower() != ".md":
        continue
    headings = [plain(path.stem)] + [""] * 6
    content = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8-sig", errors="replace"), flags=re.S)
    for line in content.splitlines():
        line = plain(line.strip())
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading:
            level = len(heading[1])
            headings[level:] = [heading[2]] + [""] * (6 - level)
        elif line.strip(" *_-`().") and not line.strip(" *_-`(").startswith(("todo", "tbd", "placeholder", "thanh vien 3 dien")):
            topics.update(headings)
            written.add(name)
for label, terms in (("workload", ("workload", "kich ban tai", "mo hinh tai", "tai thu")),
                     ("experiments", ("thi nghiem", "thuc nghiem", "experiment")),
                     ("validation", ("kiem chung", "doi chieu", "validation", "verification"))):
    check(any(term in topic for term in terms for topic in topics),
          label + " description (docs/ Markdown section or named PDF)")

experiments = ("e1_throughput_curves", "e2_capacity_delay", "e3_loom_vs_bun_sensitivity",
               "e4_closed_loop", "e5_special_scenarios", "raw_seed_runs")
for stem in experiments:
    check(f"results/{stem}.csv" in present, f"workload/experiment results/{stem}.csv")
check("results/verification_summary.csv" in present, "validation results/verification_summary.csv")
check(any(n.startswith("results/figures/") and Path(n).suffix.lower() in {".png", ".pdf"} for n in present),
      "figures in results/figures/")
check("docs/user_manual.md" in written, "user manual docs/user_manual.md")

archive = Path(f"Spe-Ass-final-{group}.zip")
with NamedTemporaryFile(dir=archive.parent, suffix=".tmp", delete=False) as handle:
    temporary = Path(handle.name)
try:
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as out:
        for name, source in sorted(files.items()):
            out.write(source, name)
    temporary.replace(archive)
finally:
    temporary.unlink(missing_ok=True)
with ZipFile(archive) as out:
    print(f"{archive} ({len(out.infolist())} files)")
    out.printdir()
endef
pack: export PACK_SCRIPT := $(PACK_SCRIPT)

pack:
	@python -X utf8 -c "import os; exec(os.environ['PACK_SCRIPT'])"

clean:
	@python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); [p.unlink() for p in pathlib.Path('.').glob('*.zip')]"
