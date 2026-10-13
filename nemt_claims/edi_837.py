"""
Write READY claims as X12 837P files (the electronic claim format), one file per payer.

This is a simplified 837P (005010X222A1) for demonstration: it has the main loops a
payer needs (submitter, receiver, billing provider, subscriber, payer, claim, service
lines) but it is not certified against any payer's companion guide.
"""
from datetime import datetime

from . import config


def _seg(*elements):
    return "*".join(str(e) for e in elements) + "~"


def build_837(payer_id, payer_name, claims, lines_by_claim, control_number):
    now = datetime(2026, 10, 1, 6, 0)
    d8, t4 = now.strftime("%Y%m%d"), now.strftime("%H%M")
    segs = [
        _seg("ISA", "00", " " * 10, "00", " " * 10, "ZZ", "NEMTDEMO".ljust(15), "ZZ",
             payer_id.ljust(15), now.strftime("%y%m%d"), t4, "^", "00501",
             f"{control_number:09d}", "0", "T", ":"),
        _seg("GS", "HC", "NEMTDEMO", payer_id, d8, t4, control_number, "X", "005010X222A1"),
        _seg("ST", "837", "0001", "005010X222A1"),
        _seg("BHT", "0019", "00", f"B{control_number}", d8, t4, "CH"),
        _seg("NM1", "41", "2", "NEMT CLAIMS DEMO", "", "", "", "", "46", "NEMTDEMO"),
        _seg("NM1", "40", "2", payer_name.upper(), "", "", "", "", "46", payer_id),
    ]
    hl = 0
    for c in claims:
        hl += 1
        parent = hl
        segs += [
            _seg("HL", hl, "", "20", "1"),
            _seg("NM1", "85", "2", c["provider_id"], "", "", "", "", "XX", c["billing_npi"]),
        ]
        hl += 1
        segs += [
            _seg("HL", hl, parent, "22", "0"),
            _seg("SBR", "P", "18", "", "", "", "", "", "", "MC"),
            _seg("NM1", "IL", "1", c["last_name"].upper(), c["first_name"].upper(), "", "", "",
                 "MI", c["payer_member_id"]),
            _seg("DMG", "D8", c["date_of_birth"].strftime("%Y%m%d"), c["gender"]),
            _seg("NM1", "PR", "2", payer_name.upper(), "", "", "", "", "PI", payer_id),
            _seg("CLM", c["claim_id"], f"{c['total_charge']:.2f}", "", "", "41:B:1", "Y", "A", "Y", "Y"),
            _seg("HI", "ABK:" + c["diagnosis_code"].replace(".", "")),
        ]
        for ln in lines_by_claim[c["claim_id"]]:
            segs += [
                _seg("LX", ln["line_number"]),
                _seg("SV1", f"HC:{ln['hcpcs_code']}:{ln['modifier']}", f"{ln['charge_amount']:.2f}",
                     "UN", ln["units"], "", "", "1"),
                _seg("DTP", "472", "D8", c["service_date"].strftime("%Y%m%d")),
            ]
    st_count = len(segs) - 2 + 1  # segments from ST to SE inclusive
    segs += [
        _seg("SE", st_count, "0001"),
        _seg("GE", "1", control_number),
        _seg("IEA", "1", f"{control_number:09d}"),
    ]
    return "\n".join(segs) + "\n"


def export(con):
    """Write one 837P file per payer for every READY claim. Returns claims written per payer."""
    config.OUTBOUND_DIR.mkdir(parents=True, exist_ok=True)
    for f in config.OUTBOUND_DIR.glob("*.x12"):
        f.unlink()

    cols = ["claim_id", "payer_id", "payer_name", "provider_id", "billing_npi", "payer_member_id",
            "first_name", "last_name", "date_of_birth", "gender", "service_date",
            "diagnosis_code", "total_charge"]
    rows = con.execute(f"""
        SELECT c.claim_id, c.payer_id, p.payer_name, c.provider_id, c.billing_npi, c.payer_member_id,
               m.first_name, m.last_name, m.date_of_birth, m.gender, c.service_date,
               c.diagnosis_code, c.total_charge
        FROM claims.claims c
        JOIN validation.claim_status s USING (claim_id)
        JOIN staging.members m USING (member_id)
        JOIN staging.payers p ON p.payer_id = c.payer_id
        WHERE s.submission_status = 'READY'
        ORDER BY c.payer_id, c.claim_id
    """).fetchall()
    claims = [dict(zip(cols, r)) for r in rows]

    lines_by_claim = {}
    for claim_id, line_number, code, mod, units, charge in con.execute("""
        SELECT l.claim_id, l.line_number, l.hcpcs_code, l.modifier, l.units, l.charge_amount
        FROM claims.claim_lines l
        JOIN validation.claim_status s USING (claim_id)
        WHERE s.submission_status = 'READY'
        ORDER BY l.claim_id, l.line_number
    """).fetchall():
        lines_by_claim.setdefault(claim_id, []).append(
            {"line_number": line_number, "hcpcs_code": code, "modifier": mod,
             "units": units, "charge_amount": charge})

    written = {}
    for n, payer_id in enumerate(sorted({c["payer_id"] for c in claims}), start=1):
        batch = [c for c in claims if c["payer_id"] == payer_id]
        text = build_837(payer_id, batch[0]["payer_name"], batch, lines_by_claim, 1000 + n)
        (config.OUTBOUND_DIR / f"837P_{payer_id}_{config.RUN_DATE:%Y%m%d}.x12").write_text(text)
        written[payer_id] = len(batch)
    return written
