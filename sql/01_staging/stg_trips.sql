-- STAGING: trips. This is where the messy source data gets cleaned:
--   * trip status arrives as "completed", "COMPLETED" or "Completed"
--   * diagnosis codes sometimes arrive without the dot ("N186" -> "N18.6")
--   * blank strings become real NULLs

CREATE OR REPLACE TABLE staging.trips AS
WITH cleaned AS (
    SELECT
        trim(trip_id)                                   AS trip_id,
        trim(member_id)                                 AS member_id,
        trim(provider_id)                               AS provider_id,
        CAST(service_date AS DATE)                      AS service_date,
        trim(pickup_time)                               AS pickup_time,
        upper(trim(origin_type))                        AS origin_type,
        upper(trim(destination_type))                   AS destination_type,
        lower(trim(level_of_service))                   AS level_of_service,
        lower(trim(vehicle_type))                       AS vehicle_type,
        CAST(loaded_miles AS DECIMAL(8, 1))             AS loaded_miles,
        CAST(gps_miles AS DECIMAL(8, 1))                AS gps_miles,
        upper(nullif(trim(diagnosis_code), ''))         AS dx_raw,
        lower(trim(trip_status))                        AS trip_status,
        CAST(documentation_completed_date AS DATE)      AS documentation_completed_date,
        lower(trim(source_system))                      AS source_system
    FROM raw.trips
)
SELECT
    * EXCLUDE (dx_raw),
    CASE
        WHEN dx_raw IS NULL THEN NULL
        WHEN dx_raw NOT LIKE '%.%' AND length(dx_raw) > 3
            THEN substr(dx_raw, 1, 3) || '.' || substr(dx_raw, 4)
        ELSE dx_raw
    END AS diagnosis_code
FROM cleaned;
