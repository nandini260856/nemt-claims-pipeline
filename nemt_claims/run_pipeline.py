"""
Run the whole pipeline end to end:

    python -m nemt_claims.run_pipeline

Each step is a plain function so the same steps can be called from Airflow
(see dags/nemt_claims_dag.py).
"""
import time

import duckdb

from . import config, edi_835, edi_837, generate_data, payer_simulator, quality_checks, report
from .validators import is_valid_npi

SCHEMAS = ["raw", "staging", "claims", "validation", "marts", "reports"]
RAW_TABLES = ["payers", "procedure_codes", "fee_schedule", "providers", "members",
              "eligibility", "authorizations", "trips"]


def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.WAREHOUSE))
    for s in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    # make the Python NPI checker callable from SQL
    con.create_function("is_valid_npi", is_valid_npi, ["VARCHAR"], "BOOLEAN")
    return con


def run_sql_folder(con, folder):
    files = sorted((config.SQL_DIR / folder).glob("*.sql"))
    for f in files:
        con.execute(f.read_text())
    return [f.name for f in files]


# ---------------- steps ----------------
def step_generate(con):
    return generate_data.main()


def step_load_raw(con):
    # Everything lands as text first, exactly like files in an S3 raw zone.
    for t in RAW_TABLES:
        path = config.RAW_DIR / f"{t}.csv"
        con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS "
                    f"SELECT * FROM read_csv('{path}', header = true, all_varchar = true)")
    return {t: con.execute(f"SELECT count(*) FROM raw.{t}").fetchone()[0] for t in RAW_TABLES}


def step_staging(con):
    return run_sql_folder(con, "01_staging")


def step_build_claims(con):
    run_sql_folder(con, "02_claims")
    return con.execute("SELECT count(*) FROM claims.claims").fetchone()[0]


def step_validate(con):
    run_sql_folder(con, "03_validation")
    return dict(con.execute(
        "SELECT submission_status, count(*) FROM validation.claim_status GROUP BY 1").fetchall())


def step_export_837(con):
    return edi_837.export(con)


def step_payer_adjudication(con):
    return payer_simulator.run(con)


def step_load_835(con):
    return edi_835.load(con, config.INBOUND_DIR)


def step_marts(con):
    return run_sql_folder(con, "04_marts")


def step_reports(con):
    return run_sql_folder(con, "05_reports")


def step_quality_checks(con):
    failures = quality_checks.run(con)
    if failures:
        raise RuntimeError(f"Data quality checks failed: {failures}")
    return f"{len(quality_checks.CHECKS)} checks passed"


def step_report(con):
    return str(report.build(con))


STEPS = [
    ("generate_source_data", step_generate),
    ("load_raw", step_load_raw),
    ("staging", step_staging),
    ("build_claims", step_build_claims),
    ("validate_claims", step_validate),
    ("export_837", step_export_837),
    ("payer_adjudication", step_payer_adjudication),
    ("load_835", step_load_835),
    ("build_marts", step_marts),
    ("build_reports", step_reports),
    ("quality_checks", step_quality_checks),
    ("write_report", step_report),
]


def run_step(name):
    """Used by Airflow: run one step with its own connection."""
    fn = dict(STEPS)[name]
    con = connect()
    try:
        return fn(con)
    finally:
        con.close()


def main():
    con = connect()
    start = time.time()
    for name, fn in STEPS:
        t0 = time.time()
        result = fn(con)
        print(f"[{time.time() - t0:5.1f}s] {name:<22} {result}")
    con.close()
    print(f"Pipeline finished in {time.time() - start:.1f}s. Warehouse: {config.WAREHOUSE}")


if __name__ == "__main__":
    main()
