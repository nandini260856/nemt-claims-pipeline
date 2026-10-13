"""Runs the full pipeline once, then checks the results make business sense."""
import pytest

from nemt_claims import quality_checks, run_pipeline


@pytest.fixture(scope="module")
def con():
    run_pipeline.main()
    c = run_pipeline.connect()
    yield c
    c.close()


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def test_all_quality_checks_pass(con):
    assert quality_checks.run(con) == {}


def test_every_planted_problem_is_caught(con):
    caught = {r[0] for r in con.execute("SELECT DISTINCT rule_code FROM validation.results").fetchall()}
    expected = {r[0] for r in con.execute("SELECT rule_code FROM validation.rules").fetchall()}
    assert caught == expected


def test_messy_values_are_cleaned(con):
    assert scalar(con, "SELECT count(*) FROM staging.trips WHERE trip_status NOT IN ('completed','cancelled','no_show')") == 0
    assert scalar(con, "SELECT count(*) FROM staging.trips WHERE diagnosis_code IS NOT NULL AND length(diagnosis_code) > 3 AND diagnosis_code NOT LIKE '%.%'") == 0  # 3-character codes like I10 have no dot


def test_validation_lowers_denial_rate(con):
    rates = dict(con.execute("SELECT scenario, denial_rate FROM reports.validation_impact").fetchall())
    assert rates["with_validation"] < rates["no_validation"] / 3


def test_only_unpredictable_denials_remain(con):
    codes = {r[0] for r in con.execute("SELECT DISTINCT denial_carc FROM marts.fact_claim WHERE claim_status='DENIED'").fetchall()}
    assert codes <= {"96"}


def test_money_reconciles_at_claim_and_line_level(con):
    diff = scalar(con, """
        SELECT abs(sum(f.paid_amount) - (SELECT sum(paid_amount) FROM marts.fact_claim_line))
        FROM marts.fact_claim f""")
    assert diff < 0.01
