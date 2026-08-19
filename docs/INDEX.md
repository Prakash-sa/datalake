# Documentation

Start with the [project README](../README.md) for what this is, screenshots, and
how to run it.

| Document | What it covers |
| --- | --- |
| [Architecture](architecture/ARCHITECTURE.md) | Design principles, runtime topology, storage, security boundary |
| [Backend architecture](architecture/BACKEND.md) | Layering, ingestion state machine, retrieval, fingerprints, streaming |
| [API reference](reference/API_REFERENCE.md) | Every endpoint, error code, and streaming format |
| [Backend README](../backend/README.md) | Layout, configuration, developer commands |
| [Evals](../evals/README.md) | Fixture corpus, eval cases, retrieval metrics |
| [Deployment](operations/DEPLOYMENT.md) | Desktop builds, releasing, container stack, backups, upgrades |
| [Troubleshooting](operations/TROUBLESHOOTING.md) | Error codes and what to do about them |
| [Pipeline guide](operations/PIPELINE_GUIDE.md) | The optional Airflow ingestion pipeline |
| [Security](../SECURITY.md) | Policy, trust boundaries, threat model, release blockers |
| [Privacy](security/PRIVACY.md) | What runs locally, what is stored, what redaction does |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Bundled software and model, and an unresolved licence conflict |
| [ADR 0001](adr/0001-local-first-desktop-rag.md) | Why local-first desktop, and how the decision was amended |
| [Production plan](architecture/DESKTOP_RAG_PRODUCTION_PLAN.md) | Historical: the plan this was built against |

## Conventions

Each subject has one home. Where two documents would describe the same
mechanism, the more specific one owns it and the other links to it — the system
architecture describes the runtime and defers backend internals to the backend
document, and the security policy holds the threat model rather than splitting
it across two files.
