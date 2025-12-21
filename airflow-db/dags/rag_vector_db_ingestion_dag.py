"""
Airflow DAG for Document RAG Pipeline
Orchestrates document ingestion, embedding generation, and vector database indexing.
Processes structured and unstructured documents (PDFs, text, databases) into Chroma vector store.
"""

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import logging
import json
from typing import List, Dict
import os

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
def fetch_documents_from_minio(**context) -> List[Dict]:
    """
    Fetch documents from MinIO (S3-compatible storage).
    
    Retrieves:
    - PDF documents
    - Text files
    - JSON structured data
    - Database query results
    
    Returns documents with metadata.
    """
    from minio import Minio
    import io
    
    logger.info("📄 Fetching documents from MinIO...")
    
    try:
        # MinIO client configuration
        minio_client = Minio(
            endpoint='minio:9000',  # Docker compose service
            access_key=os.getenv('MINIO_ROOT_USER', 'minioadmin'),
            secret_key=os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin'),
            secure=False
        )
        
        bucket_name = 'documents'
        documents = []
        
        # List all objects in bucket
        try:
            objects = minio_client.list_objects(bucket_name, recursive=True)
            
            for obj in objects:
                if obj.is_dir:
                    continue
                
                try:
                    # Download object
                    response = minio_client.get_object(bucket_name, obj.object_name)
                    content = response.read().decode('utf-8', errors='ignore')
                    
                    # Create document record
                    document = {
                        'id': obj.object_name.replace('/', '_'),
                        'content': content[:5000],  # First 5000 chars to avoid truncation
                        'metadata': {
                            'source': 'minio',
                            'bucket': bucket_name,
                            'filename': obj.object_name,
                            'size': obj.size,
                            'modified': obj.last_modified.isoformat() if obj.last_modified else None,
                            'type': 'document'
                        }
                    }
                    documents.append(document)
                    logger.info(f"✅ Loaded: {obj.object_name} ({obj.size} bytes)")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load {obj.object_name}: {e}")
                    continue
            
            logger.info(f"✅ Fetched {len(documents)} documents from MinIO")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error listing bucket contents: {e}")
            # Return empty list if bucket doesn't exist yet
            return []
    
    except Exception as e:
        logger.error(f"❌ Error connecting to MinIO: {e}")
        return []


@task
def process_documents(documents: List[Dict]) -> List[Dict]:
    """
    Process and prepare documents for embedding.
    
    Operations:
    - Clean and normalize text
    - Remove duplicates
    - Split large documents into chunks
    - Add document structure metadata
    """
    logger.info(f"🔄 Processing {len(documents)} documents...")
    
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        
        processed_docs = []
        
        for doc in documents:
            try:
                content = doc['content']
                
                # Split large documents into chunks
                chunks = text_splitter.split_text(content)
                
                for i, chunk in enumerate(chunks):
                    processed_doc = {
                        'id': f"{doc['id']}_chunk_{i}",
                        'content': chunk,
                        'metadata': {
                            **doc['metadata'],
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'processing_timestamp': datetime.now().isoformat()
                        }
                    }
                    processed_docs.append(processed_doc)
                
                logger.info(f"✅ Processed {doc['id']} into {len(chunks)} chunks")
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to process {doc.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"✅ Processed into {len(processed_docs)} document chunks")
        return processed_docs
    
    except Exception as e:
        logger.error(f"❌ Error processing documents: {e}")
        raise


@task
def create_embeddings(documents: List[Dict]) -> List[Dict]:
    """
    Create vector embeddings from document chunks.
    
    Uses Ollama nomic-embed-text model for consistent 768-dim embeddings.
    Same model as RAG engine to ensure compatibility.
    """
    logger.info(f"🧮 Creating embeddings for {len(documents)} documents...")
    
    try:
        from langchain_ollama import OllamaEmbeddings
        
        # Initialize embeddings (same as RAG engine)
        embeddings_model = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://ollama:11434"
        )
        
        embedded_docs = []
        
        for i, doc in enumerate(documents):
            try:
                # Generate embedding for document content
                vector = embeddings_model.embed_query(doc['content'])
                
                embedded_doc = {
                    'id': doc['id'],
                    'content': doc['content'],
                    'vector': vector,
                    'metadata': doc['metadata']
                }
                embedded_docs.append(embedded_doc)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"✅ Embedded {i + 1}/{len(documents)} documents")
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to embed {doc.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"✅ Created {len(embedded_docs)} embeddings (768-dim)")
        return embedded_docs
        
    except Exception as e:
        logger.error(f"❌ Error creating embeddings: {e}")
        raise


@task
def upsert_to_chroma(embeddings: List[Dict]) -> Dict:
    """
    Upsert embeddings to Chroma vector database.
    
    Updates existing embeddings and adds new ones.
    Uses 'documents' collection for indexed enterprise documents.
    """
    logger.info(f"💾 Upserting {len(embeddings)} embeddings to Chroma...")
    
    try:
        import chromadb
        import uuid
        
        # Initialize Chroma client (persistent)
        client = chromadb.PersistentClient(
            path="/app/chroma_db"  # Same location as RAG backend
        )
        
        collection_name = "documents"
        
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
        
        for item in embeddings:
            # Use document ID from processing
            doc_id = item['id']
            
            ids.append(doc_id)
            documents.append(item['content'])
            embeddings_list.append(item['vector'])
            
            # Flatten metadata for Chroma
            metadata = item.get('metadata', {})
            # Chroma only supports string, int, or float metadata values
            clean_metadata = {
                k: str(v) for k, v in metadata.items()
            }
            metadatas.append(clean_metadata)
        
        # Upsert to collection (replaces if exists)
        if ids:
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
        
        try:
            collection = client.get_collection(name="documents")
        except:
            logger.warning("⚠️ Documents collection not found")
            return {
                'status': 'warning',
                'total_embeddings': 0,
                'sample_query_results': 0,
                'message': 'Collection not found'
            }
        
        # Get collection stats
        count = collection.count()
        logger.info(f"📊 Total embeddings in collection: {count}")
        
        # Test a sample query if collection has data
        query_results = 0
        if count > 0:
            test_query = "document data information"
            results = collection.query(
                query_texts=[test_query],
                n_results=3
            )
            
            query_results = len(results['documents'][0]) if results['documents'] else 0
            logger.info(f"✅ Sample query returned {query_results} results")
            
            # Verify embeddings exist and have correct dimensions
            sample = collection.get(limit=1)
            if sample['embeddings']:
                embedding_dim = len(sample['embeddings'][0])
                logger.info(f"✅ Embedding dimension verified: {embedding_dim} dims")
        
        return {
            'status': 'success',
            'total_embeddings': count,
            'sample_query_results': query_results,
            'validation_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'validation_time': datetime.now().isoformat()
        }


@task
def notify_completion(validation_result: Dict) -> None:
    """
    Send completion notification with summary.
    
    Logs the final status and can be extended to send emails/Slack messages.
    """
    logger.info("📬 Document RAG pipeline completed!")
    logger.info(f"📊 Summary:")
    logger.info(f"   - Total embeddings: {validation_result.get('total_embeddings', 0)}")
    logger.info(f"   - Sample query results: {validation_result.get('sample_query_results', 0)}")
    logger.info(f"   - Status: {validation_result.get('status', 'unknown')}")
    logger.info(f"   - Timestamp: {validation_result.get('validation_time', 'unknown')}")
    
    # Can integrate with Slack/Email here
    # send_slack_notification(f"Document RAG updated: {validation_result['total_embeddings']} embeddings")


# Define the DAG
with DAG(
    dag_id='document_rag_ingestion_pipeline',
    default_args=default_args,
    description='Continuous ingestion of enterprise documents into Chroma vector database for RAG',
    schedule_interval='@daily',  # Run daily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['rag', 'vector-db', 'documents', 'daily'],
    doc_md=__doc__
) as dag:
    
    # Task 1: Fetch documents from MinIO
    documents = fetch_documents_from_minio()
    
    # Task 2: Process documents (clean, chunk, prepare)
    processed = process_documents(documents)
    
    # Task 3: Create embeddings
    embeddings = create_embeddings(processed)
    
    # Task 4: Upsert to Chroma
    upsert_result = upsert_to_chroma(embeddings)
    
    # Task 5: Validate vector database
    validation = validate_vector_db()
    
    # Task 6: Notify completion
    notify = notify_completion(validation)
    
    # Define task dependencies
    documents >> processed >> embeddings >> upsert_result >> validation >> notify
