"""
Step 0: create realistic, fully synthetic source data.

No real people, plans or providers are used. The data copies the shape of what a
non-emergency medical transportation (NEMT) company sees: members, health plans,
eligibility, prior authorizations, transport providers and trips.

Real-world problems are planted on purpose so the pipeline has something to catch:
ineligible members, missing authorizations, duplicate trips, missing diagnoses,
mileage that doesn't match GPS, the wrong vehicle type, late paperwork,
an invalid provider NPI and messy text values.
"""
import csv
import random
from datetime import date, timedelta

from . import config
from .validators import npi_check_digit

rng = random.Random(config.SEED)

FIRST = ["Ana", "Ben", "Carla", "Dev", "Elena", "Femi", "Grace", "Hugo", "Ines", "Jamal",
         "Kira", "Luis", "Maya", "Nora", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara",
         "Uma", "Victor", "Wen", "Yara", "Zane"]
LAST = ["Adams", "Brooks", "Chen", "Diaz", "Evans", "Fischer", "Garcia", "Hill", "Ito",
        "Jones", "Khan", "Lopez", "Moore", "Nguyen", "Owens", "Patel", "Reyes", "Silva",
        "Turner", "Vega", "Walsh", "Young"]
COUNTIES = ["Fulton", "DeKalb", "Cobb", "Gwinnett", "Clayton", "Henry"]

# Fictional health plans. auth_rule: which trips need a prior authorization.
PAYERS = [
    # payer_id, name, type, filing limit (days), auth_rule
    ("P001", "State Medicaid Fee-for-Service", "MEDICAID_FFS", 365, "stretcher_ambulance"),
    ("P002", "Sunrise Health Plan (Medicaid MCO)", "MEDICAID_MCO", 180, "all"),
    ("P003", "Harbor Medicare Advantage", "MEDICARE_ADVANTAGE", 120, "stretcher_ambulance"),
    ("P004", "Lakeside Community Care (Medicaid MCO)", "MEDICAID_MCO", 90, "all"),
]
PAYER_MIX = [0.35, 0.30, 0.15, 0.20]

# HCPCS codes used for NEMT. Each level of service has a base (per trip) code
# and a mileage (per mile) code.
PROCEDURES = [
    # code, description, level_of_service, code_type, base fee
    ("A0100", "Non-emergency transport; taxi/sedan", "sedan", "base", 22.00),
    ("S0215", "Non-emergency transport; mileage, per mile", "sedan", "mileage", 1.75),
    ("A0130", "Non-emergency transport; wheelchair van", "wheelchair_van", "base", 38.00),
    ("S0209", "Wheelchair van, mileage, per mile", "wheelchair_van", "mileage", 2.40),
    ("T2005", "Non-emergency transport; stretcher van", "stretcher_van", "base", 85.00),
    ("T2049", "Non-emergency transport; stretcher van, mileage, per mile", "stretcher_van", "mileage", 3.10),
    ("A0428", "Ambulance service, BLS, non-emergency transport", "ambulance", "base", 210.00),
    ("A0425", "Ground mileage, per statute mile", "ambulance", "mileage", 7.50),
]
LOS_MIX = {"sedan": 0.55, "wheelchair_van": 0.30, "stretcher_van": 0.10, "ambulance": 0.05}

# Origin/destination pairs (these become the 2-letter HCPCS modifier, e.g. "RJ"
# = Residence to non-hospital dialysis facility) with a matching diagnosis.
LEGS = [
    ("R", "J", ["N18.6", "Z99.2"]),        # home -> dialysis
    ("J", "R", ["N18.6", "Z99.2"]),        # dialysis -> home
    ("R", "P", ["E11.9", "I10", "F32.9", "M54.50", "J44.9"]),  # home -> doctor
    ("P", "R", ["E11.9", "I10", "F32.9", "M54.50", "J44.9"]),
    ("R", "H", ["Z51.11", "C50.919", "I50.9"]),  # home -> hospital outpatient
    ("H", "R", ["Z51.11", "C50.919", "I50.9"]),
    ("R", "D", ["R07.9", "Z01.818"]),       # home -> diagnostic center
    ("D", "R", ["R07.9", "Z01.818"]),
]
LEG_MIX = [0.22, 0.22, 0.17, 0.17, 0.07, 0.07, 0.04, 0.04]


def make_npi(valid=True):
    body = "1" + "".join(str(rng.randint(0, 9)) for _ in range(8))
    check = npi_check_digit(body)
    if not valid:
        check = (check + 3) % 10
    return body + str(check)


def rand_date(start, end):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def write(name, header, rows):
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RAW_DIR / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def main():
    counts = {}

    # ---------- payers, procedure codes, fee schedule ----------
    counts["payers"] = write("payers", ["payer_id", "payer_name", "payer_type",
                                        "filing_limit_days", "auth_rule"], PAYERS)
    counts["procedure_codes"] = write("procedure_codes", ["hcpcs_code", "description",
                                      "level_of_service", "code_type"],
                                      [p[:4] for p in PROCEDURES])
    fee_rows = []
    for pid, *_ in PAYERS:
        factor = {"P001": 1.00, "P002": 1.08, "P003": 1.15, "P004": 1.04}[pid]
        for code, _, _, _, fee in PROCEDURES:
            fee_rows.append([pid, code, round(fee * factor, 2), "2026-01-01", "2026-12-31"])
    counts["fee_schedule"] = write("fee_schedule", ["payer_id", "hcpcs_code", "allowed_rate",
                                   "effective_start", "effective_end"], fee_rows)

    # ---------- transport providers (one has a bad NPI) ----------
    providers = []
    for i in range(1, 41):
        pid = f"TP{i:03d}"
        providers.append([pid, f"{rng.choice(LAST)} {rng.choice(['Transit', 'Mobility', 'Medical Rides', 'Care Transport'])} LLC",
                          make_npi(valid=(i != 17)), f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}",
                          rng.choice(COUNTIES), "GA"])
    counts["providers"] = write("providers", ["provider_id", "provider_name", "npi", "tax_id",
                                "county", "state"], providers)

    # ---------- members + eligibility ----------
    members, eligibility = [], []
    for i in range(1, config.N_MEMBERS + 1):
        mid = f"M{i:07d}"
        payer = rng.choices([p[0] for p in PAYERS], PAYER_MIX)[0]
        los = rng.choices(list(LOS_MIX), list(LOS_MIX.values()))[0]
        dob = rand_date(date(1940, 1, 1), date(2004, 12, 31))
        members.append([mid, payer, f"{payer[-1]}{rng.randint(100000000, 999999999)}",
                        rng.choice(FIRST), rng.choice(LAST), dob.isoformat(),
                        rng.choice(["F", "M"]), rng.choice(COUNTIES), los])
        start = date(2025, rng.randint(1, 12), 1)
        end = date(2026, 12, 31)
        if rng.random() < 0.10:  # coverage ends mid-year
            end = rand_date(date(2026, 3, 1), date(2026, 8, 31))
        eligibility.append([mid, payer, start.isoformat(), end.isoformat()])
    counts["members"] = write("members", ["member_id", "payer_id", "payer_member_id", "first_name",
                              "last_name", "date_of_birth", "gender", "county",
                              "mobility_level"], members)
    counts["eligibility"] = write("eligibility", ["member_id", "payer_id", "coverage_start",
                                  "coverage_end"], eligibility)

    # ---------- prior authorizations (monthly), with ~4% missing ----------
    auth_rule = {p[0]: p[4] for p in PAYERS}
    auths, n = [], 0
    for m in members:
        mid, payer, los = m[0], m[1], m[8]
        needs = auth_rule[payer] == "all" or los in ("stretcher_van", "ambulance")
        if not needs:
            continue
        for month in range(1, 10):
            if rng.random() < 0.04:
                continue  # authorization never obtained
            n += 1
            start = date(2026, month, 1)
            end = (date(2026, month + 1, 1) - timedelta(days=1))
            auths.append([f"AUTH{n:07d}", mid, payer, los, start.isoformat(), end.isoformat(), 40])
    counts["authorizations"] = write("authorizations", ["auth_number", "member_id", "payer_id",
                                     "level_of_service", "start_date", "end_date",
                                     "trips_approved"], auths)

    # ---------- trips ----------
    filing = {p[0]: p[3] for p in PAYERS}
    trips = []
    for i in range(1, config.N_TRIPS + 1):
        m = rng.choice(members)
        mid, payer, los = m[0], m[1], m[8]
        o, d, dxs = rng.choices(LEGS, LEG_MIX)[0]
        svc = rand_date(config.SERVICE_START, config.SERVICE_END)
        miles = round(min(rng.lognormvariate(2.1, 0.55) * (1.6 if los == "ambulance" else 1), 75), 1)
        gps = round(miles * rng.uniform(0.95, 1.06), 1)
        vehicle = los
        dx = rng.choice(dxs)
        status = rng.choices(["completed", "cancelled", "no_show"], [0.93, 0.04, 0.03])[0]
        doc_date = svc + timedelta(days=rng.randint(1, 14))
        source = "driver_app"

        if status == "completed":
            r = rng.random()
            if r < 0.02:      # GPS says the trip was much shorter/longer than billed
                gps = round(miles * rng.choice([rng.uniform(0.3, 0.6), rng.uniform(1.5, 2.0)]), 1)
            elif r < 0.04:    # driver sent a different vehicle than ordered
                vehicle = rng.choice([v for v in LOS_MIX if v != los])
            elif r < 0.06:    # diagnosis missing on the trip order
                dx = ""
            elif r < 0.085:   # paperwork finished after the payer's filing deadline
                limit = filing[payer]
                latest = config.RUN_DATE - timedelta(days=limit + 5)
                if latest > config.SERVICE_START:
                    svc = rand_date(config.SERVICE_START, latest)
                    doc_date = min(svc + timedelta(days=limit + rng.randint(5, 60)), config.RUN_DATE)

        # messy formatting from different source systems
        if rng.random() < 0.15:
            status = status.upper() if rng.random() < 0.5 else status.title()
        if dx and rng.random() < 0.10:
            dx = dx.replace(".", "")
        doc_date = min(doc_date, config.RUN_DATE)

        trips.append([f"T{i:08d}", mid, rng.choice(providers)[0], svc.isoformat(),
                      f"{rng.randint(5, 17):02d}:{rng.choice(['00', '15', '30', '45'])}",
                      o, d, los, vehicle, miles, gps, dx, status, doc_date.isoformat(), source])

    # duplicates: same trip keyed in twice from the call center (~2%)
    completed = [t for t in trips if t[12].lower() == "completed"]
    for k, t in enumerate(rng.sample(completed, int(len(completed) * 0.02))):
        dup = list(t)
        dup[0] = f"T9{k:07d}"
        dup[14] = "call_center"
        trips.append(dup)
    rng.shuffle(trips)
    counts["trips"] = write("trips", ["trip_id", "member_id", "provider_id", "service_date",
                            "pickup_time", "origin_type", "destination_type",
                            "level_of_service", "vehicle_type", "loaded_miles", "gps_miles",
                            "diagnosis_code", "trip_status", "documentation_completed_date",
                            "source_system"], trips)
    return counts


if __name__ == "__main__":
    for k, v in main().items():
        print(f"{k:>16}: {v:,} rows")
