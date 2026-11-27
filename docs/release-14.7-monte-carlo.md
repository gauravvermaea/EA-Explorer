# Release 14.7: Monte Carlo simulation (decided 27 Nov 2026, D957; to be built)

The owner, 27 Nov 2026, 08:10: "will EA benefit from monte carlo simulation?"; 08:11: "Please make a new release for
this but before we start documentation. We will discuss then". Discussed at 15:13 to 15:20 the same day ("First
explain me what is monte carlo and how does it help?"; "Yes lets answer one by one"): the seven questions at the end
are answered (D957), and the release's rows (R14.7.1 to R14.7.6 in docs/build-phases.md) are planned. Nothing is built
yet. The test cases, written first (15:34): [release-14.7-test-cases.md](release-14.7-test-cases.md).

## What it answers

Monte Carlo runs a plan or a calculation thousands of times, each time drawing every uncertain number from its range,
and counts how the outcomes fall. It answers "how likely is this to work out", where a single estimate answers "what
is the best guess". In EA that matters where several uncertain numbers combine in one decision:

| Question | Today | With Monte Carlo |
| --- | --- | --- |
| When will the target architecture be in place? | the work packages' end dates, each one guess | "70% likely by Q3 2028; 90% by Q1 2029"; which work packages and dependencies drive the delay most |
| Does the business case of an option still hold? | one total cost, one benefit | the range of net value and the chance it is positive; which cost lines matter most |
| How much does the estate's risk add up to? | a heat map of risks, each likelihood × impact | the chance the year's losses pass an amount ("1 in 10 of more than R5m"), the risks that drive it |
| Which option is best across the futures? | scenario planning's scores per future, most robust and least regret (Release 10) | the chance each option beats the others, within each future and across them |

Where it does not help, and is not proposed: questions of structure (what depends on what, the gaps, the target),
which the model answers itself; and numbers nobody can give a range for: a made-up distribution gives confident
nonsense, so every input comes from a person who owns the number, as three numbers (low, most likely, high).

## What EA Explorer has already, to build on

* **Work packages, plateaus and deliverables** have Start Date and End Date (ArchiMate 4 metamodel, eax/seed/archimate4.py);
  work packages relate to each other (triggering and flow say what comes before what) and to the plateaus they lead to.
* **Annual Cost** on applications, technology and contracts; the scenario models (D492) and options of scenario planning.
* **The risk register** (Release 12, R12.5, eax/risk_register.py): risk Assessments with Likelihood and Impact (1 to 5),
  inherent and residual risk, the controls that reduce them.
* **Scenario planning and game theory** (Release 10, eax/scenario_planning.py, eax/game_theory.py): a study in a
  project, run by the person's AI through MCP, saved after a preview and a yes (D458); the working done by EA Explorer's
  own code, never the AI (D857 (4)), and shown so a person can check it; the project's Scenario planning tab shows it,
  read only.

The proposal follows the same pattern: the numbers are worked out by EA Explorer's own code (pure, no database, its
working shown), the inputs are kept in the project, and it is started and filled in by the person's AI or on a screen
(a question below).

## What is proposed (the release's parts)

**R14.7.1 The engine** (eax/monte_carlo.py, pure code like game_theory.py): three-point ranges (triangular and PERT),
a fixed seed so the same inputs always give the same answer, 10,000 runs by default; for a schedule, the network of
work packages walked in order (each starts when all before it end); the results: percentiles (P10, P50, P80, P90), the
chance of meeting a date or a budget, a histogram and an S-curve, and what drives the outcome most (each input's
correlation with the result: the "tornado"). Fast enough for a page: 10,000 runs of 200 work packages in a few seconds.

**R14.7.2 Roadmap confidence**: for a project's (or a model's) work packages, their ranges of duration (or of start and
end) and the dependencies the model already has, run as above: "how likely is plateau X by date Y", which work
packages are most often on the critical path. The ranges kept with the work packages (three attributes, or one range
attribute: a question below).

**R14.7.3 Option cost and benefit**: the cost lines and benefit lines of an option (or of a scenario model against
the baseline), each a range, over a number of years: the range of net value, the chance it is positive, the lines
that matter most.

**R14.7.4 Risk exposure**: the project's or model's risk Assessments, each with a chance in the year and a range of
loss (the 1 to 5 scales mapped to a chance and an amount the organisation sets once, or the amounts given directly):
the losses added up across runs, the chance of passing an amount, the risks that drive it, before and after controls.

**R14.7.5 Scenario planning with chances**: an option's score in a future given as a range; the chance each option is
the best within each future and across the futures (weighted by how likely each future is, if the study gives that).

**R14.7.6 Where it shows, and the tests**: the results on the project's tabs (Roadmap confidence, the Scenario planning
tab, the risk register) and in the project report; the MCP tools for the AI; the self-test's journeys and API checks
for each part, and unit tests of the engine against known answers (a single task's PERT mean and spread, a two-path
network, a sum of independent ranges).

## Questions for the discussion

1. **Which parts first?** All four uses, or start with one (roadmap confidence is the one most asked for in EA
   practice; risk exposure the one boards and risk committees understand best)?
2. **Who fills in the ranges:** the person's AI through MCP, as scenario planning (it reads the project's documents and
   suggests, the person says yes), or a screen too (a table of work packages with low, likely and high)?
3. **Where are the ranges kept:** as attributes on the elements (Duration Low, Duration Likely, Duration High on a work
   package: they travel with the model, its exports and its history), or in the project's own tables as a study (the
   model stays as it is; several studies can differ)?
4. **Distributions:** three-point only (triangular or PERT), or also others (log-normal for costs, a fixed chance for an
   event)? Three-point is what people can give; the rest could wait.
5. **Correlation:** are the ranges independent, or may the person say that some move together (the same supplier's
   work packages slipping together)? Independent is simpler and understates the spread; a simple "these move together"
   group could be a middle way.
6. **Money:** one currency per study, or the installation's currency? And the risk scales: does the organisation set
   once what Likelihood 1 to 5 and Impact 1 to 5 mean in chance and money?
7. **Its own release number:** 14.7 after the layer-to-domain rename (14.6), or a release of its own (15)?

## The owner's answers (27 Nov 2026, D957)

1. **All four uses** in 14.7: roadmap confidence, an option's cost and benefit, risk exposure, scenario planning with
   chances (the recommendation was roadmap and risk first; the owner chose all four).
2. **Both the AI and a screen:** the person's AI drafts the ranges through MCP, each with where it came from, shown as
   a preview and saved on a yes; a screen (a table with Low, Likely and High) lets a person enter or correct them. The
   working is always EA Explorer's own code, never the AI's.
3. **In a study of the project**, as scenario planning: the model is not changed, several studies can differ (the
   supplier's estimates against our own), each run is kept with the inputs it used. A study starts from the model's
   dates, costs and risk Assessments, so nothing is typed twice.
4. **PERT (the default), triangular, and an event** (yes or no, with a chance: a risk happening in the year, a
   regulator's delay). Log-normal and the rest wait.
5. **"Move together" groups:** an input may be put in a named group (a supplier, a currency) with a strength (weak,
   medium, strong) and the group's inputs are drawn together; everything else is independent. No correlation matrix.
6. **One currency per study** (the installation's currency by default). **The organisation sets the risk scales
   once**: what Likelihood 1 to 5 means as a chance in the year and Impact 1 to 5 as a range of loss, with defaults
   given; a study may override one risk's chance and amount.
7. **Release 14.7**, after 14.6 (layer to domain), before 22; nothing renumbered.
