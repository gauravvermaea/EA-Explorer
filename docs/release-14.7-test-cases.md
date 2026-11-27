# Release 14.7: Monte Carlo simulation, the test cases

The owner, 27 Nov 2026, 15:34: "write test cases for monte carlo". Written before anything is built, from the
decisions of the same afternoon (D957, [release-14.7-monte-carlo.md](release-14.7-monte-carlo.md)): all four uses,
ranges drafted by the AI or typed on a screen, kept in a project study, PERT, triangular and an event, "move together"
groups, a currency per study and the risk scales set once.

Two kinds of case:

* **The engine (MC-E01 to MC-E40)** is pure arithmetic, so every case has a known answer: a formula, a limit, or a case
  with only one possible result. They are already code, in
  `services/api/tests/test_r14_7_monte_carlo_engine.py`, skipped until `eax/monte_carlo.py` exists and then run by the
  dev check. They were checked against a throwaway engine on 27 Nov 2026: all 48 (with the parameterised ones) passed in
  5 seconds, so the expected answers and tolerances hold. The tolerances are four standard errors on 20,000 runs: a
  correct engine fails about once in 15,000.
* **The rest (MC-S, MC-A, MC-U, MC-R, MC-X)** need the running installation: the API checks and journeys of the
  self-test, written as the stories are built (R14.7.2 to R14.7.6).

## The engine (R14.7.1): `test_r14_7_monte_carlo_engine.py`

| Id | What it checks | Known answer |
| --- | --- | --- |
| MC-E01 | PERT's mean and spread | mean (a + 4m + b) / 6; variance (mean − a)(b − mean) / 7; (2, 5, 14) gives 6.0 and 2.14 |
| MC-E02 | Triangular's mean and spread | mean (a + m + b) / 3; variance (a² + m² + b² − am − ab − mb) / 18 |
| MC-E03 | PERT is the default and narrower than triangular | the same three numbers: PERT's spread is smaller |
| MC-E04 | Every draw lies within low and high | both shapes |
| MC-E05 | A range of one number | always that number |
| MC-E06 | A skewed range | median toward the likely end, mean beyond it (long tail) |
| MC-E07 | An event happens in its share of runs | 30% chance: 30% of runs, within four standard errors |
| MC-E08 | An event of chance 0 or 1 | never, always |
| MC-E09 | An event's mean | chance × the impact's mean |
| MC-E10 | A range out of order (low > likely, likely > high) | refused |
| MC-E11 | A chance below 0 or above 1 | refused |
| MC-E12 | An unknown shape (log-normal waits, D957), strength or a run count of 0 | refused |
| MC-E13 | A dependency loop, or a work package that is not there | refused, naming it |
| MC-E14 | A group naming an input that is not there | refused, naming it |
| MC-E15 | The same inputs and seed | the same answer and digest, every time |
| MC-E16 | Another seed | other draws, the same picture (means within the error) |
| MC-E17 | The order inputs are given in | no difference |
| MC-E18 | Percentiles | P10 ≤ P50 ≤ P80 ≤ P90, within the runs |
| MC-E19 | A certain total | every percentile equal |
| MC-E20 | The chance of meeting a figure | certain total of 10: 100% by 10, 0% by 9.99; symmetrical range: 50% by its middle |
| MC-E21 | A sum of independent ranges | means add, variances add |
| MC-E22 | **Why the release exists**: three right-skewed estimates | the sum of their most likely values is met less than half the time |
| MC-E23 | What drives the result (the tornado) | the widest range first, a fixed number last at 0 |
| MC-E24 | Inputs in no group | independent (correlation near 0) |
| MC-E25 | A group's members move together | weak > 0.15, medium > 0.4, strong > 0.7 correlation |
| MC-E26 | Moving together widens the total | same mean, P10 to P90 at least 1.3 times wider |
| MC-E27 | A group keeps each member's own range | a member's mean and a fixed member unchanged |
| MC-E28 | A chain of certain work packages | ends at their sum; all on the critical path |
| MC-E29 | Two parallel paths into one package | ends at the longer path; only it critical |
| MC-E30 | Two uncertain equal paths (the merge bias) | ends later than either path alone; each critical about half the time |
| MC-E31 | A package with nothing before it | starts at once |
| MC-E32 | The chance of a plateau by a date | 0 before the earliest end, 1 after the latest; P80 met 80% of the time |
| MC-E33 | Speed | 10,000 runs of 200 work packages in under 10 seconds |
| MC-E34 | An option's net value | benefits less costs |
| MC-E35 | The chance an option pays for itself | a symmetrical benefit around the cost: 50% |
| MC-E36 | A cost and a benefit that move together | the net narrows |
| MC-E37 | A year's losses from risks | mean Σ chance × impact; no loss (1 − p₁)(1 − p₂); over 5,500 only when both happen |
| MC-E38 | Controls that lower a risk's chance | every percentile and the mean fall |
| MC-E39 | Scenario planning: an option better in every run | best 100% of the time |
| MC-E40 | Two options that each win one future | the futures' weights decide: 70/30 gives 70% and 30% |

The engine's interface these cases assume is in the test file's docstring (Range, Event, Group, draw, total, net,
schedule, best, Result). It may change while R14.7.1 is built; the known answers do not.

## The study: kept in the project (R14.7.2 to R14.7.5, D957 (2), (3), (6))

| Id | Case | Expected |
| --- | --- | --- |
| MC-S01 | A study's inputs drafted from the project's work packages | the AI reads the work packages and their dates through MCP and drafts each range with its source; the model is not changed (built 27 Nov 2026: the study does not read the model by itself) |
| MC-S02 | Two studies of the same project with different ranges | both kept; each run shows which study and which inputs |
| MC-S03 | A study's currency | the installation's currency unless chosen; every amount and result in it; another study can differ |
| MC-S04 | The risk scales set once by the organisation | Likelihood 1 to 5 as a chance, Impact 1 to 5 as a range of loss; defaults given; a study's risks take them |
| MC-S05 | One risk overridden in a study | that risk uses its own chance and amount; the others the scale |
| MC-S06 | A run is kept with its inputs and seed | opened later, it shows the same numbers; run again, the same answer |
| MC-S07 | The model changes after a run (a work package added or its dates moved) | the study says so; the old run stays as it was; a new run uses the new model |
| MC-S08 | A study's project is closed, archived or deleted | the study goes with it, as scenario planning's do |
| MC-S09 | A move-together group | named, with members and a strength; a member in two groups refused |

## The API and the AI through MCP (R14.7.6, D957 (2))

| Id | Case | Expected |
| --- | --- | --- |
| MC-A01 | The AI drafts ranges for a study | a preview: each range with where it came from (a document, the model, a person); nothing saved until yes |
| MC-A02 | The AI's draft refused | nothing saved; the study as it was |
| MC-A03 | The AI asks for a run | EA Explorer's engine runs it (D857 (4)); the AI reads the result; it never sends numbers as the result |
| MC-A04 | A range out of order or a chance over 1 through the API or MCP | refused with an error code (Release 7.9) naming the input |
| MC-A05 | More than 100,000 runs, or fewer than 100, asked for | refused, saying the limit |
| MC-A06 | A person without rights to the project | 403 on the study and its runs; the MCP tools list no study of it |
| MC-A07 | A reader (Report Viewer, Auditor) | sees studies and runs; cannot change or run |
| MC-A08 | The same study run twice at the same moment | one is kept; the other is refused with 409, saying to repeat |
| MC-A09 | Every new MCP tool | in the full test's MCP check (Release 10) |

## The screens (R14.7.6, D957 (2))

| Id | Case | Expected |
| --- | --- | --- |
| MC-U01 | The ranges table | Low, Likely and High per work package, cost line or risk; typed and saved; out of order marked and not saved |
| MC-U02 | A range the AI drafted, corrected by a person | the person's number kept; marked who changed it |
| MC-U03 | Roadmap confidence | P50, P80, P90 end dates; the chance of each plateau by its date; the S-curve; the work packages most often critical |
| MC-U04 | An option's business case | the net value's range, the chance it is positive, the lines that matter most |
| MC-U05 | Risk exposure | the chance the year's losses pass an amount ("1 in 10 of more than R5m"); the risks that drive it; before and after controls |
| MC-U06 | Scenario planning with chances | each option's chance of being best, in each future and across them |
| MC-U07 | A study with no ranges yet | says what to do next, no error |
| MC-U08 | Each tab has its own address (Release 13) | opened from the address, the same tab |
| MC-U09 | The working shown | the inputs, runs, seed and how each figure is made, so a person can check it |
| MC-U10 | Journeys in the self-test (Release 14.5's rule) | a journey per screen: make a study, fill ranges, run, read each result |

## Reports and exports (R14.7.6)

| Id | Case | Expected |
| --- | --- | --- |
| MC-R01 | The project report | the latest run of each study: the figures and the S-curve |
| MC-R02 | The results as CSV | the percentiles and the chances; opens in Excel |
| MC-R03 | A presentation deck through MCP (Release 5.7) | the S-curve and the tornado as pictures, with their sources |

## Across the installation

| Id | Case | Expected |
| --- | --- | --- |
| MC-X01 | Backup and restore (B1, B2) | studies, ranges, groups, runs and the risk scales come back the same |
| MC-X02 | The DR drill | the same, counted |
| MC-X03 | A model package exported and imported | the model goes; studies stay with the project (they are not in the model) |
| MC-X04 | Coverage | eax/monte_carlo.py at 100% (pure code); the rest at the 85% bar (D934) |
| MC-X05 | SonarQube and the security gate | nothing new |
