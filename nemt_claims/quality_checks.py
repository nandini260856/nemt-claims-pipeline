"""
Data quality tests that run at the end of every pipeline run.
Each check is a SQL query that must return 0 rows. If any fail, the run fails,
so bad numbers never reach a report.
"""

CHECKS = {
    "fact_claim has one row per claim":
        "SELECT claim_id FROM marts.fact_claim GROUP BY claim_id HAVING count(*) > 1",
    "every claim has two service lines":
        "SELECT claim_id FROM marts.fact_claim_line GROUP BY claim_id HAVING count(*) <> 2",
    "no claim is missing payer, member or provider":
        "SELECT claim_id FROM marts.fact_claim WHERE payer_id IS NULL OR member_id IS NULL OR provider_id IS NULL",
    "every claim payer exists in dim_payer":
        "SELECT f.claim_id FROM marts.fact_claim f LEFT JOIN marts.dim_payer p USING (payer_id) WHERE p.payer_id IS NULL",
    "every service date exists in dim_date":
        "SELECT f.claim_id FROM marts.fact_claim f LEFT JOIN marts.dim_date d ON d.date_key = f.service_date_key WHERE d.date_key IS NULL",
    "every HELD claim has at least one reason":
        "SELECT claim_id FROM marts.fact_claim WHERE submission_status = 'HELD' AND failed_rule_count = 0",
    "no HELD claim was sent to a payer":
        "SELECT r.claim_id FROM raw.remit_claims r JOIN marts.fact_claim f USING (claim_id) WHERE f.submission_status = 'HELD'",
    "every READY claim got a remittance back":
        "SELECT claim_id FROM marts.fact_claim WHERE submission_status = 'READY' AND claim_status = 'PENDING'",
    "835 balances: charge = paid + adjustments (per claim)": """
        SELECT r.claim_id
        FROM raw.remit_claims r
        LEFT JOIN (SELECT claim_id, sum(adjustment_amount) AS adj FROM raw.remit_adjustments GROUP BY claim_id) a
          USING (claim_id)
        WHERE abs(r.charge_amount - r.paid_amount - coalesce(a.adj, 0)) > 0.01""",
    "835 charges match what we billed": """
        SELECT r.claim_id FROM raw.remit_claims r JOIN claims.claims c USING (claim_id)
        WHERE abs(r.charge_amount - c.total_charge) > 0.01""",
    "no cancelled or no-show trip was billed": """
        SELECT c.claim_id FROM claims.claims c JOIN staging.trips t USING (trip_id)
        WHERE t.trip_status <> 'completed'""",
    "no negative money amounts": """
        SELECT claim_id FROM marts.fact_claim
        WHERE total_charge < 0 OR paid_amount < 0 OR contractual_adjustment < 0""",
}


def run(con):
    failures = {}
    for name, sql in CHECKS.items():
        bad = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
        if bad:
            failures[name] = bad
    return failures
