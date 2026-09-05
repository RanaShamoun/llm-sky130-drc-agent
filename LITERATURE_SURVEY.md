# Literature & SOTA Survey

All papers below are within the last 1–3 years (2023–2026) and directly relevant to LLM applications in Electronic Design Automation (EDA), with emphasis on design rule checking (DRC) specifically, since that is this project's core domain.

---

### 1. Rule2DRC: Benchmarking LLM Agents for DRC Script Synthesis with Execution-Guided Test Generation
**Kim, Byun, Hwang, Park, Song — Seoul National University / Samsung AI Center. ICML 2026.**

The closest prior work to this project. Introduces a large-scale benchmark (1,000 rule-to-script tasks, ~14,000 evaluation GDS layouts) for LLM agents that translate natural-language SKY130-style design rules into executable KLayout DRC scripts, scored by execution correctness rather than code similarity. Also proposes SplitTester, an execution-feedback-driven method for selecting the best candidate script among several LLM-generated options.

**Relevance:** confirms the DRC-interpretation space is active and well-resourced at a top ML venue; this project deliberately does *not* compete on script generation (Rule2DRC's task) and instead targets rule interpretation/explanation using an already-correct DRC engine as a tool, a different sub-problem within the same domain.

### 2. DRC-Coder: Automated DRC Checker Code Generation Using LLM Autonomous Agent
**Chang, Ho, Li, Chen, Ren — NVIDIA. ISPD 2025.**

An LLM autonomous agent that generates DRC checker code (executable rule-checking scripts) from natural-language rule descriptions, iterating using compiler/execution feedback.

**Relevance:** a second, industry-authored (NVIDIA) confirmation that "LLM writes the DRC checker" is an active research direction — reinforcing that this project should explicitly avoid that framing and instead treat the checker (KLayout + SKY130 deck) as a fixed, trusted tool the agent calls.

### 3. ChatEDA: A Large Language Model Powered Autonomous Agent for EDA
**Wu, He, Zhang, Yao, Zheng, Zheng, Yu — CUHK / Shanghai AI Lab. IEEE TCAD 2024.**

An LLM-driven autonomous agent (built on a fine-tuned model, AutoMage) that automates the full RTL-to-GDSII flow by decomposing natural-language user requirements into sub-tasks and invoking EDA tool APIs to execute them, evaluated on a 50-task benchmark (ChatEDA-Bench).

**Relevance:** an early, influential example of the Planner/task-decomposition + tool-execution agent pattern this project also uses, but scoped to full-flow automation rather than DRC interpretation specifically — a useful architectural reference and a broader-scope point of comparison for framing this project's narrower focus as an intentional trade-off.

### 4. AutoEDA: Enabling EDA Flow Automation through Microservice-Based LLM Agents
**Lu, Au, Zhang, Pan, Wang, Li, Zhang, Chen et al. arXiv 2025 (v2 2026).**

Proposes an MCP (Model Context Protocol)-based multi-agent framework for EDA flow automation with task decomposition, tool selection, and automated error handling, reporting up to 9.9x higher accuracy than naive LLM approaches while cutting token usage ~97% via locally fine-tuned agents.

**Relevance:** demonstrates that tool-call efficiency (not just task accuracy) is treated as a first-class metric in current EDA-agent literature, supporting this project's inclusion of tool-call count and latency in its evaluation metrics (Section F of the proposal).

### 5. Large Language Models for EDA: Future or Mirage?
**He, Pu, Wu, Qiu, Yu — CUHK. ISPD 2024 / ACM TODAES 2025.**

A survey examining LLM use in EDA both as assistants and autonomous agents across the design flow, critically assessing which applications are genuinely promising versus overhyped.

**Relevance:** provides a skeptical, critical framing this project should adopt — i.e., justifying why the LLM's role here is deliberately narrow (interpretation/explanation) rather than attempting end-to-end automation, which the survey suggests remains an open challenge for many EDA sub-tasks.

### 6. A Survey of Research in Large Language Models for Electronic Design Automation
**ACM Transactions on Design Automation of Electronic Systems, 2025.**

A meta-study reviewing LLM-for-CAD publications from 2022–2024 across system-level design through physical implementation, cataloguing which design phases have received the most LLM research attention.

**Relevance:** situates DRC-focused agent work (this project's focus) within the broader LLM-for-EDA landscape and helps confirm which sub-areas remain comparatively under-explored versus saturated.

### 7. The Dawn of Agentic EDA: A Survey of Autonomous Digital Chip Design
**arXiv 2025/2026.**

A recent survey specifically on *agentic* (as opposed to single-shot prompting) approaches to digital chip design automation, cataloguing multi-agent frameworks, tool-use patterns, and autonomous design-loop architectures across the field.

**Relevance:** directly informs this project's Planner–Executor–verification architecture choice and its scoping decision to omit a full iterative Critic loop, situating that decision against the broader landscape of agentic-EDA design patterns.

### 8. Bridging the Last Mile of Circuit Design: PostEDA-Bench, a Hierarchical Benchmark for PPA Convergence and DRC Fixing
**arXiv 2026.**

Introduces a benchmark for LLM agents on post-layout tasks including DRC *violation fixing* (not just detection), evaluated hierarchically against PPA (power/performance/area) convergence criteria.

**Relevance:** a closely adjacent but distinct task — fixing violations rather than explaining them — that reinforces this project's chosen boundary: verdict + grounded explanation, not automated layout repair, is the appropriate scope for a solo, 11-week project.

### 9. LLM for EDA in Front-End Design: Challenges and Opportunities
**arXiv 2026.**

A recent overview paper cataloguing LLM applications and open challenges across front-end EDA tasks (RTL generation, verification, testbench generation, debugging), with an extensive reference list spanning 2023–2025 work.

**Relevance:** useful as a broader reference map of adjacent LLM-for-EDA subfields (verification, debugging) that share methodological concerns — e.g., grounding LLM outputs in tool execution feedback — with this project's design.

---

## Summary Takeaway

The literature confirms that "LLM + DRC" is an active research area with recent top-venue work (Rule2DRC at ICML 2026, DRC-Coder at ISPD 2025 from NVIDIA), which is a meaningfully different picture than the initial "blue ocean" assumption behind this project's earliest framing. However, essentially all closely related work targets **DRC script/checker code generation** as the LLM's task. This project instead treats the DRC engine as a fixed, already-correct tool and focuses the LLM's contribution on **rule interpretation, grounded explanation, and multi-model cost/latency evaluation** — a genuinely different sub-problem that has not been the focus of the papers surveyed above. See `NOVELTY_AUDIT.md` for the full critique and repositioning rationale.