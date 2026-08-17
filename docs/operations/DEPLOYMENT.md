# Deployment Guide

## Overview

This guide covers deploying the DataLake RAG system across different environments (development, staging, production).

## Development Deployment

### Prerequisites
- Docker Desktop (24+) with 4GB RAM minimum
- Docker Compose (2.20+)
- macOS/Linux/Windows with WSL2

### Quick Start

```bash
cd datalake-project
./ops/scripts/start.sh
```

This will:
1. Build all Docker images
2. Create networks and volumes
3. Start all services
4. Initialize databases
5. Display service endpoints

### Service Endpoints (Development)
- Frontend: http://localhost:3000
- RAG API: http://localhost:8000
- Airflow Web: http://localhost:9093
- Airflow Flower: http://localhost:5555
- MinIO Console: http://localhost:9001
- Chroma: http://localhost:8001
- API Docs: http://localhost:8000/docs

### Default Credentials (Development Only)
```
Airflow Admin:
  User: airflow
  Password: airflow

MinIO:
  Access Key: minioadmin
  Secret: minioadmin

PostgreSQL:
  User: airflow
  Password: airflow
```

### First Time Setup

1. **Upload Sample Documents**
   ```bash
   # Upload to MinIO
   curl -X POST http://localhost:9000/documents/sample.txt \
     -H "Authorization: AWS4-HMAC-SHA256 ..." \
     --data-binary @sample.txt
   ```

2. **Trigger Initial Pipeline**
   - Navigate to Airflow: http://localhost:9093
   - Find DAG: `document_rag_ingestion_pipeline`
   - Click "Trigger DAG"
   - Monitor execution in Airflow UI

3. **Test Search Query**
   ```bash
   curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "What is the main topic?"}'
   ```

## Staging Deployment

### Environment Setup

1. **Create Staging .env**
   ```bash
   cp .env.example .env.staging
   ```

2. **Configure Staging Values**
   ```env
   ENVIRONMENT=staging
   DEBUG=false
   LOG_LEVEL=info
   
   # SSL/TLS
   ENABLE_HTTPS=true
   SSL_CERT_PATH=/etc/certs/staging.crt
   SSL_KEY_PATH=/etc/certs/staging.key
   
   # Resources
   AIRFLOW_WORKERS=2
   CHROMA_WORKERS=4
   
   # Monitoring
   ENABLE_MONITORING=true
   ```

3. **Start Services**
   ```bash
   docker-compose -f docker-compose.yml \
     --env-file .env.staging up -d
   ```

### Health Checks

```bash
# Check all services
./ops/scripts/health-check.sh

# Expected output:
# ✓ Frontend: http://localhost:3000
# ✓ RAG API: http://localhost:8000
# ✓ Airflow: http://localhost:9093
# ✓ MinIO: http://localhost:9000
# ✓ Chroma: http://localhost:8001
# ✓ PostgreSQL: reachable
# ✓ Redis: reachable
# ✓ Ollama: reachable
```

### Monitoring

Access monitoring dashboard:
```bash
# Airflow Flower (Task monitoring)
http://localhost:5555

# Custom dashboard (optional)
http://localhost:8002/dashboard
```

## Production Deployment

### Architecture

```
┌─────────────────────────────────────────────────┐
│         Production Environment                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │  Load Balancer (Nginx/HAProxy)         │    │
│  │  - SSL/TLS termination                 │    │
│  │  - Request distribution                │    │
│  │  - Rate limiting                       │    │
│  └────────────────────────────────────────┘    │
│                    ▼                            │
│  ┌────────────────────────────────────────┐    │
│  │  Kubernetes Cluster                    │    │
│  │  - Multiple API replicas               │    │
│  │  - Auto-scaling                        │    │
│  │  - Self-healing                        │    │
│  └────────────────────────────────────────┘    │
│           ▼          ▼          ▼              │
│  ┌──────────────────────────────────────┐     │
│  │  Persistent Storage                  │     │
│  │  - S3 (MinIO/AWS)                   │     │
│  │  - Database (RDS/Managed)           │     │
│  │  - Vector DB (Dedicated cluster)    │     │
│  │  - Volumes (EBS/persistent volumes) │     │
│  └──────────────────────────────────────┘     │
│                                                  │
│  ┌──────────────────────────────────────┐     │
│  │  Monitoring & Logging                │     │
│  │  - Prometheus metrics                │     │
│  │  - ELK Stack logging                 │     │
│  │  - Alerting (PagerDuty)             │     │
│  └──────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

### Kubernetes Manifests

Create `k8s/` directory structure:

```
k8s/
├── namespaces.yaml
├── secrets.yaml
├── configmaps.yaml
├── services/
│   ├── api.yaml
│   ├── frontend.yaml
│   ├── airflow.yaml
│   └── infrastructure.yaml
├── volumes/
│   └── persistent-volumes.yaml
├── monitoring/
│   ├── prometheus.yaml
│   └── grafana.yaml
└── ingress/
    └── nginx-ingress.yaml
```

### Deployment Steps

1. **Set up Kubernetes Cluster**
   ```bash
   # AWS EKS
   eksctl create cluster --name datalake-prod \
     --region us-east-1 --nodes 3 --node-type t3.xlarge
   
   # GCP GKE
   gcloud container clusters create datalake-prod \
     --zone us-central1-a --num-nodes 3
   ```

2. **Install Required Add-ons**
   ```bash
   # Helm
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm repo update
   
   # Prometheus (Monitoring)
   helm install prometheus bitnami/prometheus
   
   # Loki (Logging)
   helm install loki bitnami/loki-stack
   ```

3. **Create Secrets**
   ```bash
   kubectl create secret generic airflow-credentials \
     --from-literal=user=airflow-prod \
     --from-literal=password=<strong-password>
   
   kubectl create secret generic minio-credentials \
     --from-literal=access-key=<key> \
     --from-literal=secret-key=<secret>
   ```

4. **Deploy Services**
   ```bash
   # Apply manifests
   kubectl apply -f k8s/namespaces.yaml
   kubectl apply -f k8s/secrets.yaml
   kubectl apply -f k8s/configmaps.yaml
   kubectl apply -f k8s/volumes/
   kubectl apply -f k8s/services/
   kubectl apply -f k8s/ingress/
   
   # Verify deployment
   kubectl get pods -n datalake
   kubectl get svc -n datalake
   ```

5. **Configure Auto-Scaling**
   ```bash
   # Horizontal Pod Autoscaler
   kubectl autoscale deployment api-server \
     --min=3 --max=10 \
     --cpu-percent=70 -n datalake
   ```

6. **Set up Monitoring**
   ```bash
   # Access Prometheus
   kubectl port-forward -n monitoring svc/prometheus 9090:9090
   
   # Access Grafana
   kubectl port-forward -n monitoring svc/grafana 3000:3000
   ```

### Production Configuration

#### Environment Variables
```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=warn

# Security
CORS_ORIGINS=https://app.example.com
ALLOWED_HOSTS=app.example.com,api.example.com

# Database
DATABASE_URL=postgresql://user:pass@managed-db.example.com:5432/datalake
DATABASE_POOL_SIZE=20

# Storage
MINIO_ENDPOINT=s3.example.com
MINIO_USE_SSL=true

# LLM
OLLAMA_ENDPOINT=http://ollama-service:11434
OLLAMA_MODEL=nomic-embed-text

# Airflow
AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=60
AIRFLOW__CORE__PARALLELISM=32
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=2
```

#### Resource Limits
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

### Health Checks & Monitoring

1. **Application Health Endpoint**
   ```python
   GET /health
   Response: {
     "status": "healthy",
     "services": {
       "database": "connected",
       "cache": "connected",
       "vector_db": "connected"
     },
     "timestamp": "2025-01-10T10:00:00Z"
   }
   ```

2. **Liveness Probe**
   ```yaml
   livenessProbe:
     httpGet:
       path: /health
       port: 8000
     initialDelaySeconds: 30
     periodSeconds: 10
   ```

3. **Readiness Probe**
   ```yaml
   readinessProbe:
     httpGet:
       path: /health/ready
       port: 8000
     initialDelaySeconds: 10
     periodSeconds: 5
   ```

## Backup & Disaster Recovery

### Backup Strategy

```bash
# Daily backups at 02:00 UTC
0 2 * * * /scripts/backup-all.sh

# Backup destinations
- S3 bucket: datalake-backups-prod
- Retention: 30 days
- Frequency: Daily, Weekly, Monthly snapshots
```

### Recovery Procedure

```bash
# 1. Stop services
kubectl scale deployment --replicas=0 -n datalake

# 2. Restore from backup
aws s3 cp s3://datalake-backups-prod/snapshot-2025-01-10.tar.gz .
tar -xzf snapshot-2025-01-10.tar.gz

# 3. Restore databases
psql < backup/database.sql

# 4. Restore volumes
aws ebs create-volume --snapshot-id snap-xxxxx

# 5. Restart services
kubectl scale deployment --replicas=3 -n datalake

# 6. Verify
./ops/scripts/health-check.sh
```

## Rolling Updates

```bash
# 1. Update deployment image
kubectl set image deployment/api-server \
  api-server=myregistry/datalake-api:v2.0.0 \
  -n datalake

# 2. Monitor rollout
kubectl rollout status deployment/api-server -n datalake

# 3. If issues, rollback
kubectl rollout undo deployment/api-server -n datalake
```

## Troubleshooting

### Service Not Starting
```bash
# Check pod status
kubectl describe pod <pod-name> -n datalake

# View logs
kubectl logs <pod-name> -n datalake

# Check resource availability
kubectl top nodes
kubectl describe node <node-name>
```

### High Memory Usage
```bash
# Check memory metrics
kubectl top pod -n datalake

# Identify problematic pods
kubectl get pods -n datalake --sort-by=.spec.containers[0].resources.limits.memory

# Increase limits or scale horizontally
```

### Database Connection Issues
```bash
# Test connectivity
kubectl run -it --rm debug --image=busybox -- /bin/sh
# nc -zv postgres-service 5432
# mysql -h postgres-service -u user -p
```

---

Next Steps:
1. Configure CI/CD pipeline for automated deployments
2. Set up infrastructure-as-code (Terraform/Helm)
3. Implement cost optimization
4. Plan disaster recovery drills
