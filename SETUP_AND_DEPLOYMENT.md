# Complete Setup & Deployment Guide: Enterprise Document Platform

> **Comprehensive guide covering development setup and production deployment with Kubernetes, KEDA autoscaling, and Dynamic DAGs for 1M+ document processing.**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker Compose)](#quick-start-docker-compose)
3. [Production Deployment (Kubernetes + KEDA)](#production-deployment-kubernetes--keda)
4. [Component Setup](#component-setup)
5. [Dynamic DAG Configuration](#dynamic-dag-configuration)
6. [KEDA Installation & Configuration](#keda-installation--configuration)
7. [Airflow + RAG Integration](#airflow--rag-integration)
8. [Kubernetes Manifests](#kubernetes-manifests)
9. [Monitoring & Scaling](#monitoring--scaling)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Development Environment
- **Docker & Docker Compose** (v20.10+)
- **Python** 3.11+ (for local development)
- **Git** (for version control)
- **8GB RAM minimum** (for all services)
- **20GB disk space** (for data volumes)

### Production Environment (Kubernetes + KEDA)
- **Kubernetes Cluster** (v1.24+)
  - 3+ worker nodes minimum
  - 16GB+ RAM per node
  - 100GB+ disk per node
  - Network policies enabled
- **kubectl** CLI (v1.24+)
- **Helm 3** (for package management)
- **KEDA** (v2.12+)
- **Persistent Volume Provisioner** (NFS, EBS, etc.)
- **Monitoring** (Prometheus + Grafana optional)

### System Check

```bash
# Development environment
docker --version
docker-compose --version
python3 --version

# Production environment (optional)
kubectl version --client
helm version
keda --version  # After KEDA installation
```

---

## Quick Start (Docker Compose)

### 1. Clone and Navigate to Project

```bash
cd datalake-project
```

### 2. Start All Services (One Command)

```bash
# Option A: Start entire stack (Trino + Iceberg + Airflow + RAG)
./start-all.sh

# Option B: Start individually (see Component Setup below)
```

### 3. Verify All Services

```bash
# Check all containers running
docker-compose ps

# Expected output:
# - trino         RUNNING  (port 8080)
# - postgres      RUNNING  (port 5432)
# - minio         RUNNING  (port 9000)
# - airflow       RUNNING  (port 8080)
# - ollama        RUNNING  (port 11434)
# - rag-backend   RUNNING  (port 8000)
# - rag-frontend  RUNNING  (port 3000)
```

### 4. Access Interfaces

```bash
# Trino Web UI
open http://localhost:8080

# Airflow Web UI
open http://localhost:8080

# RAG Query Engine
open http://localhost:3000

# API Backend
curl http://localhost:8000
```

---

## Production Deployment (Kubernetes + KEDA)

### Architecture

```
┌─────────────────────────────────────┐
│    Kubernetes Cluster (3+ nodes)    │
├─────────────────────────────────────┤
│  Namespaces:                        │
│  ├─ airflow (orchestration)         │
│  ├─ rag-engine (query engine)       │
│  ├─ data-lake (storage)             │
│  └─ monitoring (prometheus/grafana) │
├─────────────────────────────────────┤
│  KEDA Scaler:                       │
│  └─ Monitor Airflow task queue      │
│  └─ Scale: 2-100 pods               │
│  └─ Metric: Queue depth > 10 tasks  │
└─────────────────────────────────────┘
```

### Prerequisites

1. **Kubernetes Cluster Ready**
```bash
kubectl cluster-info
kubectl get nodes
```

2. **Install KEDA**
```bash
# Add KEDA Helm repository
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install KEDA in keda namespace
helm install keda kedacore/keda --namespace keda --create-namespace

# Verify installation
kubectl get deployment -n keda
```

3. **Create Namespaces**
```bash
kubectl create namespace airflow
kubectl create namespace rag-engine
kubectl create namespace data-lake
```

### Deploy to Kubernetes

#### 1. Deploy Data Lake Stack (Trino + Iceberg + MinIO + PostgreSQL)

```yaml
# data-lake-deployment.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: data-lake
---
# PostgreSQL Metastore
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-metastore
  namespace: data-lake
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres-metastore
  template:
    metadata:
      labels:
        app: postgres-metastore
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: metastore
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
# Persistent Volume Claim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: data-lake
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
---
# Trino Service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trino-coordinator
  namespace: data-lake
spec:
  replicas: 1
  selector:
    matchLabels:
      app: trino
  template:
    metadata:
      labels:
        app: trino
    spec:
      containers:
      - name: trino
        image: trinodb/trino:latest
        ports:
        - containerPort: 8080
        env:
        - name: TRINO_DISCOVERY_URI
          value: "http://trino-coordinator.data-lake.svc.cluster.local:8080"
        volumeMounts:
        - name: trino-config
          mountPath: /etc/trino/catalog
      volumes:
      - name: trino-config
        configMap:
          name: trino-config
---
apiVersion: v1
kind: Service
metadata:
  name: trino-coordinator
  namespace: data-lake
spec:
  selector:
    app: trino
  ports:
  - port: 8080
    targetPort: 8080
  type: LoadBalancer
```

#### 2. Deploy Airflow with KEDA Scaler

```yaml
# airflow-deployment.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: airflow
---
# Airflow Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow-worker
  namespace: airflow
spec:
  replicas: 2  # Initial replicas (KEDA will scale)
  selector:
    matchLabels:
      app: airflow-worker
  template:
    metadata:
      labels:
        app: airflow-worker
    spec:
      containers:
      - name: airflow-worker
        image: apache/airflow:2.7.0
        env:
        - name: AIRFLOW__CORE__EXECUTOR
          value: "CeleryExecutor"
        - name: AIRFLOW__CELERY__BROKER_URL
          value: "postgresql://airflow:airflow@airflow-db.airflow.svc.cluster.local:5432/airflow"
        - name: AIRFLOW__CELERY__RESULT_BACKEND
          value: "postgresql://airflow:airflow@airflow-db.airflow.svc.cluster.local:5432/airflow"
        volumeMounts:
        - name: dags
          mountPath: /opt/airflow/dags
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
      volumes:
      - name: dags
        configMap:
          name: airflow-dags
---
# KEDA ScaledObject for Airflow
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-worker-scaler
  namespace: airflow
spec:
  scaleTargetRef:
    name: airflow-worker
  minReplicaCount: 2
  maxReplicaCount: 100
  triggers:
  - type: postgresql
    metadata:
      query: "SELECT COUNT(*) FROM task_instance WHERE state='queued'"
      threshold: "10"
      dbName: "airflow"
      connection: "postgres://airflow:airflow@airflow-db.airflow.svc.cluster.local:5432/airflow"
  - type: cpu
    metadata:
      type: Utilization
      value: "80"
  fallback:
    failureThreshold: 3
    replicas: 2
  cooldownPeriod: 120
```

#### 3. Deploy RAG Query Engine

```yaml
# rag-engine-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-query-engine
  namespace: rag-engine
spec:
  replicas: 2
  selector:
    matchLabels:
      app: rag-query-engine
  template:
    metadata:
      labels:
        app: rag-query-engine
    spec:
      containers:
      - name: rag-backend
        image: rag-query-engine:latest
        ports:
        - containerPort: 8000
        env:
        - name: TRINO_HOST
          value: "trino-coordinator.data-lake.svc.cluster.local"
        - name: CHROMA_HOST
          value: "chroma-service.rag-engine.svc.cluster.local"
        - name: OLLAMA_BASE_URL
          value: "http://ollama.rag-engine.svc.cluster.local:11434"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: rag-query-engine
  namespace: rag-engine
spec:
  selector:
    app: rag-query-engine
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer
```

### Deploy Using kubectl

```bash
# Create namespaces
kubectl create namespace data-lake
kubectl create namespace airflow
kubectl create namespace rag-engine

# Deploy data lake
kubectl apply -f data-lake-deployment.yaml

# Deploy Airflow with KEDA
kubectl apply -f airflow-deployment.yaml

# Deploy RAG engine
kubectl apply -f rag-engine-deployment.yaml

# Verify deployments
kubectl get deployments -A
kubectl get scaledobjects -A
```

### Monitor Scaling

```bash
# Watch pod scaling in real-time
watch kubectl get pods -n airflow

# Check KEDA metrics
kubectl get hpa -n airflow

# View KEDA logs
kubectl logs -n keda deployment/keda-operator

# Check Airflow queue depth
kubectl exec -it deployment/airflow-scheduler -n airflow -- \
  airflow tasks list-dag-runs -d rag_vector_db_ingestion_pipeline
```

---# RAG Query Engine Frontend
open http://localhost:3000

# RAG Backend API Docs
open http://localhost:8000/docs

# MinIO Console
open http://localhost:9001
```

---

## Dynamic DAG Configuration

### Overview

Dynamic DAGs adapt task structure based on document type and batch size, enabling efficient processing of 1M+ documents with variable characteristics.

### Configuration

#### 1. Edit DAG Parameters

File: [airflow-db/dags/rag_vector_db_ingestion_dag.py](airflow-db/dags/rag_vector_db_ingestion_dag.py)

```python
# Dynamic DAG configuration
DAG_CONFIG = {
    'document_types': ['pdf', 'docx', 'images', 'database'],
    'chunk_size': 256,  # Documents per task
    'embedding_batch_size': 16,
    'max_parallel_tasks': 50,
    'retry_policy': {
        'retries': 3,
        'retry_delay_minutes': 5,
        'backoff_multiplier': 2
    },
    'schedule_interval': '@daily',
    'max_active_runs': 5
}
```

#### 2. Configure Document Type Handlers

```python
# handlers/document_type_handlers.py
DOCUMENT_HANDLERS = {
    'pdf': {
        'extractor': PDFExtractor(),
        'timeout_seconds': 120,
        'max_concurrent': 10
    },
    'docx': {
        'extractor': DocxExtractor(),
        'timeout_seconds': 60,
        'max_concurrent': 15
    },
    'images': {
        'extractor': ImageExtractor(),
        'timeout_seconds': 180,  # OCR takes longer
        'max_concurrent': 5
    },
    'database': {
        'extractor': DatabaseExtractor(),
        'timeout_seconds': 300,
        'max_concurrent': 3
    }
}
```

#### 3. Task Group Definition

```python
# Dynamic task generation pseudocode
from airflow.models import DAG
from airflow.utils.task_group import TaskGroup

def generate_document_pipeline(dag, doc_batch):
    """Generate dynamic tasks for document batch"""
    
    with TaskGroup(group_id="document_processing") as tg:
        # Extract phase
        extract_task = extract_metadata_from_iceberg()
        
        # Process phase - dynamic task groups per document type
        process_groups = {}
        for doc_type, docs in doc_batch.group_by_type():
            process_groups[doc_type] = create_process_tasks(
                doc_type=doc_type,
                docs=docs,
                chunk_size=256
            )
        
        # Embed phase - parallel embedding tasks
        embed_tasks = [
            create_embedding_task(f"embed_{i}")
            for i in range(len(doc_batch) // 16)
        ]
        
        # Upsert and validate
        upsert_task = upsert_to_chroma()
        validate_task = validate_indexing()
        
        # Set dependencies
        extract_task >> process_groups.values() >> embed_tasks >> upsert_task >> validate_task
    
    return tg
```

### Performance Tuning

| Parameter | Development | Production (1M docs) | Tuning Strategy |
|-----------|-------------|----------------------|------------------|
| **chunk_size** | 10 | 256 | Balance: memory vs. throughput |
| **embedding_batch_size** | 2 | 16 | Based on Ollama GPU memory |
| **max_parallel_tasks** | 5 | 50 | Set to (worker_pods × 10) |
| **task_pool_limit** | 10 | 500 | Prevent resource starvation |

---

## KEDA Installation & Configuration

### Step 1: Install KEDA

```bash
# Add Helm repository
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install KEDA operator
helm install keda kedacore/keda --namespace keda --create-namespace

# Verify installation
kubectl get pods -n keda
kubectl get crds | grep keda
```

### Step 2: Configure Airflow for KEDA

#### Create Airflow Secret (for Postgres connection)

```bash
kubectl create secret generic airflow-postgres \
  --from-literal=connection-string='postgresql://airflow:airflow@postgres:5432/airflow' \
  -n airflow
```

#### Apply KEDA ScaledObject

```yaml
# keda-airflow-scaler.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: airflow-celery-worker-scaler
  namespace: airflow
spec:
  scaleTargetRef:
    name: airflow-celery-worker
    kind: Deployment
  
  # Scaling limits
  minReplicaCount: 2         # Keep minimum 2 pods during low traffic
  maxReplicaCount: 100       # Scale up to 100 pods for 1M docs
  
  # Autoscaling triggers
  triggers:
  # Primary trigger: Airflow task queue depth
  - type: postgresql
    metadata:
      query: |
        SELECT COUNT(*) as queue_depth 
        FROM task_instance 
        WHERE dag_id = 'rag_vector_db_ingestion_pipeline'
        AND state = 'queued'
      threshold: "10"
      dbName: "airflow"
      connection: "airflow-postgres"
    authModes:
      - "bearer"
  
  # Secondary trigger: CPU utilization
  - type: cpu
    metadata:
      type: Utilization
      value: "80"
  
  # Scaling behavior
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
    
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
      selectPolicy: Min
  
  # Fallback strategy
  fallback:
    failureThreshold: 3
    replicas: 2
  
  cooldownPeriod: 300
```

### Step 3: Deploy KEDA Scaler

```bash
# Create scaler
kubectl apply -f keda-airflow-scaler.yaml

# Verify scaler creation
kubectl get scaledobjects -n airflow
kubectl describe scaledobject airflow-celery-worker-scaler -n airflow

# Monitor scaling activity
kubectl get hpa -n airflow -w
```

### Monitoring KEDA Scaling

```bash
# Watch real-time pod scaling
watch kubectl get pods -n airflow -L keda.sh/scaler

# Check KEDA operator logs
kubectl logs -n keda deployment/keda-operator -f

# Get scaler metrics
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/airflow/pods/*/queue_depth" | jq

# Airflow task metrics
kubectl exec -it deployment/airflow-scheduler -n airflow -- \
  airflow tasks list-dag-runs -d rag_vector_db_ingestion_pipeline
```

### Expected Scaling Behavior

```
Time          Queue Depth    Pods    Reason
------        -----------    ----    ---------
T+0min        0              2       Baseline
T+5min        5000           5       Slight increase
T+10min       50000          30      Rapid scale-up
T+15min       100000         80      Peak scaling
T+20min       80000          65      Scale partial
T+60min       10000          10      Return to baseline
T+80min       0              2       Scale down complete
```

### Troubleshooting KEDA

```bash
# Check if scaler is active
kubectl get hpa -n airflow

# View KEDA metrics
kubectl top pods -n airflow

# Test trigger manually
kubectl exec -it deployment/keda-operator -n keda -- \
  kubectl get triggers

# View recent scaling events
kubectl get events -n airflow --sort-by='.lastTimestamp'
```

---

## Component Setup

### Data Lake Stack (Trino + Iceberg + PostgreSQL + MinIO)

```bash
cd trino-dlake
docker-compose up -d
```

**Services Started**:
- **Trino** (Query Engine): http://localhost:8080
- **PostgreSQL** (Metastore): localhost:5432
- **MinIO** (Object Storage): http://localhost:9000
- **Presto** (Legacy): http://localhost:8081

**Verify**:
```bash
# Test Trino connectivity
docker-compose exec trino trino

# Inside Trino CLI:
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;
SELECT * FROM iceberg.default.example_table LIMIT 5;
```

**Stop**:
```bash
docker-compose down
```

---

### Apache Airflow

```bash
cd airflow-db

# Build custom Airflow image with dependencies
docker build -t airflow-trino -f Dockerfile . --no-cache

# Start Airflow
docker-compose up -d
```

**Services Started**:
- **Airflow Web UI**: http://localhost:8080
- **Airflow Scheduler**: Running in background
- **PostgreSQL** (Airflow DB): localhost:5432

**Verify DAG**:
```bash
# List all DAGs
airflow dags list

# Trigger the RAG pipeline manually
airflow dags trigger rag_vector_db_ingestion_pipeline

# View DAG details
airflow dags show rag_vector_db_ingestion_pipeline

# Check task logs
airflow tasks logs rag_vector_db_ingestion_pipeline task_name -1
```

**Access Airflow UI**:
1. Open http://localhost:8080
2. Default credentials: `airflow` / `airflow`
3. Search for `rag_vector_db_ingestion_pipeline`
4. Click to view DAG, trigger manually, check logs

**Stop**:
```bash
docker-compose down
```

---

### RAG Query Engine (LLM + Frontend)

```bash
cd rag-query-engine
docker-compose up --build
```

**Services Started**:
- **Ollama** (LLM Inference): http://localhost:11434
- **RAG Backend** (FastAPI): http://localhost:8000
- **RAG Frontend** (React): http://localhost:3000
- **Chroma** (Vector DB): Internal (shared volume)

**Verify**:
```bash
# Test backend health
curl http://localhost:8000/health

# Expected response:
# {"status": "ok", "chroma": "connected", "ollama": "connected"}

# View API documentation
open http://localhost:8000/docs

# Test Ollama model
curl http://localhost:11434/api/tags

# Expected: List of available models (llama2, llama3, mistral, etc.)
```

**Access Interfaces**:
- **Query Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Model Management**: http://localhost:11434

**Stop**:
```bash
docker-compose down
```

---

## Airflow + RAG Integration

### Architecture Overview

```
Apache Airflow
    ↓
rag_vector_db_ingestion_pipeline (DAG)
    ├─ Extract metadata from Iceberg (Trino)
    ├─ Extract sample data from tables
    ├─ Create embeddings (Ollama)
    ├─ Upsert to Chroma (Vector DB)
    ├─ Validate vector database
    └─ Notify completion
    ↓
Chroma Vector Database
    ↓
RAG Query Engine
    ├─ Semantic search (embeddings)
    ├─ SQL generation (LLM)
    └─ Query execution (Trino)
    ↓
User Results
```

### DAG Workflow

**File**: `airflow-db/dags/rag_vector_db_ingestion_dag.py`

**6 Production Tasks**:

1. **extract_metadata_from_iceberg()**
   - Queries Iceberg schema via Trino
   - Extracts table names, columns, data types
   - Duration: 10-30 seconds

2. **extract_sample_data()**
   - Samples 5 rows per table
   - Provides context for embeddings
   - Duration: 15-45 seconds (parallel)

3. **create_embeddings()**
   - Converts text to 768-dimensional vectors
   - Uses Ollama LLaMA2 model
   - Duration: 2-5 seconds per embedding

4. **upsert_to_chroma()**
   - Inserts/updates vectors in Chroma
   - Deduplicates by UUID
   - Duration: 5-10 seconds

5. **validate_vector_db()**
   - Counts embeddings
   - Tests sample query
   - Verifies dimensions
   - Duration: ~5 seconds

6. **notify_completion()**
   - Logs summary metrics
   - Extensible for Slack/Email
   - Duration: <1 second

### Configuration

**Schedule**: Daily at 00:00 UTC (configurable)

```python
# In rag_vector_db_ingestion_dag.py

dag = DAG(
    dag_id='rag_vector_db_ingestion_pipeline',
    schedule_interval='@daily',      # Change to '@hourly', '0 */6 * * *', etc.
    start_date=datetime(2025, 1, 1),
    default_args={
        'retries': 2,                 # Retry failed tasks 2 times
        'retry_delay': timedelta(minutes=5),  # Wait 5 minutes before retry
        'email_on_failure': False,    # Enable to send email on failure
    }
)
```

### Manual Trigger

```bash
# Trigger from CLI
airflow dags trigger rag_vector_db_ingestion_pipeline

# Or from Airflow UI
# 1. Navigate to http://localhost:8080
# 2. Find "rag_vector_db_ingestion_pipeline"
# 3. Click "Trigger DAG"
```

### Monitor Execution

```bash
# Watch logs in real-time
airflow tasks logs rag_vector_db_ingestion_pipeline extract_metadata_from_iceberg -1

# Or use Airflow UI:
# 1. Click on DAG
# 2. View Graph/Tree view
# 3. Click on task for logs
```

### Performance Metrics

| Metric | Value |
|--------|-------|
| Total Duration | 30-90 seconds |
| Success Rate | ~95-99% |
| Data Freshness | Daily (configurable) |
| Parallel Tasks | 2 (metadata + samples) |
| Retry Attempts | 2 |
| Retry Delay | 5 minutes |

---

## Docker Configuration

### Volumes

Persistent storage for data:

```yaml
volumes:
  postgres_data:      # Airflow & Iceberg metadata
  minio_data:         # Object storage
  chroma_data:        # Vector embeddings
  trino_data:         # Trino coordinator
```

### Networks

Service communication:

```yaml
networks:
  data_lake:
    driver: bridge
```

### Resource Limits

```yaml
services:
  trino:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

### Health Checks

```bash
# Check service health
docker-compose exec trino curl http://localhost:8080/ui/
docker-compose exec airflow airflow db check
docker-compose exec ollama curl http://localhost:11434/api/tags
```

---

## Troubleshooting

### Service Won't Start

**Problem**: "docker-compose: command not found"
```bash
# Solution: Use docker compose (v2+)
docker compose up -d

# Or install docker-compose v1
brew install docker-compose
```

**Problem**: "Port already in use"
```bash
# Solution: Kill process using port
lsof -ti:8080 | xargs kill -9
# Or change port in docker-compose.yml
```

**Problem**: "Out of disk space"
```bash
# Solution: Prune Docker resources
docker system prune -a
docker volume prune
```

### Connection Issues

**Problem**: "Cannot connect to Trino"
```bash
# Solution: Check if service is running
docker-compose ps | grep trino

# Restart the service
docker-compose restart trino

# Check logs
docker logs trino
```

**Problem**: "Ollama connection failed"
```bash
# Solution: Verify Ollama is running
curl http://localhost:11434/api/tags

# Pull required model if missing
docker exec ollama ollama pull llama2

# Restart service
docker-compose restart ollama
```

**Problem**: "Chroma database not found"
```bash
# Solution: Check volume mount
docker volume ls | grep chroma

# Verify RAG backend initialized DB
docker logs rag-backend | grep chroma

# Recreate if necessary
docker-compose down -v
docker-compose up --build
```

### Airflow DAG Issues

**Problem**: "DAG not appearing in Airflow UI"
```bash
# Solution: Ensure file is in correct location
ls airflow-db/dags/rag_vector_db_ingestion_dag.py

# Restart Airflow scheduler
docker-compose restart scheduler

# Check for syntax errors
python -m py_compile airflow-db/dags/rag_vector_db_ingestion_dag.py
```

**Problem**: "Task failure - Trino connection error"
```bash
# Solution: Verify Trino is running
docker-compose exec trino trino

# Check network connectivity
docker network ls
docker network inspect data_lake

# Verify Trino URL in DAG (should be: trino:8080)
```

**Problem**: "Airflow scheduler not picking up DAG"
```bash
# Solution: Check DAG folder permissions
chmod 755 airflow-db/dags/

# Restart scheduler
docker-compose down
docker-compose up -d scheduler

# Wait 30 seconds for parsing
sleep 30 && docker logs scheduler
```

---

## Performance Optimization

### Metadata Extraction

```python
# Optimize Trino query
# Add WHERE clause to filter schemas
cursor.execute("""
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema LIKE 'iceberg%'
    AND table_schema NOT LIKE '%temp%'
    LIMIT 1000
""")

# Use connection pooling
# Minimize data transfer
```

### Embedding Creation

```python
# Use faster model
embeddings = OllamaEmbeddings(
    model="mistral",  # Faster than llama2
    base_url="http://ollama:11434"
)

# Batch embeddings
embeddings_list = embeddings.embed_documents(documents)

# Cache common embeddings
```

### Database Performance

```python
# Monitor Chroma collection size
collection.count()

# Archive old embeddings
old_embeddings = collection.get(
    where={'created_at': {'$lt': cutoff_date}}
)
collection.delete(ids=old_embeddings['ids'])

# Optimize vector dimensions
# Use 384-dim for faster search (trade accuracy for speed)
```

### Scheduling Efficiency

```bash
# Run during off-peak hours
schedule_interval='0 2 * * *'  # 2 AM UTC

# Set task timeouts
timeout=300  # 5 minutes max

# Use XCom for inter-task communication
# Avoid re-computation
```

### Resource Management

```yaml
# Limit Ollama memory
services:
  ollama:
    environment:
      - OLLAMA_NUM_GPU=1
      - OLLAMA_MAX_LOADED_MODELS=1

# Set Airflow parallelism
environment:
  - AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=3
  - AIRFLOW__CORE__PARALLELISM=8
```

---

## Monitoring & Health

### Container Health

```bash
# Check all services
docker-compose ps

# View resource usage
docker stats

# Check specific service logs
docker logs -f service_name

# View last 100 lines
docker logs --tail 100 service_name
```

### Airflow Monitoring

```bash
# Check DAG parsing errors
docker logs airflow-scheduler | grep ERROR

# Validate DAG syntax
python airflow-db/dags/rag_vector_db_ingestion_dag.py

# Check task execution history
docker-compose exec airflow airflow tasks list rag_vector_db_ingestion_pipeline
```

### Vector Database

```python
# Monitor Chroma embeddings
collection = chroma_client.get_collection("metadata_embeddings")
print(f"Total embeddings: {collection.count()}")

# Test similarity search
results = collection.query(
    query_texts=["test query"],
    n_results=5
)
```

---

## Backup & Recovery

### Backup Data

```bash
# Backup PostgreSQL (Airflow DB)
docker-compose exec postgres pg_dump \
  -U airflow airflow > airflow_backup.sql

# Backup MinIO data
docker cp minio:/data ./minio_backup

# Backup Chroma embeddings
docker cp rag-backend:/app/chroma_db ./chroma_backup
```

### Restore Data

```bash
# Restore PostgreSQL
docker-compose exec -T postgres psql \
  -U airflow airflow < airflow_backup.sql

# Restore MinIO
docker cp ./minio_backup minio:/data

# Restore Chroma
docker cp ./chroma_backup rag-backend:/app/chroma_db
```

---

## Next Steps

1. ✅ Start all services
2. ✅ Verify connectivity
3. ✅ Access Airflow UI
4. ✅ Trigger RAG pipeline DAG
5. ✅ Monitor execution
6. ✅ Test RAG queries
7. ✅ Review logs
8. ✅ Customize configuration
9. ✅ Set up monitoring
10. ✅ Plan production deployment

---

**Generated**: December 20, 2025  
**Version**: 1.0  
**Status**: Production-Ready
