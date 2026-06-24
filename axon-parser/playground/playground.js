import init, { parse_axon } from '../pkg/axon_parser.js';

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
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: Str) -> Str { q }
}`,

  hello_run:
`tool Greet(name: Str) -> Str {
    /// Says hello to someone.
    "Hello, {name}!"
}

agent Bot {
    model: @anthropic/claude-4
    tools: [Greet]

    fn run(q: Str) -> Str {
        act Greet(name: q)
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
    model: @anthropic/claude-4
    tools: [ProductDocs.retrieve, CreateSupportTicket]
    memory: Memory<Semantic>

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

let wasmReady = false;
let currentIR = '';

// ---------------------------------------------------------------------------
// Init WASM
// ---------------------------------------------------------------------------
async function initWasm() {
  try {
    await init();
    wasmReady = true;
    setStatus('WASM parser ready', 'success');
    parseBtn.disabled = false;
    doParse();
  } catch (e) {
    wasmReady = false;
    setStatus('WASM init failed: ' + e, 'error');
    parseBtn.disabled = true;
  }
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
// Parse
// ---------------------------------------------------------------------------
function doParse() {
  if (!wasmReady) return;
  const src = sourceEl.value.trim();
  if (!src) {
    outputEl.innerHTML = '<code class="placeholder">Type AXON source and click Parse…</code>';
    setStatus('Empty source', '');
    return;
  }
  try {
    const json = parse_axon(src);
    currentIR = json;
    outputEl.innerHTML = formatJson(json);
    setStatus('Parse succeeded', 'success');
  } catch (e) {
    currentIR = '';
    const msg = typeof e === 'string' ? e : (e.message || String(e));
    outputEl.innerHTML = `<code class="error">${escapeHtml(msg)}</code>`;
    setStatus('Parse failed', 'error');
  }
}

// ---------------------------------------------------------------------------
// JSON formatter with syntax highlighting
// ---------------------------------------------------------------------------
function formatJson(jsonStr) {
  try {
    const obj = JSON.parse(jsonStr);
    const pretty = JSON.stringify(obj, null, 2);
    return syntaxHighlightJson(pretty);
  } catch {
    return escapeHtml(jsonStr);
  }
}

function syntaxHighlightJson(json) {
  return escapeHtml(json)
    .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
    .replace(/"([^"]*)"/g, '<span class="json-string">"$1"</span>')
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
// UI helpers
// ---------------------------------------------------------------------------
function setStatus(text, cls) {
  statusText.textContent = text;
  statusText.className = cls;
}

function loadExample(key) {
  if (key === 'custom') return;
  sourceEl.value = EXAMPLES[key];
  updateLineNumbers();
  doParse();
}

function copyToClipboard() {
  if (!currentIR) return;
  navigator.clipboard.writeText(currentIR).then(() => {
    const orig = copyBtn.textContent;
    copyBtn.textContent = 'Copied!';
    setTimeout(() => copyBtn.textContent = orig, 1200);
  });
}

function downloadJson() {
  if (!currentIR) return;
  const blob = new Blob([currentIR], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'axon_ir.json';
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
});

exampleSel.addEventListener('change', () => loadExample(exampleSel.value));
parseBtn.addEventListener('click', doParse);
copyBtn.addEventListener('click', copyToClipboard);
downloadBtn.addEventListener('click', downloadJson);

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
loadExample('hello');
updateLineNumbers();
parseBtn.disabled = true;
initWasm();
