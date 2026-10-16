# Return Detective — Response Playbook and Authority Matrix

*Operating policy written by Team Return Detective for the prototype. In production it would be owned by ALDO's Quality, Merchandising, E-commerce Ops and Customer Care teams.*

## 1. Principles
- Statistics raise a flag; the agents decide what it means, and humans approve high-stakes actions.
- Never deny, delay or restrict a legitimate customer return because of a case.
- Never use customer identity, demographics or customer value to decide an action. Actions depend only on the product, the evidence and the policy.
- Every conclusion must cite evidence: return IDs, counts, shares, dates, locations.
- When evidence is weak, prefer watching over acting.

## 2. Confidence levels
- **Low**: a signal exists but competing explanations have not been ruled out.
- **Medium**: one explanation is clearly best supported; at least two alternatives were tested and ruled out.
- **High**: medium, plus the pattern is widespread (many locations or channels) and persisted at least 3 weeks, or is confirmed by a human inspection.

## 3. Root-cause classes and owners
| Class | Typical evidence | Owner team |
|---|---|---|
| Product quality defect | "Defective / Poor quality / Manufacturer defect" share far above baseline, spread across many stores and channels | Quality & Sourcing |
| Fit / sizing issue | "Too small" or "Too big" dominates, one direction, persistent | Merchandising (product content) |
| Expectation gap (photo / description) | "Not what I expected / Not as advertised / colour" above baseline, mostly online channels | E-commerce content |
| Fulfilment error | "Wrong item / Wrong size delivered / Missing item", concentrated in online channels | E-commerce Operations (DC) |
| Transit damage | "Arrived in poor condition", concentrated in mail channels | Logistics |
| Local handling issue | Pattern concentrated in one store | Store Operations |

## 4. Action tiers and authority
| Tier | Action | Who decides | Conditions |
|---|---|---|---|
| 0 | Keep watching | Agent | Any signal |
| 1 | Open / update a case, notify the owner team | Agent | Signal present |
| 2 | Waive restocking fees on returns linked to the case; mark future returns of this style/category as fee-free | Agent, **up to CA$500 per case**; above that, Customer Care lead approves | Root cause is ALDO's responsibility (quality, fulfilment, transit damage) and confidence ≥ Medium |
| 3 | Update product-page fit or content guidance | **Merchandising approval required** | Fit or expectation class, confidence ≥ Medium |
| 4 | Hold remaining stock of the style (DC and stores) pending inspection | **Quality and Merchandising approval required** | Quality class, confidence = High |
| 5 | Proactive outreach to customers who bought the style recently (replacement or free return offer) | **Customer Care and Privacy approval required** | Quality class, confidence = High; opted-in channels only |
| 5 | Send supplier quality claim | **Quality & Sourcing approval required**; the agent may draft it | Quality class, confidence = High |

## 5. Verification
Every case with an action must schedule a verification check (default 21 days). If the signal has not fallen back below the WATCH level, reopen the case and revise the hypothesis.

The prototype persists a due date and runs checks from the UI/CLI. Resolve pending
approvals first. Require snapshot coverage through the check date and at least
five recent style returns; missing/sparse observations are inconclusive. A NORMAL
signal can close an actioned case, without claiming a causal reduction in returns.
WATCH/SIGNAL reopens the same case; pass prior hypotheses and human decisions to
the Investigator, seek disconfirming evidence and schedule the next review.
Identical rejected proposals remain rejected; revised proposals need new evidence.
