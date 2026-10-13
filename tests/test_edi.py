from datetime import date

from nemt_claims.edi_835 import parse_835
from nemt_claims.edi_837 import build_837

SAMPLE_835 = """ISA*00*~GS*HP*P003*NEMTDEMO*20261015*0800*1*X*005010X221A1~ST*835*0001~
CLP*C1*1*100.00*60.00*15.00*MC*PCN1~
SVC*HC:A0130:RJ*100.00*60.00**1~CAS*CO*45*25.00~CAS*PR*2*15.00~
CLP*C2*4*50.00*0.00*0.00*MC*PCN2~CAS*CO*197*50.00~
SVC*HC:A0100:RP*50.00*0.00**1~SE*9*0001~"""


def test_835_parses_claims_lines_and_adjustments():
    claims, lines, adj = parse_835(SAMPLE_835, "sample.x12")
    assert [c["claim_id"] for c in claims] == ["C1", "C2"]
    assert claims[0]["payer_id"] == "P003"
    assert lines[0]["hcpcs_code"] == "A0130" and lines[0]["modifier"] == "RJ"
    # claim-level denial is line 0, line adjustments are line 1
    assert {(a["claim_id"], a["line_number"], a["carc_code"]) for a in adj} == {
        ("C1", 1, "45"), ("C1", 1, "2"), ("C2", 0, "197")}


def test_835_sample_balances():
    claims, _, adj = parse_835(SAMPLE_835)
    for c in claims:
        total_adj = sum(a["adjustment_amount"] for a in adj if a["claim_id"] == c["claim_id"])
        assert round(c["charge_amount"] - c["paid_amount"] - total_adj, 2) == 0


def test_837_segment_count_is_correct():
    claim = {"claim_id": "C1", "provider_id": "TP001", "billing_npi": "1234567893",
             "payer_member_id": "1999", "first_name": "Ana", "last_name": "Diaz",
             "date_of_birth": date(1970, 1, 1), "gender": "F", "service_date": date(2026, 5, 1),
             "diagnosis_code": "N18.6", "total_charge": 88.85}
    lines = {"C1": [{"line_number": 1, "hcpcs_code": "A0130", "modifier": "RJ", "units": 1,
                     "charge_amount": 52.44}]}
    segs = [s for s in build_837("P002", "Plan", [claim], lines, 1001).replace("\n", "").split("~") if s]
    st, se = segs.index(next(s for s in segs if s.startswith("ST*"))), len(segs) - 3
    assert segs[se].startswith("SE*")
    assert int(segs[se].split("*")[1]) == se - st + 1
    assert "HI*ABK:N186" in segs
