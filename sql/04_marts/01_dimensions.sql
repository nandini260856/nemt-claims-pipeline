-- MARTS: dimension tables (the "who / what / when" of the star schema).

CREATE OR REPLACE TABLE marts.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE)                        AS full_date,
    year(d)                                AS year,
    quarter(d)                             AS quarter,
    month(d)                               AS month,
    strftime(d, '%b %Y')                   AS month_label,
    dayname(d)                             AS day_name,
    isodow(d) IN (6, 7)                    AS is_weekend
FROM generate_series(DATE '2025-01-01', DATE '2026-12-31', INTERVAL 1 DAY) AS t(d);

CREATE OR REPLACE TABLE marts.dim_payer AS
SELECT payer_id, payer_name, payer_type, filing_limit_days, auth_rule
FROM staging.payers;

CREATE OR REPLACE TABLE marts.dim_provider AS
SELECT provider_id, provider_name, npi, county, state
FROM staging.providers;

CREATE OR REPLACE TABLE marts.dim_member AS
SELECT
    member_id,
    payer_id,
    gender,
    county,
    mobility_level,
    date_diff('year', date_of_birth, DATE '2026-10-01') AS age,
    CASE
        WHEN date_diff('year', date_of_birth, DATE '2026-10-01') < 35 THEN '18-34'
        WHEN date_diff('year', date_of_birth, DATE '2026-10-01') < 50 THEN '35-49'
        WHEN date_diff('year', date_of_birth, DATE '2026-10-01') < 65 THEN '50-64'
        ELSE '65+'
    END AS age_band
FROM staging.members;   -- names and birth dates stay out of the mart (minimum necessary PHI)

CREATE OR REPLACE TABLE marts.dim_procedure AS
SELECT hcpcs_code, description, level_of_service, code_type
FROM staging.procedure_codes;

CREATE OR REPLACE TABLE marts.dim_adjustment_reason AS
SELECT * FROM (VALUES
    ('16',  'Claim lacks information or has submission/billing errors'),
    ('18',  'Exact duplicate claim/service'),
    ('2',   'Coinsurance amount'),
    ('27',  'Expenses incurred after coverage terminated'),
    ('29',  'The time limit for filing has expired'),
    ('45',  'Charge exceeds fee schedule/maximum allowable (contractual)'),
    ('96',  'Non-covered charge(s)'),
    ('197', 'Precertification/authorization/notification absent')
) AS t(carc_code, carc_description);

CREATE OR REPLACE TABLE marts.dim_validation_rule AS
SELECT * FROM validation.rules;
