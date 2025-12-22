# Backend - Clean Architecture

Production-ready Document RAG Engine following Clean Architecture principles.

## Architecture Overview

```
rag-query-engine/backend/
├── domain/                    # Business logic layer
│   ├── __init__.py
│   └── models.py             # Core domain models
├── application/              # Use case layer
│   ├── __init__.py
│   └── rag_service.py        # RAG service (orchestration)
├── infrastructure/           # External services
│   ├── __init__.py
│   └── config_manager.py     # Configuration management
├── interfaces/               # API contracts
│   ├── __init__.py
│   ├── request_models.py     # Request validation
│   └── response_models.py    # Response formatting
├── api/                      # HTTP controllers
│   └── __init__.py          # API routes
├── main.py                  # Application entry point
├── requirements.txt         # Dependencies
├── Dockerfile              # Development container
├── Dockerfile.prod         # Production container
├── .env.production        # Production settings
└── docker-compose.yml     # Local development
```

## Layer Responsibilities

### 1. Domain Layer (`domain/`)
**Purpose**: Core business logic, independent of frameworks

- **models.py**: Domain entities (Document, SearchResult, QueryResult, EngineStats)
- No external dependencies
- Pure Python dataclasses
- Validation logic

### 2. Application Layer (`application/`)
**Purpose**: Use cases and orchestration

- **rag_service.py**: Coordinates domain models with infrastructure
- Business rules implementation
- Error handling and logging
- Stateless service design

### 3. Infrastructure Layer (`infrastructure/`)
**Purpose**: External service integration

- **config_manager.py**: Handles configuration from environment
- Environment-specific settings (dev/prod/test)
- Database connections, API clients (future)

### 4. Interfaces Layer (`interfaces/`)
**Purpose**: API contracts and validation

- **request_models.py**: Pydantic models for input validation
- **response_models.py**: Pydantic models for output formatting
- Keeps FastAPI concerns separated

### 5. API Layer (`api/`)
**Purpose**: HTTP routes and controllers

- FastAPI router definitions
- Request handling and response formatting
- Service initialization

### 6. Main Application (`main.py`)
**Purpose**: Application bootstrap

- FastAPI app creation
- Middleware setup
- Service initialization
- Route registration

## Clean Architecture Benefits

✅ **Testability**: Each layer can be tested independently  
✅ **Maintainability**: Clear separation of concerns  
✅ **Flexibility**: Easy to swap implementations (e.g., different LLMs)  
✅ **Scalability**: Domain logic is independent of infrastructure  
✅ **Reusability**: RAG service can be used in different contexts  

## Dependency Flow

```
Domain (Business Logic)
  ↑
Application (Use Cases)
  ↑
Infrastructure (External Services)
  ↑
Interfaces (API Contracts)
  ↑
API (HTTP Controllers)
  ↑
Main (Entry Point)
```

Note: Dependencies always point inward (toward domain layer).

## Running the Application

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export ENV=development

# Run server
python -m uvicorn main:app --reload
```

### Production
```bash
# Via Docker
docker-compose -f docker-compose.prod.yml up -d

# Or with Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

## API Endpoints

```
GET  /              # API info and status
GET  /health        # Health check
GET  /stats         # Engine statistics
POST /query         # RAG query (search + LLM analysis)
POST /documents/search   # Semantic search only
POST /documents/index    # Index documents
```

## Configuration

Environment variables (see `.env.production`):

```
# Environment
ENV=production
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# RAG Engine
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=mistral
LLM_TEMPERATURE=0.3

# Resource Limits
MAX_DOCUMENTS=10000
MAX_QUERY_LENGTH=1000
QUERY_TIMEOUT=30
```

## Adding New Features

### New Search Algorithm
1. Add method to `rag_service.py` in application layer
2. Update `domain/models.py` if needed for new data structures
3. Add endpoint to `api/__init__.py`
4. Add request/response models to `interfaces/`

### New Configuration Option
1. Add to `ConfigManager` in `infrastructure/config_manager.py`
2. Use via `config.SETTING_NAME` in `main.py`

### New API Endpoint
1. Define Pydantic models in `interfaces/`
2. Add endpoint handler in `api/__init__.py`
3. Call `rag_service` method from application layer

## Testing

```bash
# Unit tests for domain
pytest domain/

# Application tests
pytest application/

# API integration tests
pytest api/
```

## Future Enhancements

- [ ] Database abstraction for multi-instance deployments
- [ ] Message queue for async processing
- [ ] Plugin system for custom models
- [ ] Multi-tenancy support
- [ ] Advanced caching layer
- [ ] Model versioning and A/B testing

---

**Architecture Pattern**: Clean Architecture (Hexagonal Architecture)  
**Status**: Production Ready ✅  
**Last Updated**: December 20, 2025
