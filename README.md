# 🚀 Enterprise Document RAG Platform

## 🎯 Semantic Search & LLM Analysis at Scale

A production-grade **Retrieval Augmented Generation (RAG) system** for intelligent document discovery and analysis across large enterprise document collections. Built with:

- **Apache Airflow** - Workflow orchestration and document ingestion
- **FastAPI** - High-performance REST API for document search
- **Next.js** - Modern React frontend for document exploration
- **Chroma** - Vector database for semantic embeddings
- **Ollama** - Local LLM inference (no external APIs)
- **MinIO** - S3-compatible object storage
- **PostgreSQL** - Metadata and state management
- **Redis** - Caching and message broker

Designed for enterprises needing semantic search, LLM-powered analysis, and real-time document ingestion on massive collections.

## 🏗️ Architecture

```
Frontend (Next.js) → API (FastAPI) → RAG Engine
                        ↓
                    Vector DB (Chroma)
                        ↓
                    LLM Inference (Ollama)
                        
Document Ingestion via Airflow DAGs → MinIO Storage
```

## 📚 Documentation

Complete documentation is organized in the `docs/` folder:

| Document | Purpose |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, components, data flow, tech stack |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Dev/staging/production setup, Kubernetes, troubleshooting |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | REST API endpoints, request/response examples, auth |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues, solutions, debugging tips |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 4GB RAM minimum
- macOS/Linux/Windows with WSL2

### Start Services

```bash
# Clone and navigate
git clone <repo>
cd datalake-project

# Copy environment file
cp .env.example .env

# Start all services
./scripts/start.sh

# Services will be available at:
# Frontend: http://localhost:3000
# API: http://localhost:8000
# Airflow: http://localhost:9093
# MinIO Console: http://localhost:9001
# Chroma: http://localhost:8001
```

### First Time Setup

1. **Upload Sample Documents** to MinIO (http://localhost:9001)
2. **Trigger Airflow DAG** - Navigate to http://localhost:9093
3. **Test Search** - Go to http://localhost:3000 and search

For detailed setup, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 📂 Project Structure

```
datalake-project/
├── docs/                            # Comprehensive documentation
│   ├── ARCHITECTURE.md              # System design & components
│   ├── DEPLOYMENT.md                # Setup for all environments
│   ├── API_REFERENCE.md             # REST API endpoints
│   └── TROUBLESHOOTING.md           # Common issues & solutions
│
├── src/                             # Source code
│   ├── orchestration/               # Apache Airflow DAGs
│   │   ├── dags/                    # DAG definitions
│   │   └── config/                  # Airflow configuration
│   └── services/                    # Microservices
│       ├── rag-engine/              # FastAPI backend
│       └── frontend/                # Next.js React UI
│
├── scripts/                         # Helper scripts
│   ├── start.sh                     # Start all services
│   ├── stop.sh                      # Stop services
│   ├── health-check.sh              # Health verification
│   └── setup.sh                     # Initial setup
│
├── docker-compose.yml               # Multi-container setup
├── .env.example                     # Environment template
└── README.md                        # This file
```

## 🎯 Core Features

| Feature | Details |
|---------|---------|
| **Document Search** | Semantic search with vector embeddings |
| **LLM Integration** | Local Ollama inference (no external APIs) |
| **Workflow Automation** | Apache Airflow for scheduled ingestion |
| **REST API** | FastAPI with OpenAPI documentation |
| **Web UI** | Modern Next.js React interface |
| **Vector Storage** | Chroma for semantic embeddings |
| **Object Storage** | MinIO S3-compatible storage |
| **Database** | PostgreSQL for metadata |

## 🔧 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Orchestration | Apache Airflow | 2.9.0 |
| Backend | FastAPI | 0.104+ |
| Frontend | Next.js | 14+ |
| Vector DB | Chroma | 0.4.24+ |
| LLM | Ollama | latest |
| Storage | MinIO | latest |
| Database | PostgreSQL | 13 |
| Message Broker | Redis | 7 |
| Containerization | Docker | 24+ |

## 🚦 Health Check

```bash
# Run comprehensive health check
./scripts/health-check.sh

# Expected output:
# ✓ Frontend running
# ✓ API healthy
# ✓ Airflow responsive
# ✓ Vector DB connected
# ✓ Storage accessible
```

## 📊 System Status

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | ✅ Ready | FastAPI + Uvicorn |
| Frontend | ✅ Ready | Next.js React |
| Airflow | ✅ Ready | Scheduler + Workers |
| Chroma | ✅ Ready | Vector embeddings |
| Ollama | ✅ Ready | Local LLM inference |
| MinIO | ✅ Ready | Object storage |
| PostgreSQL | ✅ Ready | Metadata store |

## 🔍 Common Commands

```bash
# View logs
docker-compose logs -f [service]

# Stop services
./scripts/stop.sh

# Clean everything
docker-compose down -v

# Rebuild images
docker-compose build --no-cache

# Access Airflow
open http://localhost:9093

# Access API docs
open http://localhost:8000/docs

# Test search endpoint
curl -X POST http://localhost:8000/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"example search"}'
```

## 📞 Support & Documentation

- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- **Deployment**: See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for setup help
- **API Usage**: See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for endpoints
- **Issues**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for solutions

## 🎓 Learning Resources

- [Apache Airflow Documentation](https://airflow.apache.org/)
- [FastAPI Guide](https://fastapi.tiangolo.com/)
- [Next.js Handbook](https://nextjs.org/learn)
- [Chroma Documentation](https://docs.trychroma.com/)
- [Ollama Models](https://ollama.ai/library)

## 📝 License

This project is private and proprietary.

---

**Last Updated**: December 21, 2025  
**Status**: ✅ Production-Ready  
**Version**: 1.0.0
