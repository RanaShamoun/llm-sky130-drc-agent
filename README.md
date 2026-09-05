# An LLM Agent for SKY130 Design Rule Interpretation & Explanation

**Team:** [Rana Shamoun] 

**Track:** Option 2 — LLMs + AI Agent System

**Target completion:** November 25, 2026

---

## Abstract

Manufacturable chip layouts must satisfy thousands of geometry-based design rules, enforced through Design Rule Checking (DRC) against a foundry's rule deck. This project builds an LLM agent that interprets natural-language SKY130 design rules, delegates all geometric verification to KLayout's real DRC engine (rather than reasoning about geometry directly, a known LLM weakness), and produces grounded, cited, plain-language explanations of pass/fail verdicts. Unlike recent work that trains or benchmarks LLMs to *generate* DRC checker code (e.g., Rule2DRC, DRC-Coder), this project treats DRC script correctness as solved by existing tooling and instead focuses the LLM's role on rule interpretation, violation explanation, and grounded verification — evaluated across three LLMs (one open-source, two closed, spanning budget and frontier tiers) on cost, latency, and accuracy against a shared evaluation set labeled by an independent oracle. A working feasibility spike has already confirmed the core pipeline: a synthetic layout with a deliberate metal1-spacing violation was correctly flagged by KLayout's SKY130 manufacturing rule deck end-to-end in batch mode.

---

## Repository Structure

```
/proposal/          - Project proposal document (Canvas submission)
/literature/         - Literature & SOTA survey (this repo, see LITERATURE_SURVEY.md)
/novelty-audit/       - AI novelty & feasibility audit (see NOVELTY_AUDIT.md)
/spike/             - Feasibility spike documentation and reproducible commands
/src/                - Agent implementation (Planner / Executor / verification)
/eval/               - Evaluation set generation and labeling scripts
```

See `LITERATURE_SURVEY.md` and `NOVELTY_AUDIT.md` in this repository for the required literature review and AI critique deliverables.