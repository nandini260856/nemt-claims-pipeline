-- STAGING: members, eligibility spans and prior authorizations.

CREATE OR REPLACE TABLE staging.members AS
SELECT
    trim(member_id)               AS member_id,
    trim(payer_id)                AS payer_id,
    trim(payer_member_id)         AS payer_member_id,
    trim(first_name)              AS first_name,
    trim(last_name)               AS last_name,
    CAST(date_of_birth AS DATE)   AS date_of_birth,
    upper(trim(gender))           AS gender,
    trim(county)                  AS county,
    lower(trim(mobility_level))   AS mobility_level
FROM raw.members;

CREATE OR REPLACE TABLE staging.eligibility AS
SELECT
    trim(member_id)              AS member_id,
    trim(payer_id)               AS payer_id,
    CAST(coverage_start AS DATE) AS coverage_start,
    CAST(coverage_end AS DATE)   AS coverage_end
FROM raw.eligibility;

CREATE OR REPLACE TABLE staging.authorizations AS
SELECT
    trim(auth_number)             AS auth_number,
    trim(member_id)               AS member_id,
    trim(payer_id)                AS payer_id,
    lower(trim(level_of_service)) AS level_of_service,
    CAST(start_date AS DATE)      AS start_date,
    CAST(end_date AS DATE)        AS end_date,
    CAST(trips_approved AS INTEGER) AS trips_approved
FROM raw.authorizations;
