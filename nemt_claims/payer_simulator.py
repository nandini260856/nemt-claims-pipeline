"""
Pretend to be the health plans (payers) on the other side.

A real payer checks claims against its own records and sends back an 835
remittance file saying what it paid or denied and why (CARC reason codes).
This simulator does the same, using its own copy of enrollment and authorization
data, so it is independent from our validation step.

It runs two scenarios so we can measure the value of validating first:
  * "no_validation"  - every claim is sent, nothing is held back
  * "with_validation" - only READY claims are sent (the real pipeline)
Only the second scenario writes 835 files.
"""
import csv
import zlib
from collections import defaultdict
from datetime import date

from . import config
from .validators import is_valid_npi

COINSURANCE = {"P003": 0.20}  # Medicare Advantage member pays 20% (PR-2)


def _load_payer_records():
    def read(name):
        with open(config.RAW_DIR / f"{name}.csv") as f:
            return list(csv.DictReader(f))

    elig = defaultdict(list)
    for r in read("eligibility"):
        elig[(r["member_id"], r["payer_id"])].append(
            (date.fromisoformat(r["coverage_start"]), date.fromisoformat(r["coverage_end"])))
    auth = defaultdict(list)
    for r in read("authorizations"):
        auth[(r["member_id"], r["payer_id"], r["level_of_service"])].append(
            (date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"])))
    payers = {r["payer_id"]: r for r in read("payers")}
    return elig, auth, payers


def _decide(c, elig, auth, payers, seen):
    """Return the CARC denial code, or None if the claim is payable."""
    p = payers[c["payer_id"]]
    svc = c["service_date"]
    if not any(s <= svc <= e for s, e in elig[(c["member_id"], c["payer_id"])]):
        return "27"   # coverage terminated / not eligible
    if not is_valid_npi(c["billing_npi"]):
        return "16"   # claim lacks valid information (provider identifier)
    if (c["claim_created_date"] - svc).days > int(p["filing_limit_days"]):
        return "29"   # time limit for filing has expired
    needs_auth = p["auth_rule"] == "all" or (
        p["auth_rule"] == "stretcher_ambulance" and c["level_of_service"] in ("stretcher_van", "ambulance"))
    if needs_auth and not any(s <= svc <= e for s, e in
                              auth[(c["member_id"], c["payer_id"], c["level_of_service"])]):
        return "197"  # precertification/authorization absent
    key = (c["member_id"], svc, c["pickup_time"], c["origin_type"], c["destination_type"])
    if key in seen:
        return "18"   # exact duplicate claim
    if not c["diagnosis_code"]:
        return "16"   # claim lacks information (diagnosis)
    if zlib.crc32(c["claim_id"].encode()) % 1000 < 15:
        return "96"   # non-covered charge: denials validation can't predict (~1.5%)
    seen.add(key)
    return None


def _claims(con, only_ready):
    where = "WHERE s.submission_status = 'READY'" if only_ready else ""
    cols = ["claim_id", "payer_id", "member_id", "billing_npi", "service_date", "claim_created_date",
            "level_of_service", "pickup_time", "origin_type", "destination_type", "diagnosis_code",
            "total_charge"]
    rows = con.execute(f"""
        SELECT c.claim_id, c.payer_id, c.member_id, c.billing_npi, c.service_date, c.claim_created_date,
               c.level_of_service, c.pickup_time, c.origin_type, c.destination_type, c.diagnosis_code,
               c.total_charge
        FROM claims.claims c JOIN validation.claim_status s USING (claim_id)
        {where}
        ORDER BY c.claim_created_date, c.claim_id
    """).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def _lines(con):
    out = defaultdict(list)
    for r in con.execute("""
        SELECT claim_id, line_number, hcpcs_code, modifier, units, charge_amount, expected_allowed_amount
        FROM claims.claim_lines ORDER BY claim_id, line_number
    """).fetchall():
        out[r[0]].append(r[1:])
    return out


def _seg(*e):
    return "*".join(str(x) for x in e) + "~"


def _write_835(payer_id, payer_name, results, lines, n):
    total_paid = sum(r["paid"] for r in results)
    segs = [
        _seg("ISA", "00", " " * 10, "00", " " * 10, "ZZ", payer_id.ljust(15), "ZZ", "NEMTDEMO".ljust(15),
             "261015", "0800", "^", "00501", f"{2000 + n:09d}", "0", "T", ":"),
        _seg("GS", "HP", payer_id, "NEMTDEMO", "20261015", "0800", 2000 + n, "X", "005010X221A1"),
        _seg("ST", "835", "0001"),
        _seg("BPR", "I", f"{total_paid:.2f}", "C", "ACH", "CCP", "", "", "", "", "", "", "", "", "", "20261015"),
        _seg("TRN", "1", f"EFT{payer_id}{n:04d}", "1999999999"),
        _seg("N1", "PR", payer_name.upper()),
        _seg("N1", "PE", "NEMT CLAIMS DEMO", "XX", "1999999999"),
    ]
    for r in results:
        c = r["claim"]
        status = "4" if r["carc"] else "1"
        segs.append(_seg("CLP", c["claim_id"], status, f"{c['total_charge']:.2f}", f"{r['paid']:.2f}",
                         f"{r['patient_resp']:.2f}", "MC", f"PCN{c['claim_id'][1:]}"))
        if r["carc"]:
            segs.append(_seg("CAS", "CO", r["carc"], f"{c['total_charge']:.2f}"))
        for ln, code, mod, units, charge, allowed in lines[c["claim_id"]]:
            if r["carc"]:
                segs.append(_seg("SVC", f"HC:{code}:{mod}", f"{charge:.2f}", "0.00", "", units))
                segs.append(_seg("DTM", "472", c["service_date"].strftime("%Y%m%d")))
                continue
            pr = round(float(allowed) * COINSURANCE.get(payer_id, 0), 2)
            paid = round(float(allowed) - pr, 2)
            segs.append(_seg("SVC", f"HC:{code}:{mod}", f"{charge:.2f}", f"{paid:.2f}", "", units))
            segs.append(_seg("DTM", "472", c["service_date"].strftime("%Y%m%d")))
            contractual = round(float(charge) - float(allowed), 2)
            if contractual:
                segs.append(_seg("CAS", "CO", "45", f"{contractual:.2f}"))
            if pr:
                segs.append(_seg("CAS", "PR", "2", f"{pr:.2f}"))
    segs.append(_seg("SE", len(segs) - 1, "0001"))
    segs += [_seg("GE", "1", 2000 + n), _seg("IEA", "1", f"{2000 + n:09d}")]
    path = config.INBOUND_DIR / f"835_{payer_id}_20261015.x12"
    path.write_text("\n".join(segs) + "\n")
    return path


def _adjudicate(claims, lines, elig, auth, payers):
    seen, results = set(), []
    for c in claims:
        carc = _decide(c, elig, auth, payers, seen)
        paid = pr = 0.0
        if not carc:
            for _, _, _, _, _, allowed in lines[c["claim_id"]]:
                line_pr = round(float(allowed) * COINSURANCE.get(c["payer_id"], 0), 2)
                pr += line_pr
                paid += round(float(allowed) - line_pr, 2)
        results.append({"claim": c, "carc": carc, "paid": round(paid, 2), "patient_resp": round(pr, 2)})
    return results


def run(con):
    elig, auth, payers = _load_payer_records()
    lines = _lines(con)

    summary = []
    for scenario, only_ready in (("no_validation", False), ("with_validation", True)):
        results = _adjudicate(_claims(con, only_ready), lines, elig, auth, payers)
        denied = [r for r in results if r["carc"]]
        summary.append({
            "scenario": scenario,
            "claims_submitted": len(results),
            "claims_denied": len(denied),
            "denial_rate": round(len(denied) / len(results), 4),
            "charges_denied": round(sum(float(r["claim"]["total_charge"]) for r in denied), 2),
            "amount_paid": round(sum(r["paid"] for r in results), 2),
        })
        if scenario == "with_validation":
            config.INBOUND_DIR.mkdir(parents=True, exist_ok=True)
            for f in config.INBOUND_DIR.glob("*.x12"):
                f.unlink()
            by_payer = defaultdict(list)
            for r in results:
                by_payer[r["claim"]["payer_id"]].append(r)
            for n, (pid, res) in enumerate(sorted(by_payer.items()), start=1):
                _write_835(pid, payers[pid]["payer_name"], res, lines, n)

    import pandas as pd
    impact = pd.DataFrame(summary)
    con.execute("CREATE OR REPLACE TABLE reports.validation_impact AS SELECT * FROM impact")
    return summary
