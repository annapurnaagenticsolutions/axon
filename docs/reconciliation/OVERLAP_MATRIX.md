# AXON ↔ AgentOps Mesh Overlap Matrix

Date: 2026-10-05

| Capability | AXON today | Mesh today | Canonical direction |
|---|---|---|---|
| Parser/type system/IR | Strong | None | AXON |
| Runtime execution | Strong | Runtime enforcement model | AXON |
| Provider registry | Implemented | Implemented | AXON runtime contract; Mesh consumes normalized provider evidence |
| Model routing | Implemented | Provider gateway governance | AXON executes; Assurance verifies policy/cost/risk |
| Tool registry/sandbox | Implemented | Tool sandbox + connector contract | AXON runtime contract; Assurance validates |
| Agent registry/discovery | Service registry/discovery | Agent registry | Separate runtime discovery from governance inventory; shared schema |
| Policy | Permission/runtime governance | Policy guardrail | Policy IR under AXON; Assurance is evaluator/enforcer adapter |
| Approvals | Runtime/governance hooks | Approval workflow | Shared approval contract; no duplicate token semantics |
| Tracing | Trace emitter/context/replay | Trace ledger | AXON emits normalized trace; Assurance stores/evaluates evidence |
| Observability | Metrics + OTel/OTLP | Observability summaries | OTel-first; Mesh-specific summaries become views |
| Evaluation | Eval harness/evaluator | Evaluator + benchmarks | AXON Assurance single evaluation contract |
| Evidence/audit | Runtime governance evidence | Evidence vault + audit bus | Assurance canonical evidence schema |
| Security | Permissions/secrets/sandbox | RBAC/readiness/identity boundary | Runtime enforcement in AXON; readiness/evaluation in Assurance |
| Deployment | Docker/K8s/Fly tooling | Deployment profiles | AXON target adapters; Assurance validates deployment contract |
| CI/CD | CI templates, project checks | Launch/readiness workflows | AXON build/test; Assurance gates release |
| Memory/RAG | Implemented abstractions | None material | AXON; do not create separate Memory SaaS |
| Debug/replay | Implemented | Trace inspection | AXON Studio/Assurance |
| Package management | Implemented | None | AXON |
| Multi-agent messaging | Native + Redis/NATS | Governance only | Replace proprietary external interoperability with A2A adapter |

## Consolidation rules

1. **Execution lives in AXON.**
2. **Assurance evaluates execution; it does not become a second runtime.**
3. **All traces normalize to one AXON trace/evidence envelope, exportable via OpenTelemetry.**
4. **MCP and A2A are protocols, not features to reinvent.**
5. **Provider-specific features are target adapters behind AXON IR.**
6. **Mesh JSON schemas are migrated only when they add assurance semantics absent from AXON.**
7. **No new service is created until an existing AXON/Mesh module is checked first.**
