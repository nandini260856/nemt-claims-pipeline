-- STAGING: reference tables. Cast text to proper types and tidy values.

CREATE OR REPLACE TABLE staging.payers AS
SELECT
    trim(payer_id)                      AS payer_id,
    trim(payer_name)                    AS payer_name,
    upper(trim(payer_type))             AS payer_type,
    CAST(filing_limit_days AS INTEGER)  AS filing_limit_days,
    lower(trim(auth_rule))              AS auth_rule
FROM raw.payers;

CREATE OR REPLACE TABLE staging.procedure_codes AS
SELECT
    upper(trim(hcpcs_code))       AS hcpcs_code,
    trim(description)             AS description,
    lower(trim(level_of_service)) AS level_of_service,
    lower(trim(code_type))        AS code_type
FROM raw.procedure_codes;

CREATE OR REPLACE TABLE staging.fee_schedule AS
SELECT
    trim(payer_id)                       AS payer_id,
    upper(trim(hcpcs_code))              AS hcpcs_code,
    CAST(allowed_rate AS DECIMAL(10, 2)) AS allowed_rate,
    CAST(effective_start AS DATE)        AS effective_start,
    CAST(effective_end AS DATE)          AS effective_end
FROM raw.fee_schedule;

CREATE OR REPLACE TABLE staging.providers AS
SELECT
    trim(provider_id)   AS provider_id,
    trim(provider_name) AS provider_name,
    trim(npi)           AS npi,
    trim(tax_id)        AS tax_id,
    trim(county)        AS county,
    upper(trim(state))  AS state
FROM raw.providers;
