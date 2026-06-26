// AXON Playground — multi-tab output with WASM and server fallback
// Tries WASM first, falls back to Python server API if WASM not available.

let wasmReady = false;
let wasmModule = null;
let currentTab = 'ir';
let currentOutput = '';
let parseResult = null;

// ---------------------------------------------------------------------------
// Example sources
// ---------------------------------------------------------------------------
const EXAMPLES = {
  hello:
`tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}`,

  hello_run:
`tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}`,

  versioned:
`tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    version: "2.0.0"

    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}`,

  permissions:
`@permission(scope: "fs", access: "read")
tool ReadFile(path: Str) -> Str {
    /// Reads a file from the filesystem.
    fs.read(path)
}

@permission(scope: "network", access: "write")
tool SendWebhook(url: Str, body: Str) -> Bool {
    /// Sends an HTTP POST request to a URL.
    http.post(url, body).ok
}

agent SecureBot {
    model: @mock/gpt
    tools: [ReadFile, SendWebhook]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        let content = act ReadFile(path: "config.json")?
        act SendWebhook(url: "https://api.example.com/hook", body: content)?
        Ok("done")
    }
}`,

  type_alias:
`type Issue = {
    id: Int,
    title: Str
}

tool FetchIssues(repo: Str) -> List<Issue> {
    /// Fetches issues from a repository.
    [Issue(id: 1, title: "test")]
}

agent IssueBot {
    model: @mock/gpt
    tools: [FetchIssues]
    version: "2.0.0"

    fn run(q: Str) -> Result<Str, AgentError> {
        Ok(q)
    }
}`,

  flow:
`tool FetchData(source: Str) -> Str {
    /// Fetches raw data from a source.
    http.get(source).body
}

tool TransformData(raw: Str) -> Str {
    /// Transforms raw data into normalized format.
    raw.upper()
}

tool SaveData(data: Str, path: Str) -> Bool {
    /// Saves data to a file path.
    fs.write(path, data).ok
}

flow ETLPipeline {
    stage Fetch(source: Str) -> Str {
        act FetchData(source: source)
    }

    stage Transform(raw: Str) -> Str {
        act TransformData(raw: raw)
    }

    stage Load(data: Str, path: Str) -> Bool {
        act SaveData(data: data, path: path)
    }

    edge Fetch -> Transform
    edge Transform -> Load
}

agent PipelineBot {
    model: @mock/gpt
    tools: [FetchData, TransformData, SaveData]
    version: "1.0.0"

    fn run(q: Str) -> Str {
        flow ETLPipeline.run(source: q, path: "output.txt")
    }
}`,

  rag:
`import { Chunk } from "axon:types"

type SearchResult = {
    chunk: Chunk,
    score: Float
}

rag KnowledgeBase {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/kb.db")

    fn search(query: Str, top_k: Int = 5) -> List<SearchResult> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(r => r.score > 0.65)
    }
}

prompt Summarize(topic: Str, context: List<Chunk], @budget(tokens: 500)) -> Str {
    """
    Summarize the topic using the provided context.

    Topic: {topic}
    Context: {context}

    Provide a concise summary.
    """
}

prompt Classify(text: Str, categories: List<Str>, @budget(tokens: 200)) -> Str {
    """
    Classify the following text into one of the categories.

    Text: {text}
    Categories: {categories}

    Return only the category name.
    """
}

tool IndexDocument(path: Str) -> Bool {
    /// Indexes a document into the knowledge base.
    KnowledgeBase.ingest(fs.read(path))
}

agent ResearchBot {
    model: @mock/gpt
    tools: [KnowledgeBase.search, IndexDocument]
    memory: Memory<Semantic>
    version: "1.0.0"

    fn research(topic: Str) -> Str {
        let context = act KnowledgeBase.search(query: topic, top_k: 3)?
        let summary = model.complete(Summarize(topic, context))
        store memory.working["last_summary"] = summary
        summary
    }
}`,

  customer_support:
`import { Chunk } from "axon:types"

type SupportResponse = {
    answer: Str,
    confidence: Float,
    escalated: Bool
}

rag ProductDocs {
    source: "./knowledge_base/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./data/product_docs.db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
            |> rerank(query, model: @cohere/rerank-3)
            |> filter(chunk => chunk.score > 0.72)
    }
}

prompt AnswerFromDocs(question: Str, context: List<Chunk>, @budget(tokens: 900)) -> SupportResponse {
    """
    Answer the customer question using only the retrieved documentation.

    Question: {question}
    Context: {context}

    Return answer, confidence, and whether escalation is required.
    """
}

tool CreateSupportTicket(title: Str, description: Str, priority: "low" | "medium" | "high" = "medium") -> Result<Str, ToolError> {
    /// Creates a support ticket in the service desk.
    /// Use when documentation is missing or confidence is too low.
    http.post(env.SUPPORT_TICKET_API, { title, description, priority })
}

agent CustomerSupportAgent {
    model: @mock/gpt
    tools: [ProductDocs.retrieve, CreateSupportTicket]
    memory: Memory<Semantic>
    version: "1.5.0"

    fn handle(question: Str) -> Result<SupportResponse, AgentError> {
        let context = act ProductDocs.retrieve(query: question, top_k: 5)?
        store memory.working["last_question"] = question
        let response = model.complete(AnswerFromDocs(question, context))

        if response.escalated {
            act CreateSupportTicket(title: question, description: response.answer, priority: "medium")?
        }

        Ok(response)
    }
}`
};

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const sourceEl   = $('source');
const lineNumsEl = $('lineNumbers');
const outputEl   = $('output');
const exampleSel = $('exampleSelect');
const parseBtn   = $('parseBtn');
const copyBtn    = $('copyBtn');
const downloadBtn= $('downloadBtn');
const statusText = $('statusText');
const sourceMeta = $('sourceMeta');
const resizer    = $('resizer');
const wasmBadge  = $('wasmBadge');
const outputMeta = $('outputMeta');
const exprPanel = $('exprPanel');
const exprInput = $('exprInput');
const scopeInput = $('scopeInput');
const depthInput = $('depthInput');
const evalBtn   = $('evalBtn');
const workspace = document.querySelector('.workspace');
const astTreeEl = $('astTree');
const themeBtn  = $('themeBtn');
const shareBtn  = $('shareBtn');
const downloadAllBtn = $('downloadAllBtn');
const meshUrlInput = $('meshUrlInput');
const governPanel = $('governPanel');
const governSubmitBtn = $('governSubmitBtn');
const fileTabsEl = $('fileTabs');
const addFileBtn = $('addFileBtn');
const removeFileBtn = $('removeFileBtn');

// ---------------------------------------------------------------------------
// Multi-file support
// ---------------------------------------------------------------------------
const files = [{ name: 'main.ax', content: '' }];
let activeFileIdx = 0;

function getActiveFile() { return files[activeFileIdx]; }

function renderFileTabs() {
  fileTabsEl.innerHTML = '';
  files.forEach((f, i) => {
    const tab = document.createElement('div');
    tab.className = 'file-tab' + (i === activeFileIdx ? ' active' : '');
    tab.textContent = f.name;
    tab.addEventListener('click', () => switchToFile(i));
    fileTabsEl.appendChild(tab);
  });
}

function switchToFile(idx) {
  if (idx < 0 || idx >= files.length) return;
  // Save current editor content to the current file
  files[activeFileIdx].content = sourceEl.value;
  activeFileIdx = idx;
  sourceEl.value = files[idx].content;
  updateLineNumbers();
  renderFileTabs();
  clearErrorMarkers();
  if (debounceTimer) clearTimeout(debounceTimer);
  doParse();
}

function addFile() {
  const name = prompt('File name:', 'file' + (files.length + 1) + '.ax');
  if (!name) return;
  if (files.some(f => f.name === name)) {
    setStatus('File already exists: ' + name, 'error');
    return;
  }
  files[activeFileIdx].content = sourceEl.value;
  files.push({ name, content: '' });
  activeFileIdx = files.length - 1;
  sourceEl.value = '';
  updateLineNumbers();
  renderFileTabs();
  setStatus('Added file: ' + name, 'success');
}

function removeFile() {
  if (files.length <= 1) {
    setStatus('Cannot remove the last file', 'error');
    return;
  }
  const removed = files.splice(activeFileIdx, 1)[0];
  activeFileIdx = Math.min(activeFileIdx, files.length - 1);
  sourceEl.value = files[activeFileIdx].content;
  updateLineNumbers();
  renderFileTabs();
  setStatus('Removed file: ' + removed.name, '');
  doParse();
}

function resolveSource() {
  // Concatenate all files for parsing, resolving import directives
  // Save current editor content first
  files[activeFileIdx].content = sourceEl.value;
  // If only one file, just return it
  if (files.length === 1) return files[0].content;
  // Concatenate all files with a comment separator
  return files.map(f => '// ── ' + f.name + ' ──\n' + f.content).join('\n\n');
}

// ---------------------------------------------------------------------------
// Backend abstraction — WASM or server fallback
// ---------------------------------------------------------------------------
async function apiParse(source) {
  if (wasmReady) {
    const json = wasmModule.parse_axon(source);
    return JSON.parse(json);
  }
  const resp = await fetch('/api/parse', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source}),
  });
  return resp.json();
}

async function apiValidate(source) {
  if (wasmReady) {
    const json = wasmModule.validate_axon(source);
    return JSON.parse(json);
  }
  const resp = await fetch('/api/validate', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source}),
  });
  return resp.json();
}

async function apiCodegen(source, target) {
  if (wasmReady) {
    try {
      const code = wasmModule.codegen_axon(source, target);
      return { code };
    } catch (e) {
      return { error: typeof e === 'string' ? e : (e.message || String(e)) };
    }
  }
  const resp = await fetch('/api/codegen', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source, target}),
  });
  return resp.json();
}

async function apiAst(source) {
  if (wasmReady) {
    try {
      const json = wasmModule.ast_snapshot(source);
      return { ast: JSON.parse(json) };
    } catch (e) {
      return { error: typeof e === 'string' ? e : (e.message || String(e)) };
    }
  }
  const resp = await fetch('/api/ast', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source}),
  });
  return resp.json();
}

async function apiEvalExpr(expr, scope, maxDepth) {
  if (wasmReady) {
    try {
      const astJson = wasmModule.parse_expr(expr);
      const result = wasmModule.evaluate_expr(astJson, scope, maxDepth);
      return { result, ast: JSON.parse(astJson) };
    } catch (e) {
      return { error: typeof e === 'string' ? e : (e.message || String(e)) };
    }
  }
  const resp = await fetch('/api/eval-expr', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({expr, scope, max_depth: maxDepth}),
  });
  return resp.json();
}

async function apiGovern(source, meshUrl) {
  const resp = await fetch('/api/govern', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source, mesh_url: meshUrl}),
  });
  return resp.json();
}

// ---------------------------------------------------------------------------
// Init WASM
// ---------------------------------------------------------------------------
async function initWasm() {
  try {
    const mod = await import('./pkg/axon_parser.js');
    await mod.default();
    wasmModule = mod;
    wasmReady = true;
    wasmBadge.textContent = 'WASM';
    wasmBadge.className = 'wasm-badge ready';
    setStatus('WASM parser ready', 'success');
  } catch {
    wasmReady = false;
    wasmBadge.textContent = 'Server';
    wasmBadge.className = 'wasm-badge fallback';
    setStatus('Using Python server backend', '');
  }
  parseBtn.disabled = false;
  doParse();
}

// ---------------------------------------------------------------------------
// Line numbers
// ---------------------------------------------------------------------------
function updateLineNumbers() {
  const lines = sourceEl.value.split('\n').length;
  lineNumsEl.textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
  sourceMeta.textContent = `${lines} lines`;
}

function syncScroll() {
  lineNumsEl.scrollTop = sourceEl.scrollTop;
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentTab = tab.dataset.tab;

    if (currentTab === 'expr') {
      exprPanel.style.display = 'flex';
      workspace.classList.add('expr-mode');
    } else {
      exprPanel.style.display = 'none';
      workspace.classList.remove('expr-mode');
    }

    if (currentTab === 'govern') {
      governPanel.style.display = 'flex';
    } else {
      governPanel.style.display = 'none';
    }

    renderOutput();
  });
});

// ---------------------------------------------------------------------------
// Parse and render
// ---------------------------------------------------------------------------
async function doParse() {
  const src = resolveSource().trim();
  if (!src) {
    outputEl.innerHTML = '<code class="placeholder">Type AXON source and click Parse…</code>';
    setStatus('Empty source', '');
    return;
  }

  setStatus('Parsing…', '');
  try {
    parseResult = await apiParse(src);
    if (parseResult.error) throw new Error(parseResult.error);
    clearErrorMarkers();
    setStatus('Parse succeeded', 'success');
    renderOutput();
  } catch (e) {
    parseResult = null;
    const msg = typeof e === 'string' ? e : (e.message || String(e));
    outputEl.innerHTML = `<code class="error">${escapeHtml(msg)}</code>`;
    setStatus('Parse failed', 'error');
    const errs = parseResult && parseResult.errors ? parseResult.errors : [{ message: msg, line: 0 }];
    showErrorMarkers(errs);
  }
}

async function renderOutput() {
  if (!parseResult) {
    outputEl.innerHTML = '<code class="placeholder">Nothing parsed yet.</code>';
    return;
  }

  const src = resolveSource().trim();

  // Show/hide AST tree vs pre output
  outputEl.style.display = currentTab === 'ast' ? 'none' : 'block';
  astTreeEl.style.display = currentTab === 'ast' ? 'block' : 'none';

  if (currentTab === 'ir') {
    outputMeta.textContent = 'AxonIR v' + (parseResult.version || '0.2');
    const pretty = JSON.stringify(parseResult, null, 2);
    currentOutput = pretty;
    outputEl.innerHTML = syntaxHighlightJson(pretty);
    return;
  }

  if (currentTab === 'ast') {
    outputMeta.textContent = 'AST Tree View';
    outputEl.style.display = 'none';
    astTreeEl.style.display = 'block';
    try {
      const result = await apiAst(src);
      if (result.error) throw new Error(result.error);
      currentOutput = JSON.stringify(result.ast, null, 2);
      astTreeEl.innerHTML = renderAstTree(result.ast);
      setStatus('AST rendered', 'success');
    } catch (e) {
      astTreeEl.innerHTML = `<code class="error">${escapeHtml(e.message || String(e))}</code>`;
      setStatus('AST failed', 'error');
    }
    return;
  }

  if (currentTab === 'validate') {
    outputMeta.textContent = 'Diagnostics';
    try {
      const result = await apiValidate(src);
      currentOutput = JSON.stringify(result, null, 2);
      outputEl.innerHTML = renderDiagnostics(result);
    } catch (e) {
      outputEl.innerHTML = `<code class="error">${escapeHtml(e.message || String(e))}</code>`;
    }
    return;
  }

  if (currentTab === 'go' || currentTab === 'rust' || currentTab === 'ts' || currentTab === 'mcp') {
    const targetMap = { ts: 'typescript', mcp: 'mcp', go: 'go', rust: 'rust' };
    const target = targetMap[currentTab] || currentTab;
    const label = currentTab === 'mcp' ? 'MCP Server' : target.toUpperCase() + ' Codegen';
    outputMeta.textContent = label;
    try {
      const result = await apiCodegen(src, target);
      if (result.error) throw new Error(result.error);
      currentOutput = result.code;
      outputEl.innerHTML = `<code class="code-output">${highlightCode(result.code, currentTab)}</code>`;
    } catch (e) {
      outputEl.innerHTML = `<code class="error">${escapeHtml(e.message || String(e))}</code>`;
    }
    return;
  }

  if (currentTab === 'expr') {
    outputMeta.textContent = 'Expression Evaluator';
    const expr = exprInput.value.trim();
    if (!expr) {
      outputEl.innerHTML = '<code class="placeholder">Type an expression below and click Evaluate…</code>';
      return;
    }
    const scope = scopeInput.value.trim() || '{}';
    const depth = parseInt(depthInput.value) || 100;
    try {
      const result = await apiEvalExpr(expr, scope, depth);
      if (result.error) throw new Error(result.error);
      const pretty = JSON.stringify(result, null, 2);
      currentOutput = pretty;
      outputEl.innerHTML = syntaxHighlightJson(pretty);
      setStatus('Evaluation succeeded', 'success');
    } catch (e) {
      outputEl.innerHTML = `<code class="error">${escapeHtml(e.message || String(e))}</code>`;
      setStatus('Evaluation failed', 'error');
    }
    return;
  }

  if (currentTab === 'govern') {
    outputMeta.textContent = 'AgentOps Mesh Governance';
    const src = resolveSource().trim();
    if (!src) {
      outputEl.innerHTML = '<code class="placeholder">Type AXON source, then click Submit to Governance…</code>';
      return;
    }
    outputEl.innerHTML = '<code class="placeholder">Click <strong>Submit to Governance</strong> to compile and submit to AgentOps Mesh…</code>';
    return;
  }
}

// ---------------------------------------------------------------------------
// Diagnostics rendering
// ---------------------------------------------------------------------------
function renderDiagnostics(result) {
  if (!result) return '<code class="placeholder">No diagnostics.</code>';

  // Handle both WASM format (array) and server format ({diagnostics, error_count, warning_count})
  const diags = Array.isArray(result) ? result : (result.diagnostics || []);
  const errors = diags.filter(d => d.severity === 'error').length;
  const warnings = diags.filter(d => d.severity === 'warning').length;

  let html = '<div class="diag-summary">';
  if (errors > 0) html += `<span class="fail">${errors} error(s)</span> `;
  if (warnings > 0) html += `<span class="warn">${warnings} warning(s)</span> `;
  if (errors === 0 && warnings === 0) html += '<span class="pass">✓ No issues found</span>';
  html += '</div>';

  for (const d of diags) {
    html += '<div class="diag-item">';
    html += `<span class="diag-severity ${d.severity}">${d.severity}</span>`;
    html += `<span class="diag-message">${escapeHtml(d.message)}</span>`;
    if (d.line) html += `<span class="diag-line">line ${d.line}</span>`;
    if (d.code) html += ` <span class="diag-code">[${d.code}]</span>`;
    html += '</div>';
  }

  if (diags.length === 0) {
    html += '<code class="placeholder">All checks passed — no diagnostics.</code>';
  }

  return html;
}

// ---------------------------------------------------------------------------
// Governance submission and rendering
// ---------------------------------------------------------------------------
async function submitGovernance() {
  const src = resolveSource().trim();
  if (!src) {
    outputEl.innerHTML = '<code class="placeholder">Type AXON source first…</code>';
    setStatus('Empty source', '');
    return;
  }
  const meshUrl = meshUrlInput.value.trim();
  setStatus('Compiling governance submission…', '');
  outputEl.innerHTML = '<code class="placeholder">Submitting to AgentOps Mesh…</code>';
  try {
    const result = await apiGovern(src, meshUrl);
    if (result.error) throw new Error(result.error);
    currentOutput = JSON.stringify(result, null, 2);
    outputEl.innerHTML = renderGovernResult(result);
    if (result.governance_response) {
      setStatus('Governance decision received', 'success');
    } else {
      setStatus('Governance submission generated (no Mesh URL set)', 'success');
    }
  } catch (e) {
    outputEl.innerHTML = `<code class="error">${escapeHtml(e.message || String(e))}</code>`;
    setStatus('Governance submission failed', 'error');
  }
}

function renderGovernResult(result) {
  let html = '';

  if (result.governance_response) {
    const gov = result.governance_response;
    const decision = gov.overall_decision || 'unknown';
    const decisionClass = decision.includes('production') ? 'pass' :
                          decision.includes('pilot') ? 'warn' :
                          decision.includes('blocked') ? 'fail' : 'warn';
    const readiness = gov.readiness_score != null ? gov.readiness_score.toFixed(1) : '—';
    const riskLevel = gov.risk_level || '—';

    html += '<div class="govern-summary">';
    html += `<div class="govern-decision ${decisionClass}">`;
    html += `<span class="govern-decision-label">Decision</span>`;
    html += `<span class="govern-decision-value">${escapeHtml(decision)}</span>`;
    html += `</div>`;
    html += `<div class="govern-metric"><span>Readiness</span><strong>${readiness}</strong></div>`;
    html += `<div class="govern-metric"><span>Risk</span><strong>${escapeHtml(riskLevel)}</strong></div>`;
    html += `<div class="govern-metric"><span>Domain</span><strong>${escapeHtml(gov.domain || '—')}</strong></div>`;
    html += `<div class="govern-metric"><span>Stage</span><strong>${escapeHtml(gov.current_stage || '—')}</strong></div>`;
    html += '</div>';

    if (gov.gate_results && gov.gate_results.length > 0) {
      html += '<div class="govern-gates">';
      html += '<h3>Governance Gates (9)</h3>';
      for (const gate of gov.gate_results) {
        const status = gate.status || 'unknown';
        const statusClass = status === 'pass' ? 'pass' : status === 'caution' ? 'warn' : 'fail';
        html += '<div class="govern-gate">';
        html += `<div class="gate-header">`;
        html += `<span class="gate-id">${escapeHtml(gate.gate_id)}</span>`;
        html += `<span class="gate-name">${escapeHtml(gate.gate_name)}</span>`;
        html += `<span class="gate-status ${statusClass}">${escapeHtml(status)}</span>`;
        html += `<span class="gate-score">${gate.score.toFixed(1)}</span>`;
        html += `</div>`;
        if (gate.reasons && gate.reasons.length > 0) {
          html += '<div class="gate-reasons">';
          for (const r of gate.reasons) {
            html += `<div class="gate-reason">${escapeHtml(r)}</div>`;
          }
          html += '</div>';
        }
        if (gate.recommendations && gate.recommendations.length > 0) {
          html += '<div class="gate-recs">';
          for (const r of gate.recommendations) {
            html += `<div class="gate-rec">→ ${escapeHtml(r)}</div>`;
          }
          html += '</div>';
        }
        html += '</div>';
      }
      html += '</div>';
    }

    if (gov.required_controls && gov.required_controls.length > 0) {
      html += '<div class="govern-controls">';
      html += '<h3>Required Controls</h3>';
      html += '<ul>';
      for (const c of gov.required_controls) {
        html += `<li>${escapeHtml(c)}</li>`;
      }
      html += '</ul>';
      html += '</div>';
    }

    if (gov.next_actions && gov.next_actions.length > 0) {
      html += '<div class="govern-actions">';
      html += '<h3>Next Actions</h3>';
      html += '<ul>';
      for (const a of gov.next_actions) {
        html += `<li>${escapeHtml(a)}</li>`;
      }
      html += '</ul>';
      html += '</div>';
    }

    if (gov.production_readiness_report) {
      const pr = gov.production_readiness_report;
      html += '<div class="govern-readiness">';
      html += '<h3>Production Readiness</h3>';
      html += `<p>${escapeHtml(pr.summary || '')}</p>`;
      html += `<div class="readiness-flags">`;
      html += `<span class="${pr.pilot_ready ? 'pass' : 'fail'}">Pilot: ${pr.pilot_ready ? 'Ready' : 'Not Ready'}</span>`;
      html += `<span class="${pr.production_ready ? 'pass' : 'fail'}">Production: ${pr.production_ready ? 'Ready' : 'Not Ready'}</span>`;
      html += `</div>`;
      html += '</div>';
    }
  } else if (result.submission) {
    html += '<div class="govern-submission-only">';
    html += '<p class="placeholder">Governance submission generated. Set Mesh URL to submit.</p>';
    html += '<div class="govern-submission-meta">';
    html += `<span>Use Case: <strong>${escapeHtml(result.submission.use_case_id || '—')}</strong></span>`;
    html += `<span>Domain: <strong>${escapeHtml(result.submission.domain || '—')}</strong></span>`;
    html += `<span>Autonomy: <strong>${result.submission.autonomy_level || '—'}</strong></span>`;
    html += '</div>';
    html += '</div>';
  }

  html += '<details class="govern-raw"><summary>Raw JSON</summary>';
  html += `<pre class="json-view">${syntaxHighlightJson(currentOutput)}</pre>`;
  html += '</details>';

  return html;
}

// ---------------------------------------------------------------------------
// JSON formatter with syntax highlighting
// ---------------------------------------------------------------------------
function syntaxHighlightJson(jsonStr) {
  return escapeHtml(jsonStr)
    .replace(/&quot;([^&]+)&quot;:/g, '<span class="json-key">"$1"</span>:')
    .replace(/&quot;([^&]*)&quot;/g, '<span class="json-string">"$1"</span>')
    .replace(/\b(true|false)\b/g, '<span class="json-bool">$1</span>')
    .replace(/\bnull\b/g, '<span class="json-null">$1</span>')
    .replace(/(-?\d+\.?\d*)/g, '<span class="json-number">$1</span>')
    .replace(/([{}[\]])/g, '<span class="json-brace">$1</span>');
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function highlightCode(code, lang) {
  let html = escapeHtml(code);
  const kw = {
    go: /\b(package|import|func|type|struct|return|var|const|if|else|for|range|map|chan|go|defer|interface|nil|true|false)\b/g,
    rust: /\b(pub|fn|struct|enum|impl|use|let|mut|return|if|else|match|for|while|loop|trait|type|self|Self|Option|Result|Some|None|Ok|Err|true|false|mod|const|static|where|async|await|move)\b/g,
    ts: /\b(export|import|from|interface|type|class|extends|implements|return|if|else|for|while|switch|case|break|const|let|var|async|await|new|this|null|undefined|true|false|void|number|string|boolean|any|Promise)\b/g,
    mcp: /\b(from|import|def|class|return|if|else|elif|for|while|try|except|finally|with|as|async|await|yield|lambda|None|True|False|self|raise|pass|in|not|and|or|is)\b/g,
  };
  const re = kw[lang] || kw.mcp;
  html = html.replace(re, '<span class="code-keyword">$1</span>');
  html = html.replace(/(\/\/[^\n]*)/g, '<span class="code-comment">$1</span>');
  html = html.replace(/(#[^\n]*)/g, lang === 'mcp' ? '<span class="code-comment">$1</span>' : '$1');
  html = html.replace(/("(?:[^"\\]|\\.)*")/g, '<span class="code-string">$1</span>');
  html = html.replace(/(\b[A-Z][A-Za-z0-9_]*\b)/g, '<span class="code-type">$1</span>');
  return html;
}

// ---------------------------------------------------------------------------
// AST tree view renderer
// ---------------------------------------------------------------------------
function renderAstTree(ast) {
  if (!ast) return '<code class="placeholder">No AST data.</code>';
  const nodes = Array.isArray(ast) ? ast : [ast];
  let html = '<ul>';
  for (const node of nodes) {
    html += renderAstNode(node, 'root');
  }
  html += '</ul>';
  return html;
}

function renderAstNode(node, label) {
  if (node === null || node === undefined) {
    return `<li><span class="ast-leaf">${label}: null</span></li>`;
  }
  if (typeof node !== 'object') {
    return `<li><span class="ast-leaf">${escapeHtml(String(label))}:</span> <span class="ast-node-value">${escapeHtml(String(node))}</span></li>`;
  }

  const type = node.kind || node.type || node.__class__ || 'object';
  const name = node.name || '';
  const hasChildren = Object.keys(node).length > 0;

  let html = `<li class="${hasChildren ? '' : 'ast-leaf'}">`;
  if (hasChildren) {
    html += `<span class="ast-toggle" onclick="this.parentElement.classList.toggle('collapsed')">▼</span>`;
  }
  html += `<span class="ast-node-type">${escapeHtml(type)}</span>`;
  if (name) html += `<span class="ast-node-name">${escapeHtml(name)}</span>`;

  if (hasChildren) {
    html += '<ul>';
    for (const [key, val] of Object.entries(node)) {
      if (key === 'kind' || key === 'type' || key === '__class__' || key === 'name') continue;
      if (Array.isArray(val)) {
        html += `<li><span class="ast-toggle" onclick="this.parentElement.classList.toggle('collapsed')">▼</span><span class="ast-node-type">${escapeHtml(key)}</span> [${val.length}]<ul>`;
        for (const item of val) {
          html += renderAstNode(item, key);
        }
        html += '</ul></li>';
      } else {
        html += renderAstNode(val, key);
      }
    }
    html += '</ul>';
  }

  html += '</li>';
  return html;
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------
function setStatus(text, cls) {
  statusText.textContent = text;
  statusText.className = cls;
}

function loadExample(key) {
  if (key === 'custom') return;
  // Reset to single file when loading an example
  files.length = 0;
  files.push({ name: 'main.ax', content: EXAMPLES[key] || '' });
  activeFileIdx = 0;
  sourceEl.value = files[0].content;
  updateLineNumbers();
  renderFileTabs();
  doParse();
}

function copyToClipboard() {
  if (!currentOutput) return;
  navigator.clipboard.writeText(currentOutput).then(() => {
    const orig = copyBtn.textContent;
    copyBtn.textContent = 'Copied!';
    setTimeout(() => copyBtn.textContent = orig, 1200);
  });
}

function downloadJson() {
  if (!currentOutput) return;
  const extMap = { ir: 'json', ast: 'json', validate: 'json', ts: 'ts', go: 'go', rust: 'rs', mcp: 'py', expr: 'json' };
  const ext = extMap[currentTab] || 'txt';
  const mime = ext === 'json' ? 'application/json' : 'text/plain';
  const blob = new Blob([currentOutput], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `axon_output.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadAllZip() {
  const src = resolveSource().trim();
  if (!src) { setStatus('Nothing to export', 'error'); return; }
  setStatus('Generating all targets…', '');
  // Save current editor content
  files[activeFileIdx].content = sourceEl.value;
  const sourceFiles = files.map(f => ({ name: f.name, content: f.content }));
  const targets = [
    ...sourceFiles,
    { name: 'ir.json', getContent: async () => { const r = await apiParse(src); return r.error ? `// ${r.error}` : JSON.stringify(r, null, 2); } },
    { name: 'generated.go', getContent: async () => { const r = await apiCodegen(src, 'go'); return r.error ? `// ${r.error}` : r.code; } },
    { name: 'generated.rs', getContent: async () => { const r = await apiCodegen(src, 'rust'); return r.error ? `// ${r.error}` : r.code; } },
    { name: 'generated.ts', getContent: async () => { const r = await apiCodegen(src, 'typescript'); return r.error ? `// ${r.error}` : r.code; } },
    { name: 'generated_mcp.py', getContent: async () => { const r = await apiCodegen(src, 'mcp'); return r.error ? `// ${r.error}` : r.code; } },
  ];
  const zipFiles = [];
  for (const t of targets) {
    const content = t.getContent ? await t.getContent() : t.content;
    zipFiles.push({ name: t.name, content });
  }
  const zip = createZip(zipFiles);
  const blob = new Blob([zip], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'axon_project.zip';
  a.click();
  URL.revokeObjectURL(url);
  setStatus('Project ZIP downloaded', 'success');
}

function createZip(files) {
  const encoder = new TextEncoder();
  const chunks = [];
  const centralDir = [];
  let offset = 0;
  for (const file of files) {
    const nameBytes = encoder.encode(file.name);
    const contentBytes = encoder.encode(file.content);
    const crc = crc32(contentBytes);
    const localHeader = new Uint8Array(30 + nameBytes.length);
    const dv = new DataView(localHeader.buffer);
    dv.setUint32(0, 0x04034b50, true);
    dv.setUint16(4, 20, true);
    dv.setUint16(6, 0, true);
    dv.setUint16(8, 0, true);
    dv.setUint16(10, 0, true);
    dv.setUint32(12, crc, true);
    dv.setUint32(16, contentBytes.length, true);
    dv.setUint32(20, contentBytes.length, true);
    dv.setUint16(24, nameBytes.length, true);
    dv.setUint16(26, 0, true);
    localHeader.set(nameBytes, 30);
    chunks.push(localHeader);
    chunks.push(contentBytes);
    const cdEntry = new Uint8Array(46 + nameBytes.length);
    const cdv = new DataView(cdEntry.buffer);
    cdv.setUint32(0, 0x02014b50, true);
    cdv.setUint16(4, 20, true);
    cdv.setUint16(6, 20, true);
    cdv.setUint16(8, 0, true);
    cdv.setUint16(10, 0, true);
    cdv.setUint16(12, 0, true);
    cdv.setUint32(14, crc, true);
    cdv.setUint32(18, contentBytes.length, true);
    cdv.setUint32(22, contentBytes.length, true);
    cdv.setUint16(26, nameBytes.length, true);
    cdv.setUint16(28, 0, true);
    cdv.setUint16(30, 0, true);
    cdv.setUint16(32, 0, true);
    cdv.setUint16(34, 0, true);
    cdv.setUint32(36, 0, true);
    cdv.setUint32(42, offset, true);
    cdEntry.set(nameBytes, 46);
    centralDir.push(cdEntry);
    offset += localHeader.length + contentBytes.length;
  }
  const cdOffset = offset;
  let cdSize = 0;
  for (const cd of centralDir) { chunks.push(cd); cdSize += cd.length; }
  const endRecord = new Uint8Array(22);
  const ev = new DataView(endRecord.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(4, 0, true);
  ev.setUint16(6, 0, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true);
  ev.setUint32(16, cdOffset, true);
  ev.setUint16(20, 0, true);
  chunks.push(endRecord);
  let total = 0;
  for (const c of chunks) total += c.length;
  const result = new Uint8Array(total);
  let pos = 0;
  for (const c of chunks) { result.set(c, pos); pos += c.length; }
  return result;
}

function crc32(bytes) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) {
    crc ^= bytes[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

// ---------------------------------------------------------------------------
// Error markers (inline highlight in source editor)
// ---------------------------------------------------------------------------
function clearErrorMarkers() {
  const existing = document.querySelectorAll('.error-marker');
  existing.forEach(el => el.remove());
}

function showErrorMarkers(errors) {
  clearErrorMarkers();
  if (!errors || !errors.length) return;
  const lines = sourceEl.value.split('\n');
  const lineHeight = 20;
  for (const err of errors) {
    const lineNum = err.line || err.lineno || (err.location && err.location.line) || 0;
    if (lineNum < 1 || lineNum > lines.length) continue;
    const marker = document.createElement('div');
    marker.className = 'error-marker';
    marker.style.top = ((lineNum - 1) * lineHeight + 8) + 'px';
    marker.title = err.message || err.msg || String(err);
    marker.textContent = '⚠ ' + (err.message || err.msg || '').slice(0, 60);
    document.querySelector('.editor-wrap').appendChild(marker);
  }
}

// ---------------------------------------------------------------------------
// Resizer
// ---------------------------------------------------------------------------
let isResizing = false;

resizer.addEventListener('mousedown', (e) => {
  isResizing = true;
  resizer.classList.add('dragging');
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', (e) => {
  if (!isResizing) return;
  const workspace = document.querySelector('.workspace');
  const rect = workspace.getBoundingClientRect();
  const pct = ((e.clientX - rect.left) / rect.width) * 100;
  const clamped = Math.min(Math.max(pct, 15), 85);
  document.querySelector('.source-panel').style.flex = `0 0 ${clamped}%`;
  document.querySelector('.output-panel').style.flex = `0 0 ${100 - clamped}%`;
});

document.addEventListener('mouseup', () => {
  if (isResizing) {
    isResizing = false;
    resizer.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
});

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
let debounceTimer = null;
sourceEl.addEventListener('input', () => {
  updateLineNumbers();
  clearErrorMarkers();
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => { doParse(); }, 500);
});
sourceEl.addEventListener('scroll', syncScroll);
sourceEl.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = sourceEl.selectionStart;
    const end = sourceEl.selectionEnd;
    sourceEl.value = sourceEl.value.substring(0, start) + '    ' + sourceEl.value.substring(end);
    sourceEl.selectionStart = sourceEl.selectionEnd = start + 4;
    updateLineNumbers();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    doParse();
  }
});

exampleSel.addEventListener('change', () => loadExample(exampleSel.value));
parseBtn.addEventListener('click', doParse);
copyBtn.addEventListener('click', copyToClipboard);
downloadBtn.addEventListener('click', downloadJson);
downloadAllBtn.addEventListener('click', downloadAllZip);
addFileBtn.addEventListener('click', addFile);
removeFileBtn.addEventListener('click', removeFile);

evalBtn.addEventListener('click', renderOutput);
governSubmitBtn.addEventListener('click', submitGovernance);
exprInput.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    renderOutput();
  }
});
scopeInput.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    renderOutput();
  }
});

document.querySelectorAll('.expr-example-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    exprInput.value = btn.dataset.expr;
    if (btn.dataset.scope) {
      scopeInput.value = btn.dataset.scope;
    } else {
      scopeInput.value = '{}';
    }
    renderOutput();
  });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
loadExample('hello');
updateLineNumbers();
renderFileTabs();
parseBtn.disabled = true;
initWasm();

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------
(function initTheme() {
  const saved = localStorage.getItem('axon-theme');
  if (saved === 'light') {
    document.documentElement.classList.add('light');
    themeBtn.textContent = '\u{2600}';
  }
})();

themeBtn.addEventListener('click', () => {
  const isLight = document.documentElement.classList.toggle('light');
  themeBtn.textContent = isLight ? '\u{2600}' : '\u{1F319}';
  localStorage.setItem('axon-theme', isLight ? 'light' : 'dark');
});

// ---------------------------------------------------------------------------
// Shareable URL (encode source in hash fragment)
// ---------------------------------------------------------------------------
shareBtn.addEventListener('click', () => {
  const src = resolveSource().trim();
  if (!src) { setStatus('Nothing to share', 'error'); return; }
  const hash = '#s=' + btoa(unescape(encodeURIComponent(src)));
  const url = location.origin + location.pathname + hash;
  navigator.clipboard.writeText(url).then(() => {
    const orig = shareBtn.textContent;
    shareBtn.textContent = 'Copied!';
    setTimeout(() => shareBtn.textContent = orig, 1200);
    setStatus('Share URL copied to clipboard', 'success');
  }).catch(() => setStatus('Failed to copy URL', 'error'));
});

// Load from hash if present
(function loadFromHash() {
  if (location.hash.startsWith('#s=')) {
    try {
      const encoded = location.hash.slice(3);
      const src = decodeURIComponent(escape(atob(encoded)));
      files[0].content = src;
      sourceEl.value = src;
      exampleSel.value = 'custom';
      updateLineNumbers();
      renderFileTabs();
    } catch (e) {
      console.warn('Failed to load from hash:', e);
    }
  }
})();
