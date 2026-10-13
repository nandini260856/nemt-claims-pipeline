-- VALIDATION: final decision per claim. READY = send to payer, HELD = fix first.

CREATE OR REPLACE TABLE validation.claim_status AS
SELECT
    c.claim_id,
    CASE WHEN count(r.rule_code) = 0 THEN 'READY' ELSE 'HELD' END   AS submission_status,
    count(r.rule_code)                                              AS failed_rule_count,
    string_agg(r.rule_code, ', ' ORDER BY r.rule_code)              AS failed_rules
FROM claims.claims c
LEFT JOIN validation.results r USING (claim_id)
GROUP BY c.claim_id;
