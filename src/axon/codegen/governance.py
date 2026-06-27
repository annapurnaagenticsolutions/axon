"""AgentOps Mesh governance submission generator for AXON.

Compiles AXON declarations into a GovernanceWorkflowRequest JSON object
compatible with AgentOps Mesh's /governance/run endpoint.

This is the integration bridge between AXON (how you write agents) and
AgentOps Mesh (how you govern agents). The pipeline:

    .ax file → parse → validate → generate governance submission JSON
    → submit to AgentOps Mesh /governance/run → 9-gate governance workflow
"""

from __future__ import annotations

import json
import re
from typing import Any

from axon.ast_nodes import AgentDecl, FlowDecl, RagDecl, ToolDecl, TypeAliasDecl


def generate_governance_submission(
    declarations: list,
    source_filename: str = "",
    business_owner: str = "TBD",
    technical_owner: str = "TBD",
    target_environment: str = "sandbox",
) -> dict[str, Any]:
    """Generate an AgentOps Mesh GovernanceWorkflowRequest from AXON declarations.

    Args:
        declarations: output of parse() from parser.py
        source_filename: the .ax source file name (used for artifact tracking)
        business_owner: business owner name (overrideable)
        technical_owner: technical owner name (overrideable)
        target_environment: sandbox, pilot, or production

    Returns:
        A dict matching the AgentOps Mesh GovernanceWorkflowRequest schema.
    """
    agents = [d for d in declarations if isinstance(d, AgentDecl)]
    tools = [d for d in declarations if isinstance(d, ToolDecl)]
    rags = [d for d in declarations if isinstance(d, RagDecl)]
    flows = [d for d in declarations if isinstance(d, FlowDecl)]
    types = [d for d in declarations if isinstance(d, TypeAliasDecl)]

    agent = agents[0] if agents else None

    if agent is None:
        raise ValueError(
            "No agent declaration found. Governance submissions require at least one agent."
        )

    use_case_id = _derive_use_case_id(agent.name)
    name = agent.name
    domain = _infer_domain(agent, tools)
    description = _build_description(agent, tools, rags, flows)
    autonomy_level = _infer_autonomy(agent, tools)
    risk_factors = _infer_risk_factors(agent, tools)
    scores = _infer_scores(agent, tools, rags, flows, types)
    submitted_artifacts = _build_artifacts(source_filename, agent, tools, rags, flows)

    # Override with @governance annotation values if present
    gov_annotation = _extract_governance_annotation(agent)
    if gov_annotation:
        if "autonomy" in gov_annotation:
            try:
                autonomy_level = int(gov_annotation["autonomy"])
            except (ValueError, TypeError):
                pass
        if "risk" in gov_annotation:
            risk_factors = _override_risk(risk_factors, gov_annotation["risk"])
        if "domain" in gov_annotation:
            domain = gov_annotation["domain"].strip('"').strip("'")
        if "artifacts" in gov_annotation:
            extra_artifacts = _parse_artifact_list(gov_annotation["artifacts"])
            for a in extra_artifacts:
                if a not in submitted_artifacts:
                    submitted_artifacts.append(a)
        if "business_owner" in gov_annotation:
            business_owner = gov_annotation["business_owner"].strip('"').strip("'")
        if "technical_owner" in gov_annotation:
            technical_owner = gov_annotation["technical_owner"].strip('"').strip("'")
        if "target_environment" in gov_annotation:
            target_environment = gov_annotation["target_environment"].strip('"').strip("'")
        if "description" in gov_annotation:
            description = gov_annotation["description"].strip('"').strip("'")

    return {
        "use_case_id": use_case_id,
        "name": name,
        "domain": domain,
        "description": description,
        "business_owner": business_owner,
        "technical_owner": technical_owner,
        "target_environment": target_environment,
        "autonomy_level": autonomy_level,
        "submitted_artifacts": submitted_artifacts,
        "risk_factors": risk_factors,
        "scores": scores,
        "_axon_metadata": {
            "source_file": source_filename,
            "model": agent.model,
            "tools_declared": [t.name for t in tools if t.name in (agent.tools or [])],
            "rag_sources": [r.name for r in rags],
            "flows": [f.name for f in flows],
            "type_aliases": [t.name for t in types],
            "memory": _memory_summary(agent),
        },
    }


def _derive_use_case_id(agent_name: str) -> str:
    """Derive a use_case_id from the agent name."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", agent_name).strip("-").upper()
    return f"AXON-{slug}"


def _infer_domain(agent: AgentDecl, tools: list[ToolDecl]) -> str:
    """Infer a domain from agent tools and model."""
    tool_names = " ".join(t.name.lower() for t in tools)
    all_text = f"{agent.name.lower()} {tool_names}"

    domain_hints = [
        (["finance", "payment", "refund", "billing", "purchase"], "Finance"),
        (["search", "research", "fetch", "web", "scrape"], "Research"),
        (["invoice", "po", "procurement", "vendor", "challan"], "Procurement"),
        (["email", "ticket", "support", "customer", "reply"], "Customer Support"),
        (["github", "issue", "triage", "label", "pr", "commit"], "Engineering"),
        (["doc", "summarize", "extract", "knowledge"], "Knowledge Management"),
        (["monitor", "alert", "metric", "log", "deploy"], "DevOps"),
        (["hr", "policy", "employee", "leave"], "Human Resources"),
        (["rag", "retrieve", "embed", "vector"], "Knowledge Management"),
    ]

    for keywords, domain in domain_hints:
        if any(kw in all_text for kw in keywords):
            return domain

    return "General"


def _build_description(
    agent: AgentDecl,
    tools: list[ToolDecl],
    rags: list[RagDecl],
    flows: list[FlowDecl],
) -> str:
    """Build a human-readable description from declarations."""
    parts = [f"AXON-compiled agent '{agent.name}' using model '{agent.model}'."]

    agent_tool_names = [t for t in (agent.tools or [])]
    if agent_tool_names:
        parts.append(f"Tools: {', '.join(agent_tool_names)}.")

    if rags:
        parts.append(f"RAG sources: {', '.join(r.name for r in rags)}.")

    if flows:
        parts.append(f"Flows: {', '.join(f.name for f in flows)}.")

    if agent.memory:
        parts.append(f"Memory: {agent.memory.kind}.")

    return " ".join(parts)


def _infer_autonomy(agent: AgentDecl, tools: list[ToolDecl]) -> int:
    """Infer autonomy level (0-5) from agent capabilities."""
    level = 1

    tool_names_lower = " ".join(t.name.lower() for t in tools)
    agent_tools_lower = [t.lower() for t in (agent.tools or [])]

    if agent.memory:
        level += 1

    if any("send" in t or "email" in t or "write" in t or "create" in t
           for t in agent_tools_lower):
        level += 1

    if any("approve" in t or "payment" in t or "refund" in t or "close" in t
           for t in agent_tools_lower):
        level += 1

    if any("deploy" in t or "execute" in t or "run" in t for t in agent_tools_lower):
        level += 1

    return min(level, 5)


def _infer_risk_factors(agent: AgentDecl, tools: list[ToolDecl]) -> dict[str, Any]:
    """Infer risk factors from agent tools and capabilities."""
    agent_tools_lower = [t.lower() for t in (agent.tools or [])]
    tool_bodies = " ".join(t.body.lower() for t in tools)

    external_action = any(
        kw in " ".join(agent_tools_lower) + " " + tool_bodies
        for kw in ["http", "send", "email", "deploy", "write", "create", "approve", "payment"]
    )

    financial_keywords = ["payment", "refund", "invoice", "billing", "purchase", "approve"]
    financial_impact = "high" if any(kw in " ".join(agent_tools_lower) for kw in financial_keywords) else "none"

    if financial_impact == "none":
        financial_impact = "medium" if any(kw in tool_bodies for kw in financial_keywords) else "none"

    data_sensitivity = "medium"
    if agent.memory and agent.memory.kind == "Semantic":
        data_sensitivity = "medium"
    if any("rag" in t or "retrieve" in t or "embed" in t for t in agent_tools_lower):
        data_sensitivity = "high" if external_action else "medium"

    reversibility = "easy"
    if external_action:
        reversibility = "moderate"
    if financial_impact == "high":
        reversibility = "hard"

    impact = "low"
    if external_action:
        impact = "medium"
    if financial_impact == "high":
        impact = "high"

    return {
        "data_sensitivity": data_sensitivity,
        "external_action": external_action,
        "financial_impact": financial_impact,
        "reversibility": reversibility,
        "customer_or_employee_impact": impact,
    }


def _infer_scores(
    agent: AgentDecl,
    tools: list[ToolDecl],
    rags: list[RagDecl],
    flows: list[FlowDecl],
    types: list[TypeAliasDecl],
) -> dict[str, float]:
    """Infer heuristic governance scores from declaration richness."""
    tool_count = len([t for t in tools if t.name in (agent.tools or [])])
    has_memory = 1 if agent.memory else 0
    has_rag = 1 if rags else 0
    has_flows = 1 if flows else 0
    type_count = len(types)

    base = 70.0

    return {
        "business_value": min(base + tool_count * 3, 95),
        "task_suitability": min(base + tool_count * 2 + has_flows * 5, 95),
        "data_readiness": min(base - 10 + has_rag * 15 + type_count * 2, 90),
        "governance_readiness": min(base - 5 + has_memory * 5, 90),
        "evaluation_coverage": min(base - 15 + tool_count * 4, 85),
        "safety_security": min(base - 5, 85),
        "human_in_loop": min(base + 10, 95),
        "operational_readiness": min(base - 10 + has_flows * 10 + has_memory * 5, 85),
        "open_architecture_fit": min(base + 15, 98),
    }


def _build_artifacts(
    source_filename: str,
    agent: AgentDecl,
    tools: list[ToolDecl],
    rags: list[RagDecl],
    flows: list[FlowDecl],
) -> list[str]:
    """Build the submitted_artifacts list."""
    artifacts = ["axon_source_file"]
    if source_filename:
        artifacts.append(source_filename)
    if agent.tools:
        artifacts.append("tool_inventory")
    if rags:
        artifacts.append("data_inventory")
    if flows:
        artifacts.append("flow_specification")
    if agent.memory:
        artifacts.append("memory_specification")
    return artifacts


def _memory_summary(agent: AgentDecl) -> str | None:
    """Get a memory summary string."""
    if not agent.memory:
        return None
    opts = ", ".join(f"{k}={v}" for k, v in agent.memory.options.items())
    return f"{agent.memory.kind}({opts})" if opts else agent.memory.kind


def _extract_governance_annotation(agent: AgentDecl) -> dict[str, str] | None:
    """Extract @governance annotation args from an agent declaration."""
    for ann in (agent.annotations or []):
        if ann.name == "governance" and ann.args:
            return dict(ann.args)
    return None


def _override_risk(risk_factors: dict[str, Any], risk_level: str) -> dict[str, Any]:
    """Override risk factors based on explicit @governance risk level."""
    level = risk_level.strip('"').strip("'").lower()
    if level in ("low", "minimal"):
        risk_factors["external_action"] = False
        risk_factors["financial_impact"] = "none"
        risk_factors["reversibility"] = "easy"
        risk_factors["customer_or_employee_impact"] = "low"
    elif level in ("medium", "moderate"):
        risk_factors["external_action"] = True
        risk_factors["financial_impact"] = "medium"
        risk_factors["reversibility"] = "moderate"
        risk_factors["customer_or_employee_impact"] = "medium"
    elif level in ("high", "critical"):
        risk_factors["external_action"] = True
        risk_factors["financial_impact"] = "high"
        risk_factors["reversibility"] = "hard"
        risk_factors["customer_or_employee_impact"] = "high"
    return risk_factors


def _parse_artifact_list(artifacts_str: str) -> list[str]:
    """Parse a bracketed list of artifact names from annotation args."""
    s = artifacts_str.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    items = [a.strip().strip('"').strip("'") for a in s.split(",")]
    return [a for a in items if a]
