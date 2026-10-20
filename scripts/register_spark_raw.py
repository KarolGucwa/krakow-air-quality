"""Register the raw Parquet layer as tables `raw.<table>` in a local Spark metastore.

Used with the `spark_local` dbt target to run the Databricks/Spark SQL dialect locally:

    pip install "dbt-spark[session]"
    python scripts/register_spark_raw.py --raw-dir data/sample/raw
    dbt build --project-dir dbt --profiles-dir dbt --target spark_local
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pyspark.sql import SparkSession

TABLES = ["gios_station_metadata", "gios_sensor_metadata", "gios_sensors", "gios_measurements",
          "openmeteo_weather_hourly"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    spark = (SparkSession.builder.appName("register-raw")
             .config("spark.sql.warehouse.dir", "warehouse/spark-warehouse")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.parquet.inferTimestampNTZ.enabled", "false")
             .enableHiveSupport().getOrCreate())
    spark.sql("create database if not exists raw")
    for table in TABLES:
        location = (args.raw_dir / table).resolve()
        spark.sql(f"drop table if exists raw.{table}")
        spark.sql(f"create table raw.{table} using parquet location '{location.as_posix()}'")
        spark.sql(f"msck repair table raw.{table}")  # discover ingestion_date=... partitions
        print(table, spark.table(f"raw.{table}").count())
    spark.stop()


if __name__ == "__main__":
    main()
