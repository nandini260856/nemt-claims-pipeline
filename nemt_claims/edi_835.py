"""
Read 835 remittance files (what the payer paid and why) into flat tables.

An X12 file is a list of segments ending in "~", with elements split by "*".
We only need three segments:
  CLP = one claim's result, SVC = one service line's result, CAS = an adjustment
A CAS right after CLP belongs to the whole claim; a CAS after SVC belongs to that line.
"""
from pathlib import Path


def parse_835(text: str, file_name: str = ""):
    claims, lines, adjustments = [], [], []
    payer_id = None
    claim = None
    line_no = 0

    for raw in text.replace("\n", "").split("~"):
        if not raw:
            continue
        e = raw.split("*")
        tag = e[0]
        if tag == "GS":
            payer_id = e[2]
        elif tag == "CLP":
            line_no = 0
            claim = {
                "claim_id": e[1],
                "payer_id": payer_id,
                "claim_status_code": e[2],
                "charge_amount": float(e[3]),
                "paid_amount": float(e[4]),
                "patient_responsibility": float(e[5] or 0),
                "payer_claim_control_number": e[7],
                "source_file": file_name,
            }
            claims.append(claim)
        elif tag == "SVC" and claim:
            line_no += 1
            _, code, modifier = e[1].split(":")
            lines.append({
                "claim_id": claim["claim_id"],
                "line_number": line_no,
                "hcpcs_code": code,
                "modifier": modifier,
                "charge_amount": float(e[2]),
                "paid_amount": float(e[3]),
                "units": int(e[5]),
            })
        elif tag == "CAS" and claim:
            # CAS can repeat reason/amount pairs: CAS*CO*45*10.00*1*45*2.00...
            group = e[1]
            for i in range(2, len(e) - 1, 3):
                if e[i]:
                    adjustments.append({
                        "claim_id": claim["claim_id"],
                        "line_number": line_no,  # 0 = claim level
                        "group_code": group,
                        "carc_code": e[i],
                        "adjustment_amount": float(e[i + 1]),
                    })
    return claims, lines, adjustments


def load(con, inbound_dir: Path):
    """Parse every 835 file and load raw.remit_* tables."""
    import pandas as pd

    all_c, all_l, all_a = [], [], []
    files = sorted(inbound_dir.glob("835_*.x12"))
    for f in files:
        c, l, a = parse_835(f.read_text(), f.name)
        all_c += c
        all_l += l
        all_a += a
    remit_claims = pd.DataFrame(all_c)
    remit_lines = pd.DataFrame(all_l)
    remit_adjustments = pd.DataFrame(all_a)
    con.execute("CREATE OR REPLACE TABLE raw.remit_claims AS SELECT * FROM remit_claims")
    con.execute("CREATE OR REPLACE TABLE raw.remit_lines AS SELECT * FROM remit_lines")
    con.execute("CREATE OR REPLACE TABLE raw.remit_adjustments AS SELECT * FROM remit_adjustments")
    return {"files": len(files), "claims": len(all_c), "lines": len(all_l), "adjustments": len(all_a)}
