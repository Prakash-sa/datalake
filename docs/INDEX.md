# Documentation Index

Start with the [project README](../README.md) for setup and a tour of the
repository. This index maps the rest.

## Architecture

| Document | What it covers |
| --- | --- |
| [ARCHITECTURE.md](architecture/ARCHITECTURE.md) | System design, components, and data flow |
| [ARCHITECTURE_DIAGRAMS.md](architecture/ARCHITECTURE_DIAGRAMS.md) | Rendered diagrams of the pipeline and services |
| [SYSTEM_DESIGN_INTERVIEW.md](architecture/SYSTEM_DESIGN_INTERVIEW.md) | System design walkthrough in Q&A form |
| [DESKTOP_RAG_PRODUCTION_PLAN.md](architecture/DESKTOP_RAG_PRODUCTION_PLAN.md) | Plan and rationale for the local-first desktop build |
| [Backend architecture](../backend/ARCHITECTURE.md) | Backend layering, composition, and retrieval pipeline |

## Decisions

| Document | What it covers |
| --- | --- |
| [ADR 0001](adr/0001-local-first-desktop-rag.md) | Why the product is a local-first desktop RAG application |

## Reference

| Document | What it covers |
| --- | --- |
| [API_REFERENCE.md](reference/API_REFERENCE.md) | REST endpoints with request and response examples |
| [Backend README](../backend/README.md) | Endpoint table, configuration, and developer commands |

## Operations

| Document | What it covers |
| --- | --- |
| [QUICK_START_PRODUCTION.md](operations/QUICK_START_PRODUCTION.md) | Fastest path to a running production stack |
| [DEPLOYMENT.md](operations/DEPLOYMENT.md) | Environment setup, Kubernetes, and cloud deployment |
| [PIPELINE_GUIDE.md](operations/PIPELINE_GUIDE.md) | Running and monitoring the Airflow ingestion pipeline |
| [RELEASE.md](operations/RELEASE.md) | Release, signing, and checksum process |
| [TROUBLESHOOTING.md](operations/TROUBLESHOOTING.md) | Common failures and how to diagnose them |

## Security and privacy

| Document | What it covers |
| --- | --- |
| [SECURITY_THREAT_MODEL.md](security/SECURITY_THREAT_MODEL.md) | Assets, trust boundaries, and mitigations |
| [PRIVACY.md](security/PRIVACY.md) | What is stored locally and what never leaves the machine |
| [SECURITY.md](../SECURITY.md) | How to report a vulnerability |

## Layout

```
docs/
├── INDEX.md            # this file
├── adr/                # architecture decision records
├── architecture/       # system design and diagrams
├── reference/          # API reference
├── operations/         # deployment, pipeline, release, troubleshooting
├── security/           # threat model and privacy
└── assets/             # images used by the docs
```
