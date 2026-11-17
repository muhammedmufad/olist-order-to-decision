"""Run the full pipeline: load raw CSVs into DuckDB, then build and test the dbt models."""
import subprocess
from pathlib import Path

from prefect import flow, get_run_logger, task

from load_raw import main as load_raw_main

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"


@task(retries=1, retry_delay_seconds=5)
def load_raw() -> None:
    load_raw_main()


@task
def dbt_build() -> None:
    logger = get_run_logger()
    result = subprocess.run(
        ["dbt", "build"], cwd=DBT_DIR, capture_output=True, text=True
    )
    logger.info(result.stdout[-1500:])
    if result.returncode != 0:
        raise RuntimeError("dbt build failed. See the log above.")


@flow(name="olist-pipeline")
def pipeline() -> None:
    load_raw()
    dbt_build()


if __name__ == "__main__":
    pipeline()