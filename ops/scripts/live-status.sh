#!/bin/bash

# Real-time Pipeline Status Tracker
# Shows live status of DAG execution

cd "/Users/prakashsaini/Documents/Projects/Data Engineer/datalake-project"

AIRFLOW_URL="http://localhost:9093"
DAG_ID="document_rag_ingestion_pipeline"

echo "📊 REAL-TIME PIPELINE STATUS"
echo "============================"
echo ""

# Poll for DAG status
for i in {1..30}; do
    clear
    echo "📊 REAL-TIME PIPELINE EXECUTION MONITOR"
    echo "======================================="
    echo "Polling interval: ${i}s"
    echo ""
    
    # Get DAG run
    DAG_RUN=$(curl -s -u "airflow:airflow" \
        "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns?limit=1" \
        -H "Content-Type: application/json")
    
    STATE=$(echo "$DAG_RUN" | grep -o '"state":"[^"]*' | cut -d'"' -f4 | head -1)
    DAG_RUN_ID=$(echo "$DAG_RUN" | grep -o '"dag_run_id":"[^"]*' | cut -d'"' -f4 | head -1)
    START_DATE=$(echo "$DAG_RUN" | grep -o '"start_date":"[^"]*' | cut -d'"' -f4 | head -1)
    END_DATE=$(echo "$DAG_RUN" | grep -o '"end_date":"[^"]*' | cut -d'"' -f4 | head -1)
    
    echo "Run ID: $DAG_RUN_ID"
    echo "State:  $STATE"
    echo "Start:  $START_DATE"
    echo "End:    $END_DATE"
    echo ""
    
    # Task status
    echo "📋 TASK EXECUTION:"
    curl -s -u "airflow:airflow" \
        "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns/$DAG_RUN_ID/taskInstances" \
        -H "Content-Type: application/json" 2>/dev/null | \
        grep -o '"task_id":"[^"]*\|"state":"[^"]*' | \
        paste - - | sed 's/"task_id":"/  📌 /;s/"state":","/: /;s/"//g'
    
    echo ""
    
    # Check for success
    if [ "$STATE" = "success" ]; then
        echo "✨ PIPELINE COMPLETED SUCCESSFULLY! ✨"
        echo ""
        echo "✅ All tasks executed:"
        echo "   1. ✓ Fetched documents from MinIO"
        echo "   2. ✓ Processed documents"
        echo "   3. ✓ Generated embeddings"
        echo "   4. ✓ Upserted to Chroma"
        echo "   5. ✓ Validated vector DB"
        echo "   6. ✓ Notified completion"
        echo ""
        echo "🎉 Your documents are now searchable!"
        break
    elif [ "$STATE" = "failed" ]; then
        echo "❌ PIPELINE FAILED!"
        echo ""
        echo "Check logs at: $AIRFLOW_URL/log?dag_id=$DAG_ID"
        break
    fi
    
    # Increment counter
    i=$((i + 1))
    
    # Wait before next poll
    if [ $i -lt 30 ]; then
        sleep 2
    fi
done

echo ""
echo "📍 Access your data:"
echo "   - Airflow UI: $AIRFLOW_URL (airflow:airflow)"
echo "   - Chroma API: http://localhost:8001/api/v2"
echo "   - FastAPI: http://localhost:8000/docs"
echo "   - Frontend: http://localhost:3000"
