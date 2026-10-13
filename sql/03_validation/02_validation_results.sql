-- VALIDATION: one row for every rule a claim fails.
-- is_valid_npi() is a Python function registered with the database (see nemt_claims/validators.py).

CREATE OR REPLACE TABLE validation.results AS

-- 1. Eligibility: was the member covered on the service date?
SELECT c.claim_id, 'ELIGIBILITY' AS rule_code
FROM claims.claims c
WHERE NOT EXISTS (
    SELECT 1 FROM staging.eligibility e
    WHERE e.member_id = c.member_id
      AND e.payer_id  = c.payer_id
      AND c.service_date BETWEEN e.coverage_start AND e.coverage_end
)

UNION ALL
-- 2. Prior authorization: required by some plans for all trips, by others only for stretcher/ambulance
SELECT c.claim_id, 'PRIOR_AUTH'
FROM claims.claims c
JOIN staging.payers p USING (payer_id)
WHERE (p.auth_rule = 'all'
       OR (p.auth_rule = 'stretcher_ambulance' AND c.level_of_service IN ('stretcher_van', 'ambulance')))
  AND NOT EXISTS (
    SELECT 1 FROM staging.authorizations a
    WHERE a.member_id = c.member_id
      AND a.payer_id  = c.payer_id
      AND a.level_of_service = c.level_of_service
      AND c.service_date BETWEEN a.start_date AND a.end_date
)

UNION ALL
-- 3. Duplicates: keep the driver-app record, flag the later copies
SELECT claim_id, 'DUPLICATE'
FROM (
    SELECT claim_id,
           row_number() OVER (
               PARTITION BY member_id, service_date, pickup_time, origin_type, destination_type
               ORDER BY (source_system = 'driver_app') DESC, trip_id
           ) AS copy_number
    FROM claims.claims
)
WHERE copy_number > 1

UNION ALL
-- 4. Missing diagnosis
SELECT claim_id, 'MISSING_DX'
FROM claims.claims
WHERE diagnosis_code IS NULL

UNION ALL
-- 5. Timely filing: days from service to claim creation vs the plan's limit
SELECT c.claim_id, 'TIMELY_FILING'
FROM claims.claims c
JOIN staging.payers p USING (payer_id)
WHERE date_diff('day', c.service_date, c.claim_created_date) > p.filing_limit_days

UNION ALL
-- 6. NPI check digit (Python UDF)
SELECT claim_id, 'INVALID_NPI'
FROM claims.claims
WHERE NOT is_valid_npi(billing_npi)

UNION ALL
-- 7. Mileage: billed miles vs GPS miles
SELECT claim_id, 'MILEAGE_VARIANCE'
FROM claims.claims
WHERE abs(loaded_miles - gps_miles) > 2
  AND abs(loaded_miles - gps_miles) / nullif(gps_miles, 0) > 0.25

UNION ALL
-- 8. Level of service: billed wheelchair van but a sedan showed up (or similar)
SELECT claim_id, 'LOS_MISMATCH'
FROM claims.claims
WHERE vehicle_type <> level_of_service;
