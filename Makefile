.PHONY: install test test-fast run-exp run-exp-fast plot all-pipeline pack clean

install:
	pip install -r requirements.txt

test:
	python -m pytest -v

test-fast:
	python -m pytest -q tests/test_invariants.py -k "drains or arrival_cohort or round_robin or ladder_queue or cpu_percentile"

run-exp-fast:
	python -m apps.benchmark_experiments_app --quick

run-exp:
	python -m apps.benchmark_experiments_app

plot:
	python -m apps.plotting_app

all-pipeline: test run-exp plot

pack:
	zip -r Spe-Ass-final-GroupName.zip bkitevsim scenarios apps tests results docs design Makefile README.md requirements.txt -x "*/__pycache__/*" "*.pyc"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache *.zip
