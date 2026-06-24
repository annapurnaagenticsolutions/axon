# AXON → AgentOps Mesh Integration Bridge

## Overview

AXON agents can be compiled into AgentOps Mesh governance submissions using:

```bash
axon compile examples/research_pipeline.ax --target governance -o governance.json
```

This generates a `GovernanceWorkflowRequest` JSON compatible with AgentOps Mesh's `/governance/run` endpoint.

## Pipeline

```
.ax source file
    → parse (AXON parser)
    → validate (semantic checks)
    → generate_governance_submission()
    → GovernanceWorkflowRequest JSON
    → POST to AgentOps Mesh /governance/run
    → 9-gate governance workflow
    → readiness decision
```

## What the Bridge Extracts

| AXON Declaration | Governance Field |
|---|---|
| `agent` name | `use_case_id`, `name` |
| `agent` model | `_axon_metadata.model` |
| `agent` tools | `submitted_artifacts`, risk inference |
| `tool` declarations | `domain` inference, `risk_factors.external_action` |
| `rag` declarations | `data_readiness` score, `data_sensitivity` |
| `flow` declarations | `operational_readiness` score |
| `type` declarations | `data_readiness` score |
| `agent` memory | `governance_readiness` score, autonomy level |

## Risk Inference Heuristics

The bridge infers risk factors from tool names and bodies:

- **external_action**: `true` if tools contain `http`, `send`, `email`, `deploy`, `write`, `create`, `approve`, `payment`
- **financial_impact**: `high` if tools contain `payment`, `refund`, `invoice`, `billing`, `purchase`, `approve`
- **data_sensitivity**: `high` if RAG is present with external action; `medium` otherwise
- **reversibility**: `hard` if financial impact is high; `moderate` if external action; `easy` otherwise

## Autonomy Level Inference

| Signal | Level |
|---|---|
| Base | 1 |
| Has memory | +1 |
| Has send/email/write/create tools | +1 |
| Has approve/payment/refund tools | +1 |
| Has deploy/execute/run tools | +1 |
| Max | 5 |

## Demo

```bash
# Generate governance JSON only
python examples/governance_bridge_demo.py

# Generate and submit to a running AgentOps Mesh instance
python examples/governance_bridge_demo.py --submit http://localhost:8000

# Save output to file
python examples/governance_bridge_demo.py -o governance_submission.json
```

## AgentOps Mesh Side

The generated JSON is a valid `GovernanceWorkflowRequest` that AgentOps Mesh processes through its 9-gate workflow:

1. Use Case Intake
2. Suitability
3. Risk Assessment
4. Data Readiness
5. Governance
6. Evaluation
7. Human Approval
8. Pilot Readiness
9. Production Readiness

Each gate produces pass/caution/fail with hard-blocking flags.

## Future Enhancements

- **Bi-directional**: AgentOps Mesh governance results fed back into AXON compiler warnings
- **Policy-as-code**: AXON agents declaring their own governance constraints in `.ax` syntax
- **Trace bridge**: AXON trace events exported to AgentOps Mesh Trace Ledger
- **CI integration**: `axon compile --target governance` in CI to gate agent deployments
