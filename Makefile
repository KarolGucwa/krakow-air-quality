# Kraków air quality pipeline – common commands.
# dbt always runs from the repository root, so relative paths in profiles/vars work.

DBT      = dbt --no-use-colors
DBT_ARGS = --project-dir dbt --profiles-dir dbt
SAMPLE_VARS = --vars '{raw_path: data/sample/raw}'

.PHONY: help install deps test lint extract dbt-build docs export analysis pipeline \
        demo demo-data demo-build dashboard demo-dashboard screenshots spark-check clean

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install:         ## install Python dependencies and the aq CLI
	pip install -r requirements-dev.txt
	pip install -e .

deps:            ## install dbt packages
	$(DBT) deps $(DBT_ARGS)

test:            ## unit tests of the extraction code
	pytest

lint:            ## ruff
	ruff check src tests analysis dashboard scripts

# ---------------------------------------------------------------- real data
extract:         ## daily extraction: metadata (weekly), last 3 days, recent weather
	aq daily

dbt-build:       ## dbt seed + run + test (fails on error-severity tests)
	$(DBT) source freshness $(DBT_ARGS) || true
	$(DBT) build $(DBT_ARGS)

docs:            ## dbt docs with lineage -> dbt/target (static_index.html is self-contained)
	$(DBT) docs generate $(DBT_ARGS) --static

export:          ## marts -> data/marts/*.parquet for the dashboard
	aq export-marts --data-mode real

analysis:        ## regression estimate of the coal-ban effect
	python analysis/coal_ban_effect.py --marts data/marts --out docs/analysis/coal_ban_effect.md

pipeline: extract dbt-build export analysis   ## full daily run on real data

dashboard:       ## dashboard on real data
	streamlit run dashboard/app.py

# ---------------------------------------------------------------- offline demo
demo-data:       ## synthetic raw layer in data/sample/raw
	aq generate-sample

demo-build:      ## dbt build on the synthetic data -> warehouse/demo.duckdb
	DUCKDB_PATH=warehouse/demo.duckdb $(DBT) build $(DBT_ARGS) $(SAMPLE_VARS)
	aq export-marts --warehouse warehouse/demo.duckdb --out data/sample/marts --data-mode synthetic
	python analysis/coal_ban_effect.py --marts data/sample/marts --out docs/analysis/coal_ban_effect_demo.md

demo: demo-data deps demo-build   ## everything offline, no API calls

demo-dashboard:  ## dashboard on the synthetic marts
	MARTS_DIR=data/sample/marts streamlit run dashboard/app.py

screenshots:     ## README images (dashboard must be running on :8501)
	DUCKDB_PATH=warehouse/demo.duckdb $(DBT) docs generate $(DBT_ARGS) $(SAMPLE_VARS) --static
	python scripts/take_screenshots.py --dashboard http://localhost:8501

spark-check:     ## build the project on local Spark (Databricks dialect); needs Java + requirements-spark.txt
	python scripts/register_spark_raw.py --raw-dir data/sample/raw
	TZ=UTC $(DBT) build $(DBT_ARGS) --target spark_local --exclude "test_type:unit"
	TZ=UTC $(DBT) test $(DBT_ARGS) --target spark_local --select "test_type:unit"

clean:
	rm -rf dbt/target dbt/target_spark dbt/dbt_packages dbt/logs logs warehouse/*.duckdb \
	       warehouse/spark-warehouse metastore_db derby.log data/sample
