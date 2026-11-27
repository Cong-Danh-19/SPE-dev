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

GROUP ?= YY9B
pack: export PACK_GROUP := $(value GROUP)
pack:
	@python -m apps.package_submission --group "$$PACK_GROUP"

clean:
	@python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); [p.unlink() for p in pathlib.Path('.').glob('*.zip')]"

.PHONY: design-report design-runs
design-runs:
	python -m apps.design_experiments_app --group E1
	python -m apps.design_experiments_app --group E2
	python -m apps.design_experiments_app --group E3
	python -m apps.design_experiments_app --group E4
	python -m apps.design_experiments_app --group E5
	python -m apps.design_experiments_app --group E6

design-report: design-runs
	python -m apps.design_report_app
