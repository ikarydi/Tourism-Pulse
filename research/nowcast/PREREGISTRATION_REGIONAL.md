# Gate 1b regional nowcast backtest: pre-registration

Written and committed **before** any model was run on regional data.
Gate 1 (countries) failed; this tests a new hypothesis and does not
change that verdict.

## Question

At sub-national level, where Wikipedia articles and GDELT locations
point at one destination rather than a whole country, do open signals
improve nowcasts of official monthly tourism nights over statistical
baselines that use official data alone?

## Target and information set

- Target: KSH STADAT 27.2.1.19 (tur0081), tourism nights at tourist
  accommodation (domestic + international, all accommodation types) for
  Hungary's 12 tourism areas: Balaton, Budapest, Greater Budapest, Bük
  and Sárvár, Debrecen, Győr and Pannonhalma, Gyula, Eger, Pécs,
  Sopron, Szeged, Tokaj and Nyíregyháza. Latest vintage.
- History starts 2021-01 (the tourism areas were defined then; older
  KSH regional tables use other definitions and are frozen archives).
- KSH publishes ~2 months after month end (at end of September 2026:
  data through July 2026). At origin `o` (last published month) we
  nowcast `o+1` and `o+2`; h = 2 is the current month.
- Alt data assumed known through `o+2` (complete months only).

## Alternative data

- `wiki`: sum of monthly user pageviews over the area's articles in
  Hungarian, English and German Wikipedia (Hungarian matters: about half
  of Hungarian tourism nights are domestic). Titles, checked to be real
  articles and not disambiguation pages:

  | area | hu | en | de |
  |---|---|---|---|
  | budapest | Budapest | Budapest | Budapest |
  | balaton | Balaton | Lake_Balaton | Balaton |
  | greater_budapest | Szentendre | Szentendre | Szentendre |
  | buk_sarvar | Bük, Sárvár | Bük, Sárvár | Bük, Sárvár |
  | debrecen | Debrecen, Hajdúszoboszló | Debrecen, Hajdúszoboszló | Debrecen, Hajdúszoboszló |
  | gyor_pannonhalma | Győr, Pannonhalma | Győr, Pannonhalma | Győr, Pannonhalma |
  | gyula | Gyula_(Magyarország) | Gyula,_Hungary | Gyula |
  | eger | Eger | Eger | Eger_(Ungarn) |
  | pecs | Pécs | Pécs | Pécs |
  | sopron | Sopron | Sopron | Sopron |
  | szeged | Szeged | Szeged | Szeged |
  | tokaj_nyiregyhaza | Tokaj, Nyíregyháza | Tokaj, Nyíregyháza | Tokaj, Nyíregyháza |

  A month is usable only if every listed article reports it.

- `gdelt`: share of GDELT daily knowledge-graph records (NUMARTS) that
  mention the area, **any theme**, 2022-01 onward.
  - Why any theme rather than tourism-tagged: in a sampled day
    (2019-06-15), Budapest appeared in 55 location entries across all
    themes and every other Hungarian town in at most 1. Tourism-tagged
    counts outside Budapest would be zero nearly every month. The
    regional GDELT signal is therefore an attention signal, like
    Wikipedia.
  - Matching (Hungarian locations only, country code HU): Budapest by
    ADM1 code `HU05`; every other area by the first comma-separated
    part of the location name, accent-folded and case-insensitive,
    equal to one of: balaton: any name starting "Balaton" or "Lake
    Balaton", Siofok, Keszthely, Heviz, Tihany, Zamardi, Fonyod;
    greater_budapest: Szentendre, Visegrad, Godollo, Vac; buk_sarvar:
    Buk, Bukfurdo, Sarvar; debrecen: Debrecen, Hajduszoboszlo;
    gyor_pannonhalma: Gyor, Pannonhalma; gyula: Gyula; eger: Eger,
    Egerszalok; pecs: Pecs; sopron: Sopron; szeged: Szeged;
    tokaj_nyiregyhaza: Tokaj, Nyiregyhaza.
  - One count per record per area. Share = (articles + 1) / corpus, the
    +1 keeping zero-mention months defined.

No GDELT tone (too sparse at this level).

## Models

Same definitions as the country study (PREREGISTRATION.md), pooled only:
per-area regressions would have too few clean training months.

| id | forecast of y(t), t = o+h |
|---|---|
| SN | y(t-12) |
| SNG | y(t-12) · exp(dbar_y(o)) |
| AIRLINE | SARIMA(0,1,1)(0,1,1)12 on log y, COVID months missing |
| POOL_GR | pooled OLS: d_y(t) = a + b·dbar_y(o) (official data only) |
| POOL_W | POOL_GR + c·Δwiki(t) |
| POOL_WG | POOL_W + g·Δgdelt(t) |

COVID exclusion unchanged (2020-03 .. 2021-12, including the months
12 earlier), so no 2021 month serves as a year-over-year base.

## Periods

- **Development** targets: 2023-10 .. 2025-07.
- **Holdout** targets: 2025-08 .. 2026-07. Run once, after the primary
  model and baseline are fixed and committed.
- MASE scale per area: mean |y(t) - y(t-12)| over 2023-01 .. 2024-12
  (the earliest two clean years; a normaliser only, identical for every
  model).

## Selection (on development only)

- Primary: POOL_W or POOL_WG, whichever has the lower median relative
  MASE vs SN across areas.
- Baseline: SNG, AIRLINE or POOL_GR, same rule.

## Gate

**Pass** if the primary model's relative MASE vs SN is ≤ 0.90 in a
majority of areas (≥ 7 of 12) on the holdout. An area without holdout
forecasts counts as not passing.

## Stricter check (reported, not gating)

Does the primary beat the baseline in ≥ 7 of 12 areas? Reported with
Diebold-Mariano tests per area. Budapest is reported on its own as the
product's anchor destination (descriptive only).

## Known limitations, stated in advance

- Short history: about 3.5 clean years per area, 12 areas, a 12-month
  holdout. Power is lower than the country study; a small real effect
  may not show.
- Signals for small areas (Gyula, Sopron) will be thin in both
  Wikipedia and GDELT.
- Greater Budapest's tourism area is approximated by Szentendre and three
  other towns; the fit is imperfect by construction.
