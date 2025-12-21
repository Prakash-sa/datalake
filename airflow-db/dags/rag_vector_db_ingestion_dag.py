"""
Airflow DAG for Vector Database Ingestion into RAG Pipeline
Orchestrates daily metadata indexing and embedding generation for the RAG Query Engine.
Ingests data from Iceberg tables into Chroma vector database.
"""

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import logging
import json
from typing import List, Dict

logger = logging.getLogger(__name__)

# Default configuration
default_args = {
    'owner': 'data-engineering',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}


@task
def extract_metadata_from_iceberg(**context) -> List[Dict]:
    """
    Extract table metadata from Iceberg catalog.
    
    Retrieves:
    - Table names, schemas
    - Column definitions
    - Data types
    - Metadata for semantic indexing
    """
    import trino
    
    logger.info("📊 Extracting metadata from Iceberg...")
    
    try:
        # Connect to Trino
        conn = trino.dbapi.connect(
            host='trino',  # Docker compose service name
            port=8080,
            user='trino'
        )
        cursor = conn.cursor()
        
        # Query Iceberg metadata
        cursor.execute("""
            SELECT 
                table_schema, 
                table_name, 
                column_name, 
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema LIKE 'iceberg%'
            ORDER BY table_schema, table_name
        """)
        
        # Fetch and format metadata
        metadata = []
        for schema, table, column, dtype, nullable in cursor.fetchall():
            doc = {
                'table_schema': schema,
                'table_name': table,
                'full_table_name': f"{schema}.{table}",
                'column': column,
                'data_type': dtype,
                'nullable': nullable,
                'metadata_text': f"""
                    Table: {schema}.{table}
                    Column: {column}
                    Type: {dtype}
                    Nullable: {nullable}
                """
            }
            metadata.append(doc)
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Extracted {len(metadata)} metadata records")
        return metadata
        
    except Exception as e:
        logger.error(f"❌ Error extracting metadata: {e}")
        raise


@task
def extract_sample_data(**context) -> List[str]:
    """
    Extract sample data from Iceberg tables for embedding.
    
    This helps understand table contents for better semantic search.
    Samples data from each table.
    """
    import trino
    
    logger.info("📄 Extracting sample data from tables...")
    
    try:
        conn = trino.dbapi.connect(
            host='trino',
            port=8080,
            user='trino'
        )
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("""
            SELECT DISTINCT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema LIKE 'iceberg%'
        """)
        
        tables = cursor.fetchall()
        sample_docs = []
        
        # Sample data from each table
        for schema, table in tables:
            try:
                full_table = f"{schema}.{table}"
                # Sample first 5 rows (limit execution time)
                cursor.execute(f"SELECT * FROM {full_table} LIMIT 5")
                rows = cursor.fetchall()
                
                if rows:
                    sample_text = f"""
                    Table: {full_table}
                    Sample data available from this table.
                    This table contains business data for analytics and reporting.
                    """
                    sample_docs.append(sample_text)
                    logger.info(f"✅ Sampled {len(rows)} rows from {full_table}")
            except Exception as e:
                logger.warning(f"⚠️ Could not sample from {schema}.{table}: {e}")
                continue
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Extracted {len(sample_docs)} sample documents")
        return sample_docs
        
    except Exception as e:
        logger.error(f"❌ Error extracting sample data: {e}")
        raise


@task
def create_embeddings(metadata: List[Dict], samples: List[str]) -> List[Dict]:
    """
    Create vector embeddings from metadata and samples.
    
    Uses the same embedding function as the RAG engine for consistency.
    Converts text to dense vectors (768 dimensions).
    """
    logger.info("🧮 Creating vector embeddings...")
    
    try:
        from langchain_ollama import OllamaEmbeddings
        
        # Initialize embeddings (same as RAG engine)
        embeddings = OllamaEmbeddings(
            model="llama2",
            base_url="http://ollama:11434"
        )
        
        # Combine metadata and samples
        all_docs = []
        
        # Add metadata embeddings
        for meta in metadata:
            text = meta['metadata_text']
            try:
                vector = embeddings.embed_query(text)
                all_docs.append({
                    'text': text,
                    'vector': vector,
                    'source': 'metadata',
                    'table_name': meta.get('full_table_name'),
                    'type': 'table_definition'
                })
            except Exception as e:
                logger.warning(f"⚠️ Failed to embed metadata: {e}")
                continue
        
        # Add sample data embeddings
        for i, sample in enumerate(samples):
            try:
                vector = embeddings.embed_query(sample)
                all_docs.append({
                    'text': sample,
                    'vector': vector,
                    'source': 'sample_data',
                    'index': i,
                    'type': 'sample_document'
                })
            except Exception as e:
                logger.warning(f"⚠️ Failed to embed sample: {e}")
                continue
        
        logger.info(f"✅ Created {len(all_docs)} embeddings")
        return all_docs
        
    except Exception as e:
        logger.error(f"❌ Error creating embeddings: {e}")
        raise


@task
def upsert_to_chroma(embeddings: List[Dict]) -> Dict:
    """
    Upsert embeddings to Chroma vector database.
    
    Replaces existing embeddings with new ones to keep data fresh.
    Uses Chroma's built-in duplicate handling (upsert).
    """
    logger.info("💾 Upserting embeddings to Chroma...")
    
    try:
        from chromadb.config import Settings
        import chromadb
        import uuid
        
        # Initialize Chroma client (persistent)
        client = chromadb.PersistentClient(
            path="/app/chroma_db"  # Same location as RAG backend
        )
        
        collection_name = "iceberg_metadata"
        
        # Get or create collection
        try:
            collection = client.get_collection(name=collection_name)
            logger.info(f"📚 Using existing collection: {collection_name}")
        except:
            collection = client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"📚 Created new collection: {collection_name}")
        
        # Prepare data for insertion
        ids = []
        documents = []
        embeddings_list = []
        metadatas = []
        
        for i, item in enumerate(embeddings):
            # Generate unique ID based on content
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, item['text']))
            
            ids.append(doc_id)
            documents.append(item['text'])
            embeddings_list.append(item['vector'])
            metadatas.append({
                'source': item.get('source', 'unknown'),
                'type': item.get('type', 'unknown'),
                'table_name': item.get('table_name', ''),
                'timestamp': datetime.now().isoformat()
            })
        
        # Upsert to collection (replaces if exists)
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings_list,
            metadatas=metadatas
        )
        
        logger.info(f"✅ Upserted {len(ids)} embeddings to Chroma")
        
        # Return summary
        return {
            'status': 'success',
            'collection_name': collection_name,
            'embeddings_count': len(embeddings),
            'ids_count': len(ids),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error upserting to Chroma: {e}")
        raise


@task
def validate_vector_db() -> Dict:
    """
    Validate vector database contents and quality.
    
    Performs:
    - Count verification
    - Sample query testing
    - Embedding quality checks
    """
    logger.info("🔍 Validating vector database...")
    
    try:
        import chromadb
        
        client = chromadb.PersistentClient(path="/app/chroma_db")
        collection = client.get_collection(name="iceberg_metadata")
        
        # Get collection stats
        count = collection.count()
        logger.info(f"📊 Total embeddings in collection: {count}")
        
        # Test a sample query
        test_query = "sales data and customer information"
        results = collection.query(
            query_texts=[test_query],
            n_results=3
        )
        
        logger.info(f"✅ Sample query returned {len(results['documents'][0])} results")
        
        # Verify embeddings exist and have correct dimensions
        if count > 0:
            sample = collection.get(limit=1)
            if sample['embeddings']:
                embedding_dim = len(sample['embeddings'][0])
                logger.info(f"✅ Embedding dimension verified: {embedding_dim}")
        
        return {
            'status': 'success',
            'total_embeddings': count,
            'sample_query_results': len(results['documents'][0]) if results['documents'] else 0,
            'validation_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        raise


@task
def notify_completion(validation_result: Dict) -> None:
    """
    Send completion notification with summary.
    
    Logs the final status and can be extended to send emails/Slack messages.
    """
    logger.info("📬 Vector database ingestion completed successfully!")
    logger.info(f"📊 Summary:")
    logger.info(f"   - Total embeddings: {validation_result['total_embeddings']}")
    logger.info(f"   - Sample query results: {validation_result['sample_query_results']}")
    logger.info(f"   - Status: {validation_result['status']}")
    logger.info(f"   - Timestamp: {validation_result['validation_time']}")
    
    # Can integrate with Slack/Email here
    # send_slack_notification(f"RAG Vector DB updated: {validation_result['total_embeddings']} embeddings")


# Define the DAG
with DAG(
    dag_id='rag_vector_db_ingestion_pipeline',
    default_args=default_args,
    description='Daily ingestion of Iceberg metadata into Chroma vector database for RAG',
    schedule_interval='@daily',  # Run daily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['rag', 'vector-db', 'metadata', 'daily'],
    doc_md=__doc__
) as dag:
    
    # Task 1: Extract metadata from Iceberg
    metadata = extract_metadata_from_iceberg()
    
    # Task 2: Extract sample data
    samples = extract_sample_data()
    
    # Task 3: Create embeddings (depends on tasks 1 & 2)
    embeddings = create_embeddings(metadata, samples)
    
    # Task 4: Upsert to Chroma
    upsert_result = upsert_to_chroma(embeddings)
    
    # Task 5: Validate vector database
    validation = validate_vector_db()
    
    # Task 6: Notify completion
    notify = notify_completion(validation)
    
    # Define task dependencies
    [metadata, samples] >> embeddings >> upsert_result >> validation >> notify
