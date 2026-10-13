-- VALIDATION: the list of checks every claim must pass before it is sent to a payer.
-- "likely_carc" is the denial code the payer would most likely return if we missed it.

CREATE OR REPLACE TABLE validation.rules AS
SELECT * FROM (VALUES
    ('ELIGIBILITY',      'Member was not covered by the plan on the date of service',            '27',  'denial'),
    ('PRIOR_AUTH',       'Plan requires a prior authorization and none covers this trip',        '197', 'denial'),
    ('DUPLICATE',        'Same member, date, pickup time and route already billed',              '18',  'denial'),
    ('MISSING_DX',       'No diagnosis code on the claim',                                       '16',  'denial'),
    ('TIMELY_FILING',    'Claim would reach the payer after its filing deadline',               '29',  'denial'),
    ('INVALID_NPI',      'Billing provider NPI fails the check-digit test',                      '16',  'denial'),
    ('MILEAGE_VARIANCE', 'Billed miles differ from GPS miles by more than 25% and 2 miles',      NULL,  'audit_risk'),
    ('LOS_MISMATCH',     'Vehicle sent does not match the level of service ordered and billed', NULL,  'audit_risk')
) AS t(rule_code, description, likely_carc, risk_type);
