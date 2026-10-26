# Budapest Market Brief: 30-day validation plan (as proposed)

Source: external strategy write-up supplied 2026-10-26. Adjustments are in `04-review-and-adjustments.md`.

## Recommendation
Build a small B2B tourism-intelligence service, starting with one narrow problem and expanding into Tourism Pulse.
Validate demand with a paid report before investing in software.

Constraints assumed: recurring monthly income; B2B first; 10-20+ h/week; EUR 100-500 budget.

## Ranked opportunities
1. **Tourism Pulse: Destination Intelligence.** B2B subscription, EUR 39-99/month. First customer: small hotel group, tour operator, destination consultant.
2. **Hotel Review Intelligence.** EUR 19-79/month. Analyze permitted review exports, recurring complaints, sentiment over time.
3. **AI City Guide and Itinerary Membership.** Consumer EUR 4-9/month; business EUR 29-79/month white-label. Weak retention (trip-length use).

## MVP: "Tourism Pulse - Budapest Market Brief"
Promise: "Know what's changing in your destination, what it means for your business, and what to do next."
Initial customers: independent Budapest tour operators, boutique accommodation, tourism consultants.

First paid version:
- Monthly destination pulse report with executive summary
- Dashboard of 5-10 indicators with historical trends where reliable
- Curated events calendar
- Competitor and tourism trend watch from permitted public sources
- 3-5 actionable recommendations linked to evidence
- PDF and spreadsheet export

Excluded: live booking integrations, scraped competitor prices, agent swarm, real-time visitor tracking, unsupported AI forecasts.

Pricing hypothesis (test prices, not established willingness to pay): Free sample brief; Starter EUR 29/mo;
Pro EUR 59/mo; Business EUR 99/mo (only after validation). Sell Starter and a few paid pilots first.

## 30-day plan (~15 h/week)
- **Days 1-7 Validate:** 30 prospects, 10-15 conversations, sample report, landing page. Gate: several independent recognitions and >=2 serious paid-pilot interests.
- **Days 8-14 Pre-sell:** send sample to qualified prospects; 1-month paid pilot at EUR 19-29; target 2-3 paid pilots; collect payment.
- **Days 15-21 Build:** documented data model, automate only reliable collection, lightweight dashboard, templated report with source links and update dates.
- **Days 22-30 Launch:** deliver, interview pilots, convert to EUR 29-59 plans, publish two public insights. Target 3-5 paying.

## Lean stack
Python/pandas -> Postgres or Parquet -> SQL/Python transforms -> Streamlit or light web dashboard -> HTML-to-PDF report -> Stripe payment links -> simple landing page.
Do not deploy the whole platform for the test; do not depend on data that cannot be legally redistributed.

## Validation targets
| Test | Target |
|---|---|
| Qualified prospects contacted | 30-40 |
| Interviews | 10-15 |
| Sample reports delivered | 5-10 |
| Paid pilots | 2-3 minimum |
| First-month subscribers | 3-5 |
| Renewals | >=2 of first 3 eligible |

Interview questions: monthly decisions; current information sources; what is hard/expensive; past spend on research;
what action a meaningful change would trigger; would you pay EUR 29/month for this example and what must it include.
"That's interesting" is not validation; paying and renewing is.

## Illustrative revenue (EUR 39 average, gross, not forecasts)
| Customers | MRR | Annualized |
|---|---|---|
| 5 | 195 | 2,340 |
| 10 | 390 | 4,680 |
| 25 | 975 | 11,700 |
| 50 | 1,950 | 23,400 |
| 100 | 3,900 | 46,800 |

Real income is lower after fees, hosting, data, AI usage, refunds, marketing and tax.

Milestones: M1 3-5 paid pilots; M2 5-10 subscribers; M3 10-15; M4-6 15-30 if retention holds.
If no paying customers after 30-40 qualified conversations and several samples, revisit the offer.

## Budget (EUR 100-500)
Domain/landing 20-60; hosting 0-50; data/AI experiments 20-100; design/sales materials 0-40; validation + contingency 60-250.

## After first customers
One data foundation (sources, quality, history, indicators) serving market intelligence, review insights, and city guides.
Keep customer review data separate; respect data rights and privacy.
