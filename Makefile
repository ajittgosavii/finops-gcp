# Developer entry points. `make dev` runs the API on demo data with no GCP and no
# key; `make test` runs every suite the way CI does; `make fmt` formats Terraform;
# `make deploy` submits the Cloud Build that ships both images.

REGION ?= us-central1

.PHONY: dev test fmt deploy install

install:
	pip install -e "packages/finops-core[dev]"
	pip install -r services/api/requirements.txt
	pip install -r services/ingest/requirements.txt

dev:
	cd services/api && DATA_SOURCE=demo uvicorn app.main:app --reload --port 8080

test:
	pytest packages/finops-core
	cd services/api && DATA_SOURCE=demo pytest
	cd services/ingest && pytest
	DATA_SOURCE=demo PYTHONPATH=services/api pytest tools

fmt:
	terraform -chdir=infra/terraform fmt -recursive

deploy:
	gcloud builds submit --config cloudbuild.yaml --substitutions=_REGION=$(REGION) .

artifacts:
	python tools/diagrams.py
	DATA_SOURCE=demo PYTHONPATH=services/api python tools/build_deck.py
	DATA_SOURCE=demo PYTHONPATH=services/api python tools/build_manual.py
	DATA_SOURCE=demo PYTHONPATH=services/api python tools/build_workbook.py
