"use strict";
const byId = (id) => document.getElementById(id);
let cases = [];
let current = null;
function text(tag, value) { const element = document.createElement(tag); element.textContent = value; return element; }
function draw() {
  const canvas = byId("layout");
  const context = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const ratio = devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  context.scale(ratio, ratio);
  context.fillStyle = "#e8eeeb"; context.fillRect(0, 0, width, height);
  context.strokeStyle = "#d5dfd9"; context.lineWidth = 1;
  for (let offset = 0; offset < width; offset += 24) { context.beginPath(); context.moveTo(offset, 0); context.lineTo(offset, height); context.stroke(); }
  for (let offset = 0; offset < height; offset += 24) { context.beginPath(); context.moveTo(0, offset); context.lineTo(width, offset); context.stroke(); }
  const layers = current?.layout?.layers || [];
  const points = layers.flatMap(layer => layer.polygons.flatMap(polygon => polygon.points_um));
  if (!points.length) { context.fillStyle = "#627074"; context.font = "14px Bahnschrift"; context.fillText("No layout attached", 24, 36); return; }
  const xs = points.map(point => point[0]), ys = points.map(point => point[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((width - 70) / Math.max(maxX - minX, 0.001), (height - 70) / Math.max(maxY - minY, 0.001));
  const left = (width - (maxX - minX) * scale) / 2;
  const bottom = (height - (maxY - minY) * scale) / 2;
  const colors = {m1:"#d15b72", m2:"#2498b0", via:"#d6ab24"};
  for (const layer of layers) {
    context.fillStyle = colors[layer.name] || "#65756b"; context.strokeStyle = context.fillStyle;
    for (const polygon of layer.polygons) {
      context.beginPath();
      polygon.points_um.forEach((point, index) => {
        const horizontal = left + (point[0] - minX) * scale;
        const vertical = height - bottom - (point[1] - minY) * scale;
        if (index === 0) context.moveTo(horizontal, vertical); else context.lineTo(horizontal, vertical);
      });
      context.closePath(); context.globalAlpha = 0.45; context.fill(); context.globalAlpha = 1; context.lineWidth = 2; context.stroke();
    }
  }
  context.fillStyle = "#20292a"; context.font = "12px Bahnschrift";
  context.fillText(`${(maxX - minX).toFixed(3)} x ${(maxY - minY).toFixed(3)} um`, 14, height - 13);
}
function selectCase() {
  current = cases.find(item => item.case_id === byId("case").value);
  byId("question").value = current.question;
  byId("cell").textContent = current.layout?.top_cell || "None";
  byId("shape-count").textContent = `${current.layout?.shape_count || 0} shapes`;
  byId("verdict").textContent = "Pending"; byId("verdict").dataset.value = "";
  byId("explanation").textContent = "No result yet.";
  for (const id of ["checks", "selections", "metrics", "trace", "error"]) byId(id).replaceChildren();
  draw();
}
async function run() {
  byId("run").disabled = true; byId("case").disabled = true; byId("question").disabled = true;
  byId("status").textContent = "Running"; byId("error").textContent = "";
  byId("verdict").textContent = "Pending"; byId("verdict").dataset.value = "";
  byId("explanation").textContent = "Waiting for local model and tool results.";
  const started = Date.now();
  const timer = setInterval(() => {
    byId("status").textContent = `Running | ${Math.floor((Date.now() - started) / 1000)} s`;
  }, 1000);
  for (const id of ["checks", "selections", "metrics", "trace"]) byId(id).replaceChildren();
  try {
    const response = await fetch("/api/run", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({case_id:current.case_id, question:byId("question").value})});
    const data = await response.json();
    if (response.status === 409) {
      byId("status").textContent = "Busy";
      byId("verdict").textContent = "Pending";
      byId("explanation").textContent = "Another request is still running on this server. Wait for it to finish before submitting again. Refreshing this page does not cancel a run.";
      return;
    }
    if (!response.ok) throw new Error(data.error || "Run failed");
    const result = data.result;
    byId("verdict").textContent = result.verdict; byId("verdict").dataset.value = result.verdict;
    byId("explanation").textContent = result.explanation;
    for (const check of result.checks || []) {
      const element = text("div", `${check.rule_id}: ${check.status} | limit ${check.limit_um} um | ${check.measured_values_um?.length ? "measured " + check.measured_values_um.join(", ") + " um" : "no scalar measurement"}`);
      element.className = "check";
      if (check.source_url?.startsWith("https://github.com/")) { const link = text("a", " Source"); link.href = check.source_url; link.target = "_blank"; link.rel = "noopener noreferrer"; element.append(link); }
      byId("checks").append(element);
    }
    for (const selection of result.selections || []) byId("selections").append(text("p", `${selection.rule_id}: ${selection.justification}`));
    for (const [label, value] of [["Model",result.model],["Latency",`${result.latency_s} s`],["Tool Calls",result.tool_call_count],["API Cost",result.cost_usd === 0 ? "$0 (local)" : "Unestimated"],["Verification", result.verification?.accepted ? "Accepted" : "Not accepted"]]) byId("metrics").append(text("dt", label), text("dd", value));
    for (const [index, call] of data.tool_trace.entries()) {
      const detail = document.createElement("details");
      detail.append(text("summary", `${index + 1}. ${call.tool} | ${call.response.ok ? "OK" : "ERROR"} | ${call.latency_s} s`), text("pre", JSON.stringify(call, null, 2)));
      byId("trace").append(detail);
    }
    byId("status").textContent = result.verdict === "ERROR" ? "Run Failed" : "Complete";
  } catch (error) {
    byId("error").textContent = error.message; byId("verdict").textContent = "ERROR"; byId("verdict").dataset.value = "ERROR"; byId("status").textContent = "Setup Required";
    byId("explanation").textContent = "No verdict issued. " + error.message;
  } finally { clearInterval(timer); byId("run").disabled = false; byId("case").disabled = false; byId("question").disabled = false; }
}
byId("case").addEventListener("change", selectCase);
byId("run").addEventListener("click", run);
new ResizeObserver(draw).observe(byId("layout"));
fetch("/api/cases").then(response => { if (!response.ok) throw new Error("Unable to load public cases"); return response.json(); }).then(data => {
  cases = data;
  for (const item of cases) { const option = text("option", `${item.case_id} | ${item.gds_path || "Scope probe"}`); option.value = item.case_id; byId("case").append(option); }
  selectCase();
}).catch(error => { byId("error").textContent = error.message; byId("run").disabled = true; });