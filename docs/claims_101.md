# Healthcare Claims 101 (plain English)

## What is a claim?

A claim is a bill sent to a health plan. For NEMT, the "service" is a ride: a member is picked up at home, taken to dialysis, and later driven back. Each leg of the ride becomes a claim.

## The life of a claim

1. **Ride happens.** The driver app records pickup, drop-off, miles and vehicle type.
2. **Claim is built.** Ride details become billing codes and dollar amounts.
3. **Claim is checked.** Is the member covered? Is an authorization needed? Is anything missing?
4. **Claim is sent.** It goes out as an **837P** file, usually through a clearinghouse.
5. **Plan decides.** It pays, partly pays, or denies the claim.
6. **Payment comes back.** It arrives as an **835** file that says what was paid and why.
7. **Reconcile.** Match every dollar billed to a dollar paid or adjusted. Fix and resend denials.

## The codes you need to know

| Code type | What it describes | Example in this project |
|---|---|---|
| **HCPCS** | What service was given | `A0130` wheelchair van trip, `S0209` wheelchair van mileage per mile |
| **Modifier** | Extra detail on a code. For NEMT, where the ride started and ended | `RJ` = Residence to dialysis facility |
| **ICD-10** | Why the member needed care (diagnosis) | `N18.6` end-stage kidney disease |
| **NPI** | The provider's 10-digit national ID, with a check digit | `1234567893` |
| **CARC** | Why a payer adjusted or denied money | `27` not covered, `197` no authorization, `18` duplicate, `29` filed too late, `45` contractual write-down |
| **Group code** | Who is responsible for an adjustment | `CO` = provider writes it off, `PR` = patient pays |

## The EDI files

| File | Direction | Says |
|---|---|---|
| **837P** | We → payer | "Here are our claims" |
| **835** | Payer → us | "Here's what we paid, denied, and why" |
| 270 / 271 | Both ways | "Is this member eligible?" / "Yes, until…" |
| 276 / 277 | Both ways | "What's the status of this claim?" |
| 999 / 277CA | Payer → us | "We received the file" / "These claims were rejected at the front door" |

An X12 file is text. Each **segment** ends in `~` and its **elements** are split by `*`. For example, `CLP*C123*1*88.85*61.52` means claim `C123` was processed (`1`), billed $88.85, and paid $61.52.

## The money

| Term | Meaning |
|---|---|
| **Billed charge** | What the provider asked for |
| **Allowed amount** | What the plan's fee schedule says the service is worth |
| **Contractual adjustment (CO-45)** | Billed minus allowed. The provider writes it off |
| **Patient responsibility (PR)** | Coinsurance or copay the member owes |
| **Paid amount** | What the plan actually paid |

**The balancing rule:** billed charge = paid + all adjustments. If a claim doesn't balance, something is wrong in the data.

## Key metrics

- **Clean claim rate:** share of claims that pass every check the first time
- **Denial rate:** share of submitted claims the payer denies
- **Net collection rate:** what was collected compared with what was expected under the contract
- **Days to bill:** time from the ride to sending the claim. It matters because of **timely filing** limits
