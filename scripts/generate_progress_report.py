from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT_DOCX = ROOT / "DRC_Explain_Progress_Report.docx"
OUT_PDF = ROOT / "DRC_Explain_Progress_Report.pdf"
REPOSITORY = "https://github.com/RanaShamoun/llm-sky130-drc-agent"


def add_heading(document, text, level=1):
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True


def add_bullets(document, items):
    for item in items:
        document.add_paragraph(item, style="List Bullet")


document = Document()
section = document.sections[0]
section.top_margin = Inches(0.65)
section.bottom_margin = Inches(0.65)
section.left_margin = Inches(0.75)
section.right_margin = Inches(0.75)

title = document.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title_run = title.add_run("DRC Explain: Progress Report")
title_run.bold = True
title_run.font.size = Pt(20)

subtitle = document.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle_run = subtitle.add_run(
    "CMPE 258 Deep Learning Project\n"
    "Rana Shamoun and Giovanni Cascone | November 22, 2026"
)
subtitle_run.font.size = Pt(11)

add_heading(document, "Repository")
repository = document.add_paragraph()
repository.add_run("GitHub: ").bold = True
repository.add_run(REPOSITORY)

add_heading(document, "Project summary")
document.add_paragraph(
    "DRC Explain evaluates whether a language model can interpret a layout question, "
    "select relevant SKY130 design rules, request KLayout geometry checks, and explain "
    "the result using verifier-accepted evidence. KLayout remains authoritative, while "
    "a deterministic verifier rejects inconsistent or unsupported final claims."
)

add_heading(document, "Completed work")
add_bullets(document, [
    "Pinned the SKY130 sources, layer map, KLayout 0.30.7 checker, and eight-rule supported scope.",
    "Created 50 benchmark layouts, six development layouts, six unsupported-scope probes, and 56-case labels.",
    "Created a separate 24-layout held-out dataset with 3 refusal probes, private labels, and native-RDB verification.",
    "Implemented rule retrieval, layout inspection, selected-rule DRC, bounded tool calls, structured claim verification, and refusal handling.",
    "Implemented local Ollama Qwen3 8B plus optional Gemini 3.5 Flash-Lite and OpenAI GPT-4o adapters.",
    "Built a resumable A/B/C experiment runner, evaluator-only scoring, local UI, raw traces, and provider metadata capture.",
    "Completed 113 passing automated tests and 1 intentional platform-specific skip.",
])

add_heading(document, "Frozen three-model comparison")
table = document.add_table(rows=1, cols=5)
table.style = "Table Grid"
for index, text in enumerate(["Model", "A", "B", "C", "ERROR"]):
    table.rows[0].cells[index].text = text
for row in [
    ("Qwen3 8B", "23/50 (46%)", "29/50 (58%)", "50/50 (100%)", "5"),
    ("GPT-4o", "29/50 (58%)", "27/50 (54%)", "50/50 (100%)", "0"),
    ("Gemini 3.5 Flash-Lite", "41/50 (82%)", "43/50 (86%)", "46/50 (92%)", "9"),
]:
    cells = table.add_row().cells
    for index, text in enumerate(row):
        cells[index].text = text

document.add_paragraph(
    "Each grid used 50 benchmark layouts plus six unsupported-scope probes, "
    "under matching public inputs, prompt text, implementation hashes, A/B/C "
    "conditions, and one repetition."
)
add_bullets(document, [
    "GPT-4o completed all 168 records with no errors. Its locally estimated API cost was $1.346.",
    "Qwen3 completed all 168 records with 5 errors; all 50 benchmark C verdicts were correct.",
    "Gemini completed all 168 records with 9 errors: 3 HTTP 503s, 2 turn-budget failures, and 4 protocol failures.",
    "Gemini recorded no HTTP 429 retries in the full grid. Its settled paid-tier estimate was $0.294; three requests remained uncertain reservations.",
])

add_heading(document, "Validity limitations")
add_bullets(document, [
    "The 50-layout benchmark is small and was previously exposed during team debugging.",
    "The benchmark is curated and not representative of full-chip signoff workloads.",
    "The benchmark is project-constructed; it is not a standard open-source SKY130/OpenROAD or Magic test suite.",
    "Three held-out Qwen3 C repetitions scored 24/24 with no errors, but this is one-model evidence only.",
    "The agent explains and verifies DRC results. It does not edit GDS layouts or run layout-fixing tools.",
    "The oracle and implementation use the same KLayout engine, so this is not an independent foundry oracle.",
    "The supported scope covers eight ordinary metal1/metal2 and via-enclosure rules.",
    "A/B outputs are unverified coordinate/retrieval predictions; C also covers only model-selected rules.",
    "Each model used one repetition, so reported proportions do not estimate run-to-run variability.",
    "Every ERROR remains in the fixed-denominator accuracy and must not be hidden or replaced by a retry.",
])

add_heading(document, "What is working")
add_bullets(document, [
    "Deterministic KLayout evidence, sources, and claim verification are implemented and tested.",
    "The frozen Qwen and GPT-4o C grids reached 50/50 benchmark verdict accuracy.",
    "Gemini reached 82% in A and 86% in B, with 46/50 in C and no 429 throttling.",
    "The local UI, demo command, experiment manifests, and raw traces support reproducible discussion.",
])

add_heading(document, "Questions for professor feedback")
add_bullets(document, [
    "The professor confirmed that the exposed 168-record runs are only sanity checks.",
    "The professor recommends 24–56 genuinely unseen layouts and 2–3 repetitions.",
    "The final report should count ERROR under a fixed denominator and break execution-error rate out separately.",
    "The final deliverables are slides due December 3 and an <=8-page LaTeX report plus GitHub repo and 2-minute demo due December 15.",
])

add_heading(document, "Immediate next steps")
add_bullets(document, [
    "Preserve and separate historical/exposed runs; do not pool or hide them.",
    "Run 24 unseen layouts for all selected models with 2–3 repetitions when API and local budgets permit.",
    "Keep every original ERROR and report mean/range or confidence intervals across repetitions.",
    "Finish the conference-format LaTeX report and 2-minute demo video.",
    "Upload the progress PDF/DOCX and linked repository to Canvas.",
])

document.save(OUT_DOCX)

styles = getSampleStyleSheet()
pdf = SimpleDocTemplate(
    str(OUT_PDF),
    pagesize=letter,
    rightMargin=54,
    leftMargin=54,
    topMargin=42,
    bottomMargin=42,
)
story = []
story.append(Paragraph("DRC Explain: Progress Report", styles["Title"]))
story.append(Paragraph(
    "CMPE 258 Deep Learning Project<br/>"
    "Rana Shamoun and Giovanni Cascone | November 22, 2026",
    styles["Heading3"],
))
story.append(Paragraph(f"<b>Repository:</b> {REPOSITORY}", styles["Normal"]))


def section(title):
    story.append(Spacer(1, 8))
    story.append(Paragraph(title, styles["Heading2"]))


def bullets(items):
    for item in items:
        story.append(Paragraph("• " + item, styles["Normal"]))
        story.append(Spacer(1, 3))


section("Project summary")
story.append(Paragraph(
    "DRC Explain evaluates whether a language model can interpret a layout question, "
    "select relevant SKY130 design rules, request KLayout geometry checks, and explain "
    "the result using verifier-accepted evidence.",
    styles["Normal"],
))

section("Completed work")
bullets([
    "Pinned KLayout, SKY130 sources, layer map, and eight-rule supported scope.",
    "Built rule retrieval, layout inspection, selected-rule DRC, bounded tool calls, structured final answers, and deterministic verification.",
    "Created a separate 24-layout held-out dataset with private labels and native-RDB verification.",
    "Implemented local Qwen3 8B plus optional Gemini 3.5 Flash-Lite and GPT-4o adapters.",
    "Built a resumable A/B/C runner, local UI, traces, evaluator-only scoring, and reproducibility checks.",
    "Completed 113 passing automated tests and 1 intentional platform-specific skip.",
])

section("Frozen three-model comparison")
data = [
    ["Model", "A", "B", "C", "ERROR"],
    ["Qwen3 8B", "23/50 (46%)", "29/50 (58%)", "50/50 (100%)", "5"],
    ["GPT-4o", "29/50 (58%)", "27/50 (54%)", "50/50 (100%)", "0"],
    ["Gemini 3.5 Flash-Lite", "41/50 (82%)", "43/50 (86%)", "46/50 (92%)", "9"],
]
table = Table(data, repeatRows=1, colWidths=[112, 82, 82, 82, 48])
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))
story.append(table)
bullets([
    "Each grid used 56 inputs and one repetition under matching prompt, implementation, and public-input hashes.",
    "GPT-4o completed every record; Qwen completed every record with 5 errors; Gemini completed every record with 9 errors.",
    "Gemini had no 429 retries in the full grid.",
    "These are preliminary frozen-grid outcomes, not independent foundry validation.",
])

section("Validity limitations")
bullets([
    "The 50-layout benchmark is small and previously exposed.",
    "It is project-constructed, not a standard open-source SKY130/OpenROAD or Magic suite.",
    "The agent explains and verifies DRC results but does not edit GDS layouts.",
    "The oracle and implementation use the same KLayout engine.",
    "A/B outputs are predictions; C verifies only model-selected rules.",
    "One repetition provides no run-to-run uncertainty.",
    "ERROR records remain in fixed-denominator accuracy.",
])

section("Questions for professor feedback")
bullets([
    "The professor confirmed that the exposed 168-record runs are sanity checks, not generalization evidence.",
    "The professor recommends 24–56 unseen layouts and 2–3 repetitions.",
    "ERROR is included in fixed-denominator accuracy and reported separately as execution-error rate.",
    "Slides are due December 3; the <=8-page LaTeX report, repository, and 2-minute demo are due December 15.",
])

section("Immediate next steps")
bullets([
    "Preserve and separate historical/exposed runs rather than pooling or hiding them.",
    "Run the held-out set across selected models with 2–3 repetitions when budgets permit.",
    "Keep every original record and report mean/range or intervals rather than replacing `ERROR` outcomes.",
    "Finish the conference-format LaTeX report and 2-minute demo.",
    "Submit the progress PDF/DOCX and repository to Canvas.",
])

pdf.build(story)
print(OUT_DOCX)
print(OUT_PDF)
