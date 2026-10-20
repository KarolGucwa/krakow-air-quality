# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Ingest raw files into a Unity Catalog volume
# MAGIC
# MAGIC Two modes:
# MAGIC * `api`  – run the same Python extractor as GitHub Actions (`aq_pipeline.extract.daily`),
# MAGIC   writing partitioned Parquet into the volume. Needs outbound internet from serverless compute.
# MAGIC * `repo` – copy the raw Parquet files that the GitHub Actions workflow commits to `data/raw`
# MAGIC   (works even if the workspace cannot reach the APIs).
# MAGIC
# MAGIC Output: `/Volumes/<catalog>/krakow_air_raw/files/<table>/ingestion_date=YYYY-MM-DD/*.parquet`

# COMMAND ----------
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[2]
    except NameError:  # interactive notebook
        return Path.cwd().parents[1]


ROOT = repo_root()
sys.path.insert(0, str(ROOT / "src"))

parser = argparse.ArgumentParser()
parser.add_argument("--catalog", default="workspace")
parser.add_argument("--mode", choices=["api", "repo"], default="repo")
args, _ = parser.parse_known_args()

spark.sql(f"create schema if not exists {args.catalog}.krakow_air_raw")  # noqa: F821 (spark is injected)
spark.sql(f"create volume if not exists {args.catalog}.krakow_air_raw.files")  # noqa: F821
volume = Path(f"/Volumes/{args.catalog}/krakow_air_raw/files")

# COMMAND ----------
if args.mode == "api":
    from aq_pipeline import extract
    from aq_pipeline.config import load_settings

    settings = load_settings(ROOT / "config" / "pipeline.yml", raw_dir=volume)
    extract.daily(settings)
else:
    source = ROOT / "data" / "raw"
    for table_dir in sorted(p for p in source.iterdir() if p.is_dir() and not p.name.startswith("_")):
        shutil.copytree(table_dir, volume / table_dir.name, dirs_exist_ok=True)
        print(f"copied {table_dir.name}")
