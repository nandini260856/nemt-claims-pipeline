-- CLAIMS: one header row per claim, with totals rolled up from the lines.

CREATE OR REPLACE TABLE claims.claims AS
SELECT
    'C' || t.trip_id                     AS claim_id,
    t.trip_id,
    t.member_id,
    m.payer_member_id,
    m.payer_id,
    t.provider_id,
    pr.npi                               AS billing_npi,
    t.service_date,
    t.documentation_completed_date       AS claim_created_date,
    t.pickup_time,
    t.origin_type,
    t.destination_type,
    t.level_of_service,
    t.vehicle_type,
    t.loaded_miles,
    t.gps_miles,
    t.diagnosis_code,
    t.source_system,
    tot.total_charge,
    tot.expected_allowed
FROM staging.trips t
JOIN staging.members   m  USING (member_id)
JOIN staging.providers pr USING (provider_id)
JOIN (
    SELECT claim_id,
           sum(charge_amount)           AS total_charge,
           sum(expected_allowed_amount) AS expected_allowed
    FROM claims.claim_lines
    GROUP BY claim_id
) tot ON tot.claim_id = 'C' || t.trip_id
WHERE t.trip_status = 'completed';
