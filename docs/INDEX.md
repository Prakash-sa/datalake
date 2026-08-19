# Documentation

Start with the [project README](../README.md) for what this is, screenshots, and
how to run it.

## Understanding the system

| Document | What it covers |
| --- | --- |
| [Architecture](architecture/ARCHITECTURE.md) | Design principles, runtime, storage, retrieval, security boundary |
| [Backend architecture](../backend/ARCHITECTURE.md) | Layering, composition, ingestion state machine, fingerprints |
| [ADR 0001](adr/0001-local-first-desktop-rag.md) | Why local-first desktop, and how the decision was amended |
| [Production plan](architecture/DESKTOP_RAG_PRODUCTION_PLAN.md) | The plan this was built against, with implementation status |

## Using it

| Document | What it covers |
| --- | --- |
| [API reference](reference/API_REFERENCE.md) | Every endpoint, error code, and streaming format |
| [Backend README](../backend/README.md) | Layout, configuration, developer commands |
| [Evals](../evals/README.md) | Fixture corpus, eval cases, retrieval metrics |

## Operating it

| Document | What it covers |
| --- | --- |
| [Deployment](operations/DEPLOYMENT.md) | Desktop builds, container stack, backups, upgrades |
| [Troubleshooting](operations/TROUBLESHOOTING.md) | Error codes and what to do about them |
| [Pipeline guide](operations/PIPELINE_GUIDE.md) | The optional Airflow ingestion pipeline |
| [Release](operations/RELEASE.md) | Release and signing process |

## Security and privacy

| Document | What it covers |
| --- | --- |
| [Privacy](security/PRIVACY.md) | What runs locally, what is stored, what redaction does |
| [Threat model](security/SECURITY_THREAT_MODEL.md) | Assets, trust boundaries, mitigations |
| [Security policy](../SECURITY.md) | Security model and how to report a vulnerability |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Bundled software, the bundled model, and an unresolved licence conflict |
