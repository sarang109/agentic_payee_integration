PY ?= .venv/bin/python
export HF_HUB_OFFLINE ?= 1

.PHONY: setup zk test quick reproduce formal report docker docker-quick clean-results lock-v2 e11 e12

setup:
	python3.12 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.lock
	$(PY) -m pip install --no-deps -e .
	cd zk/js && npm ci --no-audit --no-fund

zk:
	bash zk/setup.sh

test:
	$(PY) -m pytest -q tests

quick:
	MERIDIAN_QUICK=1 $(PY) -m experiments.run_all

reproduce:
	$(PY) -m experiments.run_all

lock-v2:
	$(PY) -m experiments.prereg lock-v2

e11:
	$(PY) -m experiments.run_all --only e11

e12:
	$(PY) -m experiments.e12_independent run

formal:
	$(PY) -m experiments.formal_check

report:
	$(PY) -m experiments.figures && $(PY) -m experiments.report

docker:
	docker compose run --rm meridian

docker-quick:
	docker compose run --rm meridian-quick

clean-results:
	rm -rf results/raw results/tables results/figures results/REPORT.md results/MANIFEST.sha256.json results/run_status.json
