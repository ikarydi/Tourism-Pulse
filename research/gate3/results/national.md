# Gate 3 Part 2 (descriptive): national visitor series

One regression per horizon on the country's own rows: OWN uses WG's regressors (recent nights growth, Wikipedia, GDELT share and tone); OWN_NAT adds the national series' year-on-year log growth at its information date (Spain's FRONTUR at o + 1). Ratio = OWN_NAT MASE / OWN MASE on the cells both forecast (below 1 = the national series helps). Greece and Italy could not be retrieved; see data/NATIONAL.md.

| geo | period | horizons | MASE ratio | OWN MAPE | OWN_NAT MAPE | cells |
|---|---|---|---|---|---|---|
| ES | dev | h ≤ 3 | 0.968 | 5.31% | 4.95% | 72 |
| ES | dev | h = 4-12 | 1.138 | 6.49% | 7.37% | 180 |
| ES | holdout | h ≤ 3 | 1.280 | 1.60% | 2.07% | 36 |
| ES | holdout | h = 4-12 | 1.047 | 1.97% | 2.14% | 108 |

By horizon:

| geo | period | h | MASE ratio | OWN MAPE | OWN_NAT MAPE |
|---|---|---|---|---|---|
| ES | dev | 1 | 1.031 | 4.41% | 4.03% |
| ES | dev | 2 | 1.083 | 4.92% | 5.41% |
| ES | dev | 3 | 0.857 | 6.62% | 5.40% |
| ES | holdout | 1 | 1.276 | 1.58% | 2.22% |
| ES | holdout | 2 | 1.006 | 1.89% | 1.91% |
| ES | holdout | 3 | 1.676 | 1.32% | 2.09% |
