-- How the star schema would be created in Amazon Redshift.
-- DISTKEY spreads rows across nodes on the most common join column;
-- SORTKEY speeds up date-range filters, which almost every claims report uses.

CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE marts.dim_payer (
    payer_id          VARCHAR(10)  PRIMARY KEY,
    payer_name        VARCHAR(100) NOT NULL,
    payer_type        VARCHAR(30),
    filing_limit_days SMALLINT,
    auth_rule         VARCHAR(30)
) DISTSTYLE ALL;

CREATE TABLE marts.dim_date (
    date_key    INTEGER PRIMARY KEY,
    full_date   DATE NOT NULL,
    year        SMALLINT,
    quarter     SMALLINT,
    month       SMALLINT,
    month_label VARCHAR(10),
    day_name    VARCHAR(10),
    is_weekend  BOOLEAN
) DISTSTYLE ALL;

CREATE TABLE marts.dim_member (
    member_id      VARCHAR(12) PRIMARY KEY,
    payer_id       VARCHAR(10),
    gender         CHAR(1),
    county         VARCHAR(40),
    mobility_level VARCHAR(20),
    age            SMALLINT,
    age_band       VARCHAR(10)
) DISTKEY (member_id);

CREATE TABLE marts.dim_provider (
    provider_id   VARCHAR(10) PRIMARY KEY,
    provider_name VARCHAR(100),
    npi           CHAR(10),
    county        VARCHAR(40),
    state         CHAR(2)
) DISTSTYLE ALL;

CREATE TABLE marts.dim_procedure (
    hcpcs_code       CHAR(5) PRIMARY KEY,
    description      VARCHAR(120),
    level_of_service VARCHAR(20),
    code_type        VARCHAR(10)
) DISTSTYLE ALL;

CREATE TABLE marts.fact_claim (
    claim_id               VARCHAR(15) PRIMARY KEY,
    trip_id                VARCHAR(12),
    member_id              VARCHAR(12) REFERENCES marts.dim_member (member_id),
    payer_id               VARCHAR(10) REFERENCES marts.dim_payer (payer_id),
    provider_id            VARCHAR(10) REFERENCES marts.dim_provider (provider_id),
    service_date_key       INTEGER     REFERENCES marts.dim_date (date_key),
    claim_created_date_key INTEGER     REFERENCES marts.dim_date (date_key),
    level_of_service       VARCHAR(20),
    route_modifier         CHAR(2),
    submission_status      VARCHAR(10),
    failed_rule_count      SMALLINT,
    failed_rules           VARCHAR(200),
    claim_status           VARCHAR(10),
    denial_carc            VARCHAR(5),
    days_service_to_claim  SMALLINT,
    loaded_miles           DECIMAL(8, 1),
    total_charge           DECIMAL(12, 2),
    expected_allowed       DECIMAL(12, 2),
    paid_amount            DECIMAL(12, 2),
    patient_responsibility DECIMAL(12, 2),
    contractual_adjustment DECIMAL(12, 2),
    denied_amount          DECIMAL(12, 2)
) DISTKEY (member_id) SORTKEY (service_date_key);

CREATE TABLE marts.fact_claim_line (
    claim_id                VARCHAR(15),
    line_number             SMALLINT,
    hcpcs_code              CHAR(5) REFERENCES marts.dim_procedure (hcpcs_code),
    modifier                CHAR(2),
    units                   SMALLINT,
    charge_amount           DECIMAL(12, 2),
    expected_allowed_amount DECIMAL(12, 2),
    paid_amount             DECIMAL(12, 2),
    contractual_adjustment  DECIMAL(12, 2),
    patient_responsibility  DECIMAL(12, 2),
    PRIMARY KEY (claim_id, line_number)
) DISTKEY (claim_id) SORTKEY (claim_id);

-- Loading from S3 after the pipeline writes Parquet to the curated zone:
-- COPY marts.fact_claim FROM 's3://<bucket>/curated/fact_claim/'
-- IAM_ROLE '<redshift-role-arn>' FORMAT AS PARQUET;
