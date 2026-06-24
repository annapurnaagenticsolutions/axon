const { parse_axon, parse_expr } = require('../pkg/node/axon_parser');

function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'Assertion failed');
}

function test_basic_agent() {
  const src = `
agent Bot {
    model: @mock/gpt
    fn run(q: Str) -> Str { q }
}
`;
  const json = parse_axon(src);
  const ir = JSON.parse(json);
  assert(ir.version === '0.2.0', 'version mismatch');
  assert(ir.agents.length === 1, 'expected 1 agent');
  assert(ir.agents[0].name === 'Bot', 'agent name mismatch');
  assert(ir.agents[0].methods.length === 1, 'expected 1 method');
  assert(ir.agents[0].methods[0].name === 'run', 'method name mismatch');
  assert(ir.agents[0].methods[0].return_type === 'Str', 'return type mismatch');
  console.log('✓ test_basic_agent');
}

function test_tool_and_agent() {
  const src = `
tool Greet(name: Str) -> Str {
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(q: Str) -> Str {
        act Greet(name: q)
    }
}
`;
  const json = parse_axon(src);
  const ir = JSON.parse(json);
  assert(ir.tools.length === 1, 'expected 1 tool');
  assert(ir.tools[0].name === 'Greet', 'tool name mismatch');
  assert(ir.agents.length === 1, 'expected 1 agent');
  assert(ir.agents[0].tools.length === 1, 'expected 1 tool ref');
  console.log('✓ test_tool_and_agent');
}

function test_error() {
  try {
    parse_axon('not valid axon');
    assert(false, 'expected parse error');
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e.message || String(e));
    assert(msg.includes('Expected keyword') || msg.includes('Parse error'), 'unexpected error: ' + msg);
  }
  console.log('✓ test_error');
}

function test_expr_literal() {
  const json = parse_expr('42');
  const ast = JSON.parse(json);
  assert(ast.kind === 'literal', 'expected literal');
  assert(ast.value.int === 42, 'expected int 42');
  console.log('✓ test_expr_literal');
}

function test_expr_binary_op() {
  const json = parse_expr('1 + 2 * 3');
  const ast = JSON.parse(json);
  assert(ast.kind === 'binary_op', 'expected binary_op');
  assert(ast.op === '+', 'expected +');
  assert(ast.left.kind === 'literal', 'left should be literal');
  assert(ast.right.kind === 'binary_op', 'right should be binary_op');
  console.log('✓ test_expr_binary_op');
}

function test_expr_if() {
  const json = parse_expr('if ready { go() } else { wait() }');
  const ast = JSON.parse(json);
  assert(ast.kind === 'if', 'expected if');
  assert(ast.then_branch.kind === 'block', 'then should be block');
  assert(ast.else_branch.kind === 'block', 'else should be block');
  console.log('✓ test_expr_if');
}

function test_expr_call() {
  const json = parse_expr('greet("world")');
  const ast = JSON.parse(json);
  assert(ast.kind === 'call', 'expected call');
  assert(ast.callee.kind === 'variable', 'callee should be variable');
  assert(ast.callee.name === 'greet', 'callee name should be greet');
  assert(ast.args.length === 1, 'expected 1 arg');
  console.log('✓ test_expr_call');
}

function test_expr_error() {
  try {
    parse_expr('1 + + 2');
    assert(false, 'expected parse error');
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e.message || String(e));
    assert(msg.includes('Expression parse error'), 'unexpected error: ' + msg);
  }
  console.log('✓ test_expr_error');
}

function main() {
  test_basic_agent();
  test_tool_and_agent();
  test_error();
  test_expr_literal();
  test_expr_binary_op();
  test_expr_if();
  test_expr_call();
  test_expr_error();
  console.log('\nAll Node.js WASM tests passed!');
}

main();
