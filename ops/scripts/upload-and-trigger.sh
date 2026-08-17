#!/bin/bash

# MinIO Document Upload and Pipeline Trigger Script
# This script uploads documents to MinIO and triggers the Airflow RAG ingestion pipeline

set -e

echo "📦 MinIO Document Upload & Airflow Pipeline Trigger"
echo "===================================================="

# Configuration
MINIO_HOST="localhost:9000"
MINIO_ROOT_USER="minioadmin"
MINIO_ROOT_PASSWORD="minioadmin"
BUCKET_NAME="documents"
AIRFLOW_API="http://localhost:9093"
AIRFLOW_USER="airflow"
AIRFLOW_PASS="airflow"
DAG_ID="document_rag_ingestion_pipeline"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[i] $1${NC}"
}

# Step 1: Create sample documents
print_status "Creating sample documents..."

mkdir -p /tmp/sample_docs

cat > /tmp/sample_docs/sample1.txt << 'EOF'
# Machine Learning Basics

Machine learning is a subset of artificial intelligence that enables 
systems to learn and improve from experience without being explicitly programmed.

## Key Concepts
- Supervised Learning: Learning from labeled data
- Unsupervised Learning: Finding patterns in unlabeled data
- Reinforcement Learning: Learning through interaction with environment

## Popular Algorithms
1. Linear Regression
2. Logistic Regression
3. Decision Trees
4. Random Forests
5. Support Vector Machines
6. Neural Networks

Machine learning applications are everywhere - from recommendation systems 
to autonomous vehicles to natural language processing.
EOF

cat > /tmp/sample_docs/sample2.txt << 'EOF'
# Cloud Computing Architecture

Cloud computing provides on-demand access to computing resources 
over the internet, eliminating the need for local infrastructure.

## Cloud Service Models
- IaaS (Infrastructure as a Service): Virtual machines, storage, networking
- PaaS (Platform as a Service): Application development frameworks
- SaaS (Software as a Service): Ready-to-use applications

## Major Cloud Providers
- Amazon Web Services (AWS)
- Microsoft Azure
- Google Cloud Platform (GCP)
- IBM Cloud

## Benefits of Cloud Computing
1. Cost-effective: Pay-as-you-go pricing
2. Scalability: Easy to scale resources up or down
3. Reliability: Built-in redundancy and backup
4. Security: Enterprise-grade security measures
5. Flexibility: Access from anywhere, anytime
EOF

cat > /tmp/sample_docs/sample3.txt << 'EOF'
# Data Science and Analytics

Data science combines domain expertise, programming skills, and 
statistical knowledge to extract meaningful insights from data.

## Data Science Process
1. Data Collection: Gathering raw data from various sources
2. Data Cleaning: Removing inconsistencies and errors
3. Exploratory Data Analysis: Understanding data patterns
4. Feature Engineering: Creating relevant features
5. Model Building: Training machine learning models
6. Model Evaluation: Assessing model performance
7. Deployment: Putting models into production
8. Monitoring: Tracking model performance over time

## Tools and Technologies
- Python: numpy, pandas, scikit-learn, tensorflow
- R: dplyr, ggplot2, caret
- SQL: Data querying and manipulation
- Apache Spark: Big data processing
- Tableau/PowerBI: Data visualization

Data-driven decision making is crucial for modern businesses 
to stay competitive in their respective markets.
EOF

print_success "Sample documents created"

# Step 2: Install minio CLI if not present
print_status "Checking for MinIO CLI..."

if ! command -v mc &> /dev/null; then
    print_info "Installing MinIO CLI (mc)..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install minio/stable/mc 2>/dev/null || {
            # Download directly
            curl -s https://dl.min.io/client/mc/release/darwin-amd64/mc -o /usr/local/bin/mc
            chmod +x /usr/local/bin/mc
        }
    else
        # Linux
        curl -s https://dl.min.io/client/mc/release/linux-x64/mc -o /usr/local/bin/mc
        chmod +x /usr/local/bin/mc
    fi
    
    print_success "MinIO CLI installed"
else
    print_success "MinIO CLI found"
fi

# Step 3: Configure MinIO alias
print_status "Configuring MinIO alias..."

# Remove old alias if exists
mc alias remove minio 2>/dev/null || true

# Create new alias
mc alias set minio http://$MINIO_HOST $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD --api s3v4

print_success "MinIO alias configured"

# Step 4: Create bucket if it doesn't exist
print_status "Creating MinIO bucket: $BUCKET_NAME..."

if mc ls minio/$BUCKET_NAME > /dev/null 2>&1; then
    print_success "Bucket already exists"
else
    mc mb minio/$BUCKET_NAME
    print_success "Bucket created"
fi

# Step 5: Upload documents
print_status "Uploading sample documents to MinIO..."

for doc in /tmp/sample_docs/*.txt; do
    filename=$(basename "$doc")
    print_info "Uploading: $filename"
    mc cp "$doc" "minio/$BUCKET_NAME/$filename"
done

print_success "Documents uploaded successfully"

# Step 6: Verify uploads
print_status "Verifying uploaded documents..."

uploaded_count=$(mc ls minio/$BUCKET_NAME | wc -l)
print_success "Total documents in bucket: $((uploaded_count - 1))" # -1 for header

# Step 7: List uploaded documents
print_info "Uploaded documents:"
mc ls minio/$BUCKET_NAME | tail -n +2

# Step 8: Trigger Airflow DAG
print_status "Triggering Airflow DAG: $DAG_ID..."

# Check if DAG exists
dag_status=$(curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
    "$AIRFLOW_API/api/v1/dags/$DAG_ID" \
    -H "Content-Type: application/json" \
    | grep -c "is_active" || echo "0")

if [ "$dag_status" -gt 0 ]; then
    # Trigger the DAG
    dag_run=$(curl -s -X POST \
        -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
        "$AIRFLOW_API/api/v1/dags/$DAG_ID/dagRuns" \
        -H "Content-Type: application/json" \
        -d '{}')
    
    print_success "DAG triggered successfully"
    print_info "DAG Run Response: $dag_run"
    
    # Extract run ID if available
    run_id=$(echo "$dag_run" | grep -oP '"dag_run_id":"?\K[^,"]*' || echo "Check UI")
    print_info "DAG Run ID: $run_id"
else
    print_error "DAG not found. Please check if document_rag_ingestion_pipeline exists"
    print_info "Available DAGs at: $AIRFLOW_API/home"
fi

echo ""
echo "✨ Upload and Pipeline Trigger Complete!"
echo "========================================"
echo ""
echo "📊 Next Steps:"
echo "============"
echo "1. Check MinIO Console: http://localhost:9001"
echo "   - Username: minioadmin"
echo "   - Password: minioadmin"
echo "   - Bucket: $BUCKET_NAME"
echo ""
echo "2. Monitor Airflow DAG: $AIRFLOW_API"
echo "   - Username: $AIRFLOW_USER"
echo "   - Password: $AIRFLOW_PASS"
echo "   - DAG: $DAG_ID"
echo ""
echo "3. Check Chroma Vector DB for indexed documents:"
echo "   - curl http://localhost:8001/api/v2/collections"
echo ""
echo "4. Search documents in RAG Engine:"
echo "   - GUI: http://localhost:3000"
echo "   - API: http://localhost:8000/docs"
echo ""
echo "📝 Pipeline Stages:"
echo "=================="
echo "1. Extract: Read documents from MinIO"
echo "2. Process: Parse and chunk documents"
echo "3. Embed: Generate embeddings using Ollama"
echo "4. Upsert: Store in Chroma Vector DB"
echo "5. Validate: Verify data integrity"
