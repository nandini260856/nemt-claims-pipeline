-- CLAIMS: turn every completed trip into claim lines.
-- Each trip (one leg) = one claim with two lines:
--   line 1 = base trip code (1 unit), line 2 = mileage code (1 unit per loaded mile, rounded up)
-- The 2-letter modifier is origin + destination, e.g. "RJ" = Residence -> dialysis facility.
-- Cancelled trips and no-shows are never billed.

CREATE OR REPLACE TABLE claims.claim_lines AS
WITH chargemaster AS (
    -- what the provider bills (always above any payer's allowed rate)
    SELECT hcpcs_code, round(max(allowed_rate) * 1.20, 2) AS charge_rate
    FROM staging.fee_schedule
    GROUP BY hcpcs_code
),
billable AS (
    SELECT t.*, m.payer_id
    FROM staging.trips t
    JOIN staging.members m USING (member_id)
    WHERE t.trip_status = 'completed'
),
lines AS (
    SELECT b.trip_id, b.payer_id, b.service_date, b.origin_type || b.destination_type AS modifier,
           p.hcpcs_code, p.code_type,
           CASE WHEN p.code_type = 'base' THEN 1 ELSE CAST(ceil(b.loaded_miles) AS INTEGER) END AS units
    FROM billable b
    JOIN staging.procedure_codes p ON p.level_of_service = b.level_of_service
)
SELECT
    'C' || l.trip_id                                        AS claim_id,
    CASE WHEN l.code_type = 'base' THEN 1 ELSE 2 END        AS line_number,
    l.hcpcs_code,
    l.modifier,
    l.units,
    round(l.units * cm.charge_rate, 2)                      AS charge_amount,
    round(l.units * fs.allowed_rate, 2)                     AS expected_allowed_amount
FROM lines l
JOIN chargemaster cm USING (hcpcs_code)
JOIN staging.fee_schedule fs
  ON fs.payer_id = l.payer_id
 AND fs.hcpcs_code = l.hcpcs_code
 AND l.service_date BETWEEN fs.effective_start AND fs.effective_end;
