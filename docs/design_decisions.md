# Design decisions

**Land everything as text first.** Raw tables keep the data exactly as received, all as strings. Typing and cleaning happen in staging, where they can be read and tested. A bad value in a source file never crashes the load. It shows up in staging, where it can be found.

**SQL for set logic, Python for what SQL is bad at.** Seven of the eight validation rules are SQL, because they are joins and window functions. The NPI check-digit test is written in Python and registered as a database function (`is_valid_npi`), so it can still be used inside SQL. EDI writing and parsing are in Python because they work on text.

**Hold, don't drop.** A claim that fails a rule is never deleted. It is marked `HELD` with every reason listed (`failed_rules`), so an operations team can fix and resend it. `fact_validation_issue` keeps one row per claim per rule, so a claim with two problems is counted under both.

**Two kinds of risk.** Most rules prevent a denial. Two rules, `MILEAGE_VARIANCE` and `LOS_MISMATCH`, catch claims the payer would pay, but that are a compliance risk. Treating these separately shows that "paid" doesn't always mean "correct".

**An independent payer.** The payer simulator reads its own copy of eligibility and authorizations instead of reusing the validation results. If it reused them, measuring the value of validation would be circular. It also adds a small number of random denials that no rule could predict.

**Reconcile every dollar.** The quality checks prove that each 835 claim balances (charge = paid + adjustments), that the charges in the 835 match what was billed, and that the claim and line totals agree. Claims reporting is only trusted when the money ties out.

**Minimum necessary PHI in the mart.** Names and birth dates stay in staging. The reporting layer keeps only an age band, county and mobility level, which is all a dashboard needs.

**Steps are plain functions.** `run_pipeline.STEPS` is a list of small functions. The command line runs them in order. Airflow runs the same functions as separate tasks with retries. The logic lives in one place.

**Runs anywhere, maps to AWS.** DuckDB lets anyone run the project in seconds with no cloud account. The SQL is standard and moves to Redshift or Athena with small changes. See the AWS table in the README.
