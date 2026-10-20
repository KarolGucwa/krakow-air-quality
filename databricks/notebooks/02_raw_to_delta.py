# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Raw Parquet → Delta tables (bronze)
# MAGIC
# MAGIC Reads every raw table from the volume with PySpark and (re)writes it as a Delta table
# MAGIC `<catalog>.raw.<table>`, the names the dbt sources expect. The raw layer is small
# MAGIC (a few million rows), so a full overwrite keeps it simple and idempotent; for larger
# MAGIC volumes this would become Auto Loader (`cloudFiles`) with incremental appends.

# COMMAND ----------
import argparse

from pyspark.sql import functions as F

parser = argparse.ArgumentParser()
parser.add_argument("--catalog", default="workspace")
args, _ = parser.parse_known_args()

volume = f"/Volumes/{args.catalog}/krakow_air_raw/files"
tables = ["gios_station_metadata", "gios_sensor_metadata", "gios_sensors", "gios_measurements",
          "openmeteo_weather_hourly"]

spark.sql(f"create schema if not exists {args.catalog}.raw")  # noqa: F821

# COMMAND ----------
for table in tables:
    df = (spark.read.option("mergeSchema", "true").parquet(f"{volume}/{table}")  # noqa: F821
          .withColumn("_loaded_at", F.current_timestamp()))
    target = f"{args.catalog}.raw.{table}"
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(target))
    print(f"{target}: {df.count()} rows")

# COMMAND ----------
# Quick bronze-level check: ingestion batches per day for measurements
display(  # noqa: F821
    spark.table(f"{args.catalog}.raw.gios_measurements")  # noqa: F821
    .groupBy("ingestion_date", "source_system").count().orderBy(F.desc("ingestion_date")).limit(20)
)
