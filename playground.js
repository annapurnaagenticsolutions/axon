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
    return { error: 'Codegen requires the Python server backend. Start the playground server for code generation.' };
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
      const json = wasmModule.parse_axon(source);
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

    renderOutput();
  });
});

// ---------------------------------------------------------------------------
// Parse and render
// ---------------------------------------------------------------------------
async function doParse() {
  const src = sourceEl.value.trim();
  if (!src) {
    outputEl.innerHTML = '<code class="placeholder">Type AXON source and click Parse…</code>';
    setStatus('Empty source', '');
    return;
  }

  setStatus('Parsing…', '');
  try {
    parseResult = await apiParse(src);
    if (parseResult.error) throw new Error(parseResult.error);
    setStatus('Parse succeeded', 'success');
    renderOutput();
  } catch (e) {
    parseResult = null;
    const msg = typeof e === 'string' ? e : (e.message || String(e));
    outputEl.innerHTML = `<code class="error">${escapeHtml(msg)}</code>`;
    setStatus('Parse failed', 'error');
  }
}

async function renderOutput() {
  if (!parseResult) {
    outputEl.innerHTML = '<code class="placeholder">Nothing parsed yet.</code>';
    return;
  }

  const src = sourceEl.value.trim();

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
      outputEl.innerHTML = `<code class="code-output">${escapeHtml(result.code)}</code>`;
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
  sourceEl.value = EXAMPLES[key] || '';
  updateLineNumbers();
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
sourceEl.addEventListener('input', () => { updateLineNumbers(); });
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

evalBtn.addEventListener('click', renderOutput);
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
parseBtn.disabled = true;
initWasm();
