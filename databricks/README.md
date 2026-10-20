# Databricks version (Free Edition)

Same pipeline, different platform. I added this because Databricks shows up in a lot of
the data job ads I've been reading in Kraków, and I wanted to show the dbt models aren't
tied to DuckDB. The flow: a Unity Catalog volume → PySpark → Delta Lake (bronze) → the
same dbt project with `dbt-databricks` (silver/gold) → a scheduled Databricks Job.

```
GitHub Actions (or Databricks)        Databricks Free Edition
──────────────────────────────        ───────────────────────────────────────────────
aq daily ──► data/raw/*.parquet ──►  01_ingest_raw   → /Volumes/<cat>/krakow_air_raw/files
                                      02_raw_to_delta → <cat>.raw.*        (Delta, PySpark)
                                      dbt build       → staging / marts / dq / analysis
```

> **Where this stands:** the dbt SQL works on Apache Spark 3.5. The local `spark_local`
> target and the `spark-dialect` CI job build every model and pass all data and unit
> tests, with results matching DuckDB. What I haven't done yet is run the Asset Bundle,
> the notebooks and the `databricks` target on a real workspace, so I expect a few fixes
> (permissions, paths) on the first deploy.

## Setup

1. Create a Free Edition workspace: <https://www.databricks.com/learn/free-edition>.
2. Copy the ID of the serverless SQL warehouse (SQL Warehouses → your warehouse → ID).
3. Install the Databricks CLI and log in: `databricks auth login --host <workspace-url>`.
4. Push this repo to GitHub and put its URL in `git_url` in `databricks.yml`.
5. Deploy and run:

   ```bash
   cd databricks
   databricks bundle deploy -t dev --var="warehouse_id=<id>"
   databricks bundle run krakow_air_daily -t dev --var="warehouse_id=<id>"
   ```

## Running dbt against Databricks from a laptop

```bash
pip install dbt-databricks
export DATABRICKS_HOST=<workspace host, without https://>
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
export DATABRICKS_TOKEN=<personal access token>
dbt build --project-dir dbt --profiles-dir dbt --target databricks
```

## Ingest mode

By default (`ingest_mode: repo`) Databricks loads the Parquet files that the GitHub
Actions workflow commits, so the workspace doesn't need internet access. With
`ingest_mode: api` the extractor runs on Databricks itself. That only works if the
workspace can reach `api.gios.gov.pl` and `*.open-meteo.com`.
