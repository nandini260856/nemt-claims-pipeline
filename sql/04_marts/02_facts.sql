-- MARTS: fact tables (the measurable events).
--   fact_claim            one row per claim (header grain)
--   fact_claim_line       one row per service line
--   fact_validation_issue one row per claim per failed rule

CREATE OR REPLACE TABLE marts.fact_claim AS
WITH claim_adj AS (
    SELECT claim_id,
           max(CASE WHEN line_number = 0 AND group_code = 'CO' THEN carc_code END) AS denial_carc,
           sum(CASE WHEN carc_code = '45' THEN adjustment_amount ELSE 0 END)      AS contractual_adjustment
    FROM raw.remit_adjustments
    GROUP BY claim_id
)
SELECT
    c.claim_id,
    c.trip_id,
    c.member_id,
    c.payer_id,
    c.provider_id,
    CAST(strftime(c.service_date, '%Y%m%d') AS INTEGER)       AS service_date_key,
    CAST(strftime(c.claim_created_date, '%Y%m%d') AS INTEGER) AS claim_created_date_key,
    c.level_of_service,
    c.origin_type || c.destination_type                       AS route_modifier,
    s.submission_status,
    s.failed_rule_count,
    s.failed_rules,
    CASE
        WHEN s.submission_status = 'HELD'   THEN 'HELD'
        WHEN r.claim_status_code = '1'      THEN 'PAID'
        WHEN r.claim_status_code = '4'      THEN 'DENIED'
        ELSE 'PENDING'
    END                                                       AS claim_status,
    a.denial_carc,
    date_diff('day', c.service_date, c.claim_created_date)   AS days_service_to_claim,
    c.loaded_miles,
    c.total_charge,
    c.expected_allowed,
    coalesce(r.paid_amount, 0)                                AS paid_amount,
    coalesce(r.patient_responsibility, 0)                     AS patient_responsibility,
    coalesce(a.contractual_adjustment, 0)                     AS contractual_adjustment,
    CASE WHEN r.claim_status_code = '4' THEN c.total_charge ELSE 0 END AS denied_amount
FROM claims.claims c
JOIN validation.claim_status s USING (claim_id)
LEFT JOIN raw.remit_claims r USING (claim_id)
LEFT JOIN claim_adj a USING (claim_id);

CREATE OR REPLACE TABLE marts.fact_claim_line AS
WITH line_adj AS (
    SELECT claim_id, line_number,
           sum(CASE WHEN group_code = 'CO' THEN adjustment_amount ELSE 0 END) AS contractual_adjustment,
           sum(CASE WHEN group_code = 'PR' THEN adjustment_amount ELSE 0 END) AS patient_responsibility
    FROM raw.remit_adjustments
    WHERE line_number > 0
    GROUP BY claim_id, line_number
)
SELECT
    l.claim_id,
    l.line_number,
    l.hcpcs_code,
    l.modifier,
    l.units,
    l.charge_amount,
    l.expected_allowed_amount,
    coalesce(rl.paid_amount, 0)             AS paid_amount,
    coalesce(a.contractual_adjustment, 0)   AS contractual_adjustment,
    coalesce(a.patient_responsibility, 0)   AS patient_responsibility
FROM claims.claim_lines l
LEFT JOIN raw.remit_lines rl USING (claim_id, line_number)
LEFT JOIN line_adj a USING (claim_id, line_number);

CREATE OR REPLACE TABLE marts.fact_validation_issue AS
SELECT
    r.claim_id,
    r.rule_code,
    c.payer_id,
    c.provider_id,
    CAST(strftime(c.service_date, '%Y%m%d') AS INTEGER) AS service_date_key,
    c.total_charge                                     AS charge_at_risk
FROM validation.results r
JOIN claims.claims c USING (claim_id);
