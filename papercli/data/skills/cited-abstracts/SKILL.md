---
name: cited-abstracts
description: Fetch the abstracts of the paper's resolved references, for judging whether a cited work supports the claim it is attached to.
---

Run from the repo root:

    papercli abstracts

It prints JSON mapping cite key to abstract for every reference in refs.json that has one.

Use it for claim–citation support checks: read the claim in main.tex, read the cited work's abstract, and give a verdict — supported, partial, or unsupported — with an honest confidence. A key with no abstract means support cannot be checked from here: say exactly that in the finding and lower the confidence; never guess what a paper you cannot see might claim.
