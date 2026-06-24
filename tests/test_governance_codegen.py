"""Tests for AXON → AgentOps Mesh governance codegen bridge."""

import json
import pytest
from pathlib import Path

from axon.parser import parse
from axon.validator import validate
from axon.codegen.governance import generate_governance_submission


# Minimal agent for testing
SIMPLE_AGENT = """
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}

agent Bot {
    model: @mock/model
    tools: [Greet]

    fn run(q: Str) -> Result<Str, AgentError> {
        let result = act Greet(name: q)?
        Ok(result)
    }
}
"""

# Agent with RAG and external tools
RESEARCH_AGENT = """
tool WebSearch(query: Str, max_results: Int = 5) -> Result<List<Any>, ToolError> {
    /// Searches the web.
    http.get("https://example.search?q={query}")
}

rag ResearchDocs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::postgres(env.PGVECTOR_URL)

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}

agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [WebSearch, ResearchDocs.retrieve]
    memory: Memory<ShortTerm>(capacity: 500)

    fn run(topic: Str) -> Result<Str, AgentError> {
        let results = act WebSearch(query: topic)?
        store memory.working["results"] = results
        Ok("done")
    }
}
"""

# Agent with financial tools
FINANCE_AGENT = """
tool ProcessRefund(amount: Float, account: Str) -> Result<Str, ToolError> {
    /// Processes a customer refund.
    "Refund processed for {account}"
}

tool SendEmail(to: Str, body: Str) -> Result<Str, ToolError> {
    /// Sends an email notification.
    "Email sent to {to}"
}

agent RefundAgent {
    model: @openai/gpt-4
    tools: [ProcessRefund, SendEmail]
    memory: Memory<Semantic>(capacity: 1000)

    fn run(request: Str) -> Result<Str, AgentError> {
        let result = act ProcessRefund(amount: 100.0, account: "ACC-001")?
        let email = act SendEmail(to: "user@example.com", body: "Refund processed")?
        Ok(result)
    }
}
"""


def _parse_and_validate(source: str):
    declarations = parse(source)
    diagnostics = validate(declarations)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert not errors, f"Validation errors: {errors}"
    return declarations


class TestGovernanceSubmissionBasic:
    """Test basic governance submission generation."""

    def test_generates_valid_json(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations, source_filename="test.ax")
        # Should be JSON-serializable
        json_str = json.dumps(submission, indent=2)
        assert isinstance(json_str, str)

    def test_required_fields_present(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations, source_filename="test.ax")
        required = {"use_case_id", "name", "domain", "business_owner", "technical_owner",
                    "autonomy_level", "risk_factors", "scores"}
        assert required.issubset(submission.keys()), f"Missing: {required - submission.keys()}"

    def test_use_case_id_derived_from_agent_name(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["use_case_id"] == "AXON-BOT"

    def test_name_matches_agent(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["name"] == "Bot"

    def test_default_owners_are_tbd(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["business_owner"] == "TBD"
        assert submission["technical_owner"] == "TBD"

    def test_owners_overridable(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(
            declarations, business_owner="Alice", technical_owner="Bob"
        )
        assert submission["business_owner"] == "Alice"
        assert submission["technical_owner"] == "Bob"

    def test_default_target_environment_sandbox(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["target_environment"] == "sandbox"

    def test_axon_metadata_present(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations, source_filename="hello.ax")
        assert "_axon_metadata" in submission
        assert submission["_axon_metadata"]["source_file"] == "hello.ax"
        assert submission["_axon_metadata"]["model"] == "@mock/model"


class TestGovernanceRiskInference:
    """Test risk factor inference from agent tools."""

    def test_simple_agent_low_risk(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        rf = submission["risk_factors"]
        assert rf["external_action"] is False
        assert rf["financial_impact"] == "none"
        assert rf["reversibility"] == "easy"

    def test_research_agent_external_action(self):
        declarations = _parse_and_validate(RESEARCH_AGENT)
        submission = generate_governance_submission(declarations)
        rf = submission["risk_factors"]
        assert rf["external_action"] is True  # http.get in tool body

    def test_finance_agent_high_financial_impact(self):
        declarations = _parse_and_validate(FINANCE_AGENT)
        submission = generate_governance_submission(declarations)
        rf = submission["risk_factors"]
        assert rf["financial_impact"] == "high"
        assert rf["reversibility"] == "hard"

    def test_finance_agent_external_action(self):
        declarations = _parse_and_validate(FINANCE_AGENT)
        submission = generate_governance_submission(declarations)
        rf = submission["risk_factors"]
        assert rf["external_action"] is True

    def test_rag_agent_high_data_sensitivity(self):
        declarations = _parse_and_validate(RESEARCH_AGENT)
        submission = generate_governance_submission(declarations)
        rf = submission["risk_factors"]
        assert rf["data_sensitivity"] == "high"  # RAG + external action


class TestGovernanceAutonomyInference:
    """Test autonomy level inference."""

    def test_simple_agent_low_autonomy(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["autonomy_level"] <= 2

    def test_finance_agent_higher_autonomy(self):
        declarations = _parse_and_validate(FINANCE_AGENT)
        submission = generate_governance_submission(declarations)
        # Has memory (+1), has send/write tools (+1), has approve/payment (+1)
        assert submission["autonomy_level"] >= 3

    def test_autonomy_max_five(self):
        declarations = _parse_and_validate(FINANCE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["autonomy_level"] <= 5


class TestGovernanceScores:
    """Test governance score inference."""

    def test_all_scores_in_range(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        for key, val in submission["scores"].items():
            assert 0 <= val <= 100, f"{key}={val} out of range"

    def test_research_agent_better_data_readiness(self):
        simple_decls = _parse_and_validate(SIMPLE_AGENT)
        research_decls = _parse_and_validate(RESEARCH_AGENT)
        simple_sub = generate_governance_submission(simple_decls)
        research_sub = generate_governance_submission(research_decls)
        assert research_sub["scores"]["data_readiness"] > simple_sub["scores"]["data_readiness"]

    def test_open_architecture_fit_high(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["scores"]["open_architecture_fit"] >= 80


class TestGovernanceDomainInference:
    """Test domain inference from agent tools."""

    def test_research_agent_domain(self):
        declarations = _parse_and_validate(RESEARCH_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["domain"] == "Research"

    def test_finance_agent_domain(self):
        declarations = _parse_and_validate(FINANCE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["domain"] == "Finance"

    def test_simple_agent_general_domain(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations)
        assert submission["domain"] == "General"


class TestGovernanceArtifacts:
    """Test submitted_artifacts list."""

    def test_simple_agent_artifacts(self):
        declarations = _parse_and_validate(SIMPLE_AGENT)
        submission = generate_governance_submission(declarations, source_filename="hello.ax")
        artifacts = submission["submitted_artifacts"]
        assert "axon_source_file" in artifacts
        assert "hello.ax" in artifacts
        assert "tool_inventory" in artifacts

    def test_research_agent_has_data_inventory(self):
        declarations = _parse_and_validate(RESEARCH_AGENT)
        submission = generate_governance_submission(declarations)
        assert "data_inventory" in submission["submitted_artifacts"]

    def test_agent_with_memory_has_memory_spec(self):
        declarations = _parse_and_validate(RESEARCH_AGENT)
        submission = generate_governance_submission(declarations)
        assert "memory_specification" in submission["submitted_artifacts"]


class TestGovernanceNoAgent:
    """Test error handling when no agent is present."""

    def test_raises_on_no_agent(self):
        source = """
tool Foo(x: Int) -> Int {
    /// Returns x.
    x
}
"""
        declarations = parse(source)
        with pytest.raises(ValueError, match="No agent declaration"):
            generate_governance_submission(declarations)


class TestGovernanceExampleFile:
    """Test governance compilation on a real example file."""

    def test_research_pipeline_compiles(self):
        example_path = Path(__file__).resolve().parent.parent / "examples" / "research_pipeline.ax"
        if not example_path.exists():
            pytest.skip("research_pipeline.ax not found")
        source = example_path.read_text(encoding="utf-8")
        # Strip only file-level /// comments (before the first declaration)
        lines = source.splitlines()
        first_decl = None
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("///"):
                continue
            if any(stripped_line.startswith(kw) for kw in
                   ("import", "type", "tool", "agent", "rag", "flow", "//")):
                first_decl = i
                break
        if first_decl is not None:
            stripped = "\n".join(lines[first_decl:])
        else:
            stripped = source
        declarations = parse(stripped)
        diagnostics = validate(declarations)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert not errors
        submission = generate_governance_submission(declarations, source_filename="research_pipeline.ax")
        # First agent in file is QueryPlanner
        assert submission["name"] == "QueryPlanner"
        assert submission["domain"] == "Research"
        assert submission["autonomy_level"] >= 1
