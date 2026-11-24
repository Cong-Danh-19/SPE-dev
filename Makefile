.PHONY: install test run-exp plot all-pipeline pack clean

install:
	pip install -r requirements.txt

test:
	pytest -v

run-exp:
	python -m apps.benchmark_experiments_app

plot:
	python -m apps.plotting_app

all-pipeline: test run-exp plot

pack:
	zip -r Spe-Ass-final-GroupName.zip scenarios apps tests results docs design Makefile README.md requirements.txt -x "*/__pycache__/*" "*.pyc"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache *.zip
