---
title: Check and improve data quality
summary: See how complete, correct and current a model is, and fix what it finds.
group: Data quality
roles: model-admin, user
---

## Why do this

Improving quality is a cycle: see the score, find what fails, fix it with the wizard, merge duplicates, add rules so it stays fixed. See [[data-quality]].

Quality is not a one-off clean-up but a habit: rules catch problems as they are saved, the score shows the trend, and owners fix what is theirs. A model people trust is one they keep using.

**In TOGAF terms:** Supports every ADM phase: the content framework is only useful if its building blocks are complete and correct. See [[ea-explorer-and-togaf]].

**The goal:** A model's data is complete, correct, current, connected and unique.

> **Before you start** You need a role on the model; fixing needs Architect or higher.

## The ways to do it

1. Open the model, its **Quality** tab: a score, completeness, rules passed, freshness, orphans and likely duplicates.
2. Open any tile to see the entities behind it.
3. **Model Admin › Wizards, Improve data quality** walks through what it finds one entity at a time: fill in, not
   applicable, or still correct.
4. Commit the changes (the Changes tab).

## Check it worked

The score rises as changes are committed. The KPIs tab keeps the score month by month.

## Each task, one page

1. [See a model's quality score](../how-do-i/see-a-models-quality-score.md)
2. [See the checks a model fails](../how-do-i/see-failing-checks.md)
3. [Run the data quality wizard](../how-do-i/run-the-data-quality-wizard.md)
4. [Find and merge duplicates](../how-do-i/find-and-merge-duplicates.md)
5. [Add a data quality rule](../how-do-i/add-a-quality-rule.md)
6. [Commit your changes](../how-do-i/commit-your-changes.md)

## Related

- [Find and merge duplicates](../how-do-i/find-and-merge-duplicates.md)
