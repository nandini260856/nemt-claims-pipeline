"""Write a plain Markdown report and two charts from the reports.* views."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402

INK, MUTED, GRID = "#1f2328", "#59636e", "#d8dee4"
ACCENT, NEUTRAL = "#2f6fbd", "#b5bcc4"


def _style(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _charts(impact, holds):
    out = config.REPORT_DIR
    # 1) denial rate with vs without validation
    fig, ax = plt.subplots(figsize=(7, 2.4), dpi=150)
    labels = ["Send every claim", "Validate first (this pipeline)"]
    rates = [impact["no_validation"]["denial_rate"] * 100, impact["with_validation"]["denial_rate"] * 100]
    bars = ax.barh(labels[::-1], rates[::-1], color=[ACCENT, NEUTRAL], height=0.5)
    for b, v in zip(bars, rates[::-1]):
        ax.text(b.get_width() + 0.3, b.get_y() + b.get_height() / 2, f"{v:.1f}%",
                va="center", color=INK, fontsize=10, fontweight="bold")
    _style(ax)
    ax.set_xlabel("Payer denial rate (%)", color=MUTED)
    ax.set_title("Simulated payer denial rate", loc="left", color=INK, fontsize=12)
    ax.tick_params(axis="y", labelsize=10, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out / "denial_rate.png")
    plt.close(fig)

    # 2) why claims were held
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=150)
    rows = list(reversed(holds))
    bars = ax.barh([r[0] for r in rows], [r[3] for r in rows], color=ACCENT, height=0.6)
    for b, r in zip(bars, rows):
        ax.text(b.get_width() + 8, b.get_y() + b.get_height() / 2, f"{r[3]:,}",
                va="center", color=INK, fontsize=9)
    _style(ax)
    ax.set_xlabel("Claims held", color=MUTED)
    ax.set_title("Claims caught before submission, by rule", loc="left", color=INK, fontsize=12)
    ax.tick_params(axis="y", labelsize=9, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out / "hold_reasons.png")
    plt.close(fig)


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build(con):
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    k = dict(zip([d[0] for d in con.execute("SELECT * FROM reports.kpi_summary").description],
                 con.execute("SELECT * FROM reports.kpi_summary").fetchone()))
    impact = {r[0]: {"claims": r[1], "denied": r[2], "denial_rate": r[3], "charges_denied": r[4],
                     "paid": r[5]}
              for r in con.execute("SELECT * FROM reports.validation_impact").fetchall()}
    holds = con.execute("SELECT * FROM reports.hold_reasons").fetchall()
    denials = con.execute("SELECT * FROM reports.denials_by_reason").fetchall()
    payers = con.execute("SELECT * FROM reports.payer_scorecard").fetchall()
    _charts(impact, holds)

    nv, wv = impact["no_validation"], impact["with_validation"]
    md = f"""# Claims run report ({config.RUN_DATE})

_All data is synthetic. Payer results come from a simulator, not a real health plan._

## Headline

| Measure | Value |
|---|---|
| Trips received | {k['total_trips']:,} |
| Claims built (completed trips) | {k['claims_built']:,} |
| Clean claim rate (passed every check) | {k['clean_claim_rate']:.1%} |
| Claims held for fixing | {k['claims_held']:,} |
| Claims paid / denied | {k['claims_paid']:,} / {k['claims_denied']:,} |
| Denial rate on submitted claims | {k['denial_rate']:.1%} |
| Total paid | ${k['total_paid']:,.2f} |
| Net collection rate (paid + patient share vs expected) | {k['net_collection_rate']:.1%} |

## Validation impact

| Scenario | Claims sent | Denied | Denial rate | Charges denied |
|---|---|---|---|---|
| Send every claim | {nv['claims']:,} | {nv['denied']:,} | {nv['denial_rate']:.1%} | ${nv['charges_denied']:,.2f} |
| Validate first | {wv['claims']:,} | {wv['denied']:,} | {wv['denial_rate']:.1%} | ${wv['charges_denied']:,.2f} |

![Denial rate](denial_rate.png)

## Why claims were held

{_table(["Rule", "What it means", "Risk", "Claims", "Charges at risk ($)"],
        [(r[0], r[1], r[2], f"{r[3]:,}", f"{r[4]:,.2f}") for r in holds])}

![Hold reasons](hold_reasons.png)

## Denials that still happened

{_table(["CARC", "Reason", "Claims", "Denied ($)"], [(r[0], r[1], r[2], f"{r[3]:,.2f}") for r in denials])}

## Payer scorecard

{_table(["Payer", "Claims", "Clean claim rate", "Denial rate", "Paid ($)"],
        [(r[0], f"{r[1]:,}", f"{r[2]:.1%}", f"{r[3]:.1%}", f"{r[4]:,.2f}") for r in payers])}
"""
    path = config.REPORT_DIR / "claims_report.md"
    path.write_text(md)
    return path
