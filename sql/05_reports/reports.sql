-- REPORTS: business-ready views built only from the star schema.

CREATE OR REPLACE VIEW reports.kpi_summary AS
SELECT
    (SELECT count(*) FROM staging.trips)                                       AS total_trips,
    count(*)                                                                   AS claims_built,
    count(*) FILTER (WHERE submission_status = 'READY')                        AS claims_ready,
    count(*) FILTER (WHERE submission_status = 'HELD')                         AS claims_held,
    round(count(*) FILTER (WHERE submission_status = 'READY') / count(*), 4)   AS clean_claim_rate,
    count(*) FILTER (WHERE claim_status = 'PAID')                              AS claims_paid,
    count(*) FILTER (WHERE claim_status = 'DENIED')                            AS claims_denied,
    round(count(*) FILTER (WHERE claim_status = 'DENIED')
          / count(*) FILTER (WHERE submission_status = 'READY'), 4)            AS denial_rate,
    round(sum(total_charge), 2)                                                AS total_charges,
    round(sum(paid_amount), 2)                                                 AS total_paid,
    round(sum(paid_amount + patient_responsibility)
          / sum(expected_allowed) FILTER (WHERE submission_status = 'READY'), 4) AS net_collection_rate
FROM marts.fact_claim;

CREATE OR REPLACE VIEW reports.hold_reasons AS
SELECT
    i.rule_code,
    r.description,
    r.risk_type,
    count(*)                       AS claims,
    round(sum(i.charge_at_risk), 2) AS charges_at_risk
FROM marts.fact_validation_issue i
JOIN marts.dim_validation_rule r USING (rule_code)
GROUP BY ALL
ORDER BY claims DESC;

CREATE OR REPLACE VIEW reports.denials_by_reason AS
SELECT
    f.denial_carc                 AS carc_code,
    d.carc_description,
    count(*)                      AS claims,
    round(sum(f.denied_amount), 2) AS denied_amount
FROM marts.fact_claim f
JOIN marts.dim_adjustment_reason d ON d.carc_code = f.denial_carc
WHERE f.claim_status = 'DENIED'
GROUP BY ALL
ORDER BY claims DESC;

CREATE OR REPLACE VIEW reports.payer_scorecard AS
SELECT
    p.payer_name,
    count(*)                                                                  AS claims,
    round(count(*) FILTER (WHERE f.submission_status = 'READY') / count(*), 4) AS clean_claim_rate,
    round(count(*) FILTER (WHERE f.claim_status = 'DENIED')
          / nullif(count(*) FILTER (WHERE f.submission_status = 'READY'), 0), 4) AS denial_rate,
    round(sum(f.paid_amount), 2)                                              AS paid_amount
FROM marts.fact_claim f
JOIN marts.dim_payer p USING (payer_id)
GROUP BY ALL
ORDER BY claims DESC;

CREATE OR REPLACE VIEW reports.monthly_trend AS
SELECT
    d.year, d.month, d.month_label,
    count(*)                                                AS claims,
    count(*) FILTER (WHERE f.submission_status = 'HELD')    AS held,
    count(*) FILTER (WHERE f.claim_status = 'DENIED')       AS denied,
    round(sum(f.paid_amount), 2)                            AS paid_amount
FROM marts.fact_claim f
JOIN marts.dim_date d ON d.date_key = f.service_date_key
GROUP BY ALL
ORDER BY d.year, d.month;
