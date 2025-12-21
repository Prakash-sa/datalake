# Production Deployment Guide

## Overview

This guide covers deploying the Document RAG Engine to production with:
- Multi-worker FastAPI server (Gunicorn + Uvicorn)
- Resource limits and health checks
- Monitoring with Prometheus + Grafana
- Security best practices
- High availability configuration

## Prerequisites

- Docker & Docker Compose
- 2+ CPU cores and 4GB RAM minimum
- Environment variables configured
- SSL certificates (for HTTPS)

## Quick Start (Production)

### 1. Configure Environment

```bash
# Copy production environment file
cp backend/.env.production backend/.env

# Edit with your production values
nano backend/.env

# Set critical variables:
export ENV=production
export LOG_LEVEL=INFO
export WORKERS=4
export ALLOWED_ORIGINS=https://yourdomain.com
export MINIO_ROOT_PASSWORD=your-secure-password
export LLM_TEMPERATURE=0.3
```

### 2. Deploy with Docker Compose

```bash
# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Verify all services are healthy
docker-compose -f docker-compose.prod.yml ps

# Check service logs
docker-compose -f docker-compose.prod.yml logs -f rag-backend
```

### 3. Verify Deployment

```bash
# Health check
curl https://your-domain.com/health

# API status
curl https://your-domain.com/

# Server metrics
curl http://localhost:9090/metrics

# View logs
docker-compose -f docker-compose.prod.yml logs rag-backend
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Client / Frontend                      │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐           ┌────▼────┐
    │  Nginx   │           │Prometheus│
    │ (Reverse │           │(Metrics) │
    │  Proxy)  │           └──────────┘
    └────┬─────┘
         │
┌────────▼──────────────────────────────────┐
│  FastAPI (Gunicorn + 4 Uvicorn Workers)   │
│  - Multi-process for parallelism          │
│  - Automatic request distribution         │
│  - Health checks every 30s                │
└────────┬──────────────────────────────────┘
         │
    ┌────┴────────────┬─────────────┐
    │                 │             │
┌───▼────────┐ ┌────▼──────┐ ┌────▼──┐
│  Ollama    │ │   MinIO   │ │Chroma│
│ (LLM)      │ │(Storage)  │ │(VDB) │
└────────────┘ └───────────┘ └──────┘
```

## Security Best Practices

### 1. Network Security

```yaml
# Use restricted CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Enable HTTPS with reverse proxy (Nginx)
# Put Nginx in front with SSL termination
```

### 2. Authentication (Recommended Add-on)

```python
# Add JWT authentication in main.py
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

@app.post("/query")
async def query_documents(
    request: DocumentQueryRequest,
    credentials: HTTPAuthCredentials = Depends(security)
):
    # Validate token
    pass
```

### 3. Rate Limiting

```python
# Add SlowAPI for rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/query")
@limiter.limit("100/minute")
async def query_documents(request):
    pass
```

### 4. Resource Limits

```yaml
# In docker-compose.prod.yml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

## Monitoring & Observability

### 1. Prometheus Metrics

```bash
# Access metrics
curl http://localhost:9090/metrics

# Key metrics to monitor:
# - http_requests_total
# - http_request_duration_seconds
# - rag_documents_indexed_total
# - rag_queries_processed_total
# - rag_errors_total
```

### 2. Grafana Dashboards

```bash
# Access Grafana
http://localhost:3001
# Default: admin / admin

# Create dashboard queries:
# - Request rate: rate(http_requests_total[5m])
# - Error rate: rate(rag_errors_total[5m])
# - Response time: histogram_quantile(0.95, http_request_duration_seconds)
```

### 3. Log Aggregation

```bash
# Structured logging to file
docker-compose -f docker-compose.prod.yml logs --tail=100 rag-backend

# For production, integrate with:
# - ELK Stack (Elasticsearch, Logstash, Kibana)
# - Splunk
# - DataDog
# - CloudWatch (if using AWS)
```

## Performance Tuning

### 1. Gunicorn Workers

```bash
# Formula: workers = (2 * CPU_cores) + 1
# For 4-core server: 9 workers
WORKERS=9
```

### 2. Ollama Performance

```bash
# Increase thread count for inference
OLLAMA_NUM_THREAD=8
OLLAMA_NUM_GPU=1  # Use GPU if available
```

### 3. Memory Management

```bash
# Set Ollama memory limits
docker run -e OLLAMA_MAX_LOADED_MODELS=2 ollama/ollama
```

## Scaling Strategies

### Horizontal Scaling

```yaml
# Run multiple backend instances with load balancer
services:
  rag-backend-1:
    # Port: 8001
  rag-backend-2:
    # Port: 8002
  rag-backend-3:
    # Port: 8003
  
  nginx:
    # Load balance traffic across instances
```

### Kubernetes Deployment

```yaml
# Deploy with HPA (Horizontal Pod Autoscaler)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Backup & Recovery

### 1. Backup Strategy

```bash
# Backup MinIO data
docker exec minio-prod mc mirror minio/data /backup/minio

# Backup configuration
docker exec minio-prod mc config export backup

# Backup Ollama models
docker exec ollama-prod tar -czf /backup/ollama.tar.gz /root/.ollama
```

### 2. Disaster Recovery

```bash
# Restore from backup
docker exec minio-prod mc mirror /backup/minio minio/data
docker exec ollama-prod tar -xzf /backup/ollama.tar.gz -C /root
```

## Maintenance

### 1. Regular Updates

```bash
# Check for updates
docker pull ollama/ollama:latest
docker pull minio/minio:latest

# Update production services
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### 2. Health Checks

```bash
# Automated health monitoring
curl -f http://localhost:8000/health || alert "Backend unhealthy"
curl -f http://localhost:11434/api/tags || alert "Ollama unhealthy"
curl -f http://minio:9000/minio/health/live || alert "MinIO unhealthy"
```

### 3. Performance Monitoring

```bash
# Monitor query performance
# Slow queries > 5s should trigger investigation
curl http://localhost:9090/api/v1/query?query=http_request_duration_seconds

# Monitor error rates
# Error rate > 1% indicates issues
curl http://localhost:9090/api/v1/query?query=rate(rag_errors_total[5m])
```

## Troubleshooting

### Container Issues

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# View logs for specific service
docker-compose -f docker-compose.prod.yml logs rag-backend

# Restart unhealthy service
docker-compose -f docker-compose.prod.yml restart rag-backend
```

### Memory Issues

```bash
# Monitor memory usage
docker stats rag-backend

# Increase memory limit if needed
# Edit docker-compose.prod.yml and restart
```

### Network Issues

```bash
# Verify service connectivity
docker-compose -f docker-compose.prod.yml exec rag-backend \
  curl -f http://ollama:11434/api/tags

docker-compose -f docker-compose.prod.yml exec rag-backend \
  curl -f http://minio:9000/minio/health/live
```

## Production Checklist

- [ ] Environment variables configured
- [ ] SSL/TLS certificates installed
- [ ] CORS allowed origins configured
- [ ] Database backups scheduled
- [ ] Monitoring & alerting configured
- [ ] Log aggregation setup
- [ ] Resource limits set
- [ ] Health checks verified
- [ ] Load testing completed
- [ ] Disaster recovery tested
- [ ] Security audit completed
- [ ] Documentation updated

## Support & Troubleshooting

For issues or questions:
1. Check logs: `docker-compose logs rag-backend`
2. Review metrics: `http://localhost:9090`
3. Check health: `curl http://localhost:8000/health`
4. Verify connectivity: `docker-compose exec rag-backend ping ollama`

---

**Status**: ✅ Production-ready for deployment
**Version**: 2.0.0
**Last Updated**: 2024
