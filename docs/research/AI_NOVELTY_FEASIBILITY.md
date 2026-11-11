# AI Novelty & Feasibility Audit

This document is the AI critique summary required for the project deliverable. It was produced by prompting Claude with the project idea and a request to critique its novelty, red-ocean risk, and feasibility, after a literature search turned up closely related recent work. It is reproduced here largely as generated, lightly formatted for readability.

---

## AI Critique Summary

**Prompt given to the AI:** "Here is my project idea: an LLM agent that interprets natural-language SKY130 design rules, uses KLayout's DRC engine as a tool to verify layouts, and explains violations in plain language, compared across 3 LLMs on cost/latency/accuracy. Is this genuinely novel? What recent papers have explored this? What are the limitations, and how can I make it more unique for a graduate-level academic project?"

**AI response:**

### Is this novel?

Partially, but less than it may first appear. A literature search surfaces two closely related, recent, credible papers:

- **Rule2DRC** (Kim et al., ICML 2026, Seoul National University + Samsung AI Center) — a large benchmark (1,000 tasks, ~14,000 layouts) for LLM agents that translate natural-language design rules into executable KLayout DRC scripts, evaluated by execution correctness.
- **DRC-Coder** (Chang et al., ISPD 2025, NVIDIA) — an LLM autonomous agent that generates DRC checker code from natural-language rule descriptions using execution feedback.

Both of these are top-venue, well-resourced (one from a major EDA research group at NVIDIA, one from a university lab in collaboration with Samsung AI Center), and both target essentially the same domain (LLMs + natural-language design rules + KLayout DRC). This means the domain is **not** an empty "blue ocean" the way an earlier framing of this idea assumed — it is an active, credible research area with recent top-conference publications.

### Where the genuine differentiation lies

The key distinction is the LLM's *task*. Rule2DRC and DRC-Coder both ask the LLM to **generate DRC script/checker code** — i.e., the LLM's output is executable code that performs the geometric check. This project's design does something different: it treats the DRC engine (KLayout + the existing, official SKY130 rule deck) as a **fixed, already-correct tool**, and asks the LLM to (a) interpret the natural-language rule into a structured query, (b) invoke the existing tool rather than write new checking code, and (c) produce a grounded, cited, plain-language explanation of the tool's verdict. This is a genuinely different sub-problem: it is closer to a "verification-and-explanation agent" than a "code-generation agent," and neither surveyed paper evaluates explanation quality, groundedness/citation correctness, or multi-model cost/latency tradeoffs — all of which are core to this project's evaluation-first framing per the course's "Option 2" requirements.

### Remaining limitations to be upfront about

- **Narrower novelty claim than originally framed.** This should not be pitched as "no one has done LLMs for DRC" — that claim is now false given Rule2DRC and DRC-Coder. It should be pitched specifically as "an evaluation-first comparison of LLM rule-interpretation-and-explanation quality, grounded by an existing DRC engine, distinct from prior code-generation-focused work."
- **Smaller scale than the cited benchmarks.** Rule2DRC's benchmark has 1,000 tasks and ~14,000 layouts; this project's 50-case eval set is appropriately scoped for a solo or maybe two people, 11-week course project, but should not be presented as competing with that benchmark's scale — it should be framed as a focused, hand-validated evaluation rather than a new large-scale benchmark contribution.
- **The "explanation grounding" evaluation is the most genuinely under-explored angle.** Neither Rule2DRC nor DRC-Coder evaluates whether an LLM's natural-language explanation of a violation correctly cites the specific rule and measurement — both are scored purely on functional/execution correctness of generated code. This is the strongest, most defensible novelty angle available and should be emphasized as the project's central contribution rather than treated as a minor add-on.

### Recommendation

Reposition the project's contribution explicitly around **explanation groundedness and multi-model cost/latency evaluation for a DRC-verification agent**, not around DRC automation generally. Cite Rule2DRC and DRC-Coder directly in the proposal as related work the project is deliberately differentiated from, rather than omitting them — a grader or reviewer familiar with the space would otherwise reasonably ask "how is this different from Rule2DRC?", and having a ready, honest, specific answer is stronger than not mentioning it.

---

## Feasibility Assessment (supplementary)

Independent of the novelty question, feasibility for this specific scope was validated empirically rather than assumed: a working feasibility spike confirmed that KLayout's batch-mode DRC engine, run against the official SKY130 manufacturing rule deck, correctly flags a deliberately introduced test violation (metal1 spacing, rule `m1.2`) end-to-end on Rana's own machine. This addresses the primary feasibility risk (whether the chosen oracle-based evaluation approach actually works) ahead of the main implementation phase. See `docs/research/spike/` in the project repository for full reproduction details.