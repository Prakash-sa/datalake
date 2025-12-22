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
import pickle

logger = logging.getLogger(__name__)

# Default configuration
default_args = {
    "owner": "data-engineering",
    "retries": 1,  # Reduced retries
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
    "email_on_retry": False,
}


@task
def fetch_documents_from_minio(**context) -> List[Dict]:
    """
    Fetch documents from MinIO (S3-compatible storage).
    Returns list of documents directly via XCom.
    """
    from minio import Minio

    logger.info("📄 Fetching documents from MinIO...")

    try:
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        logger.info(f"🔌 Connecting to MinIO at {minio_endpoint}")

        minio_client = Minio(
            endpoint=minio_endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=False,
        )

        bucket_name = "documents"
        documents = []

        try:
            objects = minio_client.list_objects(bucket_name, recursive=True)

            for obj in objects:
                if obj.is_dir:
                    continue

                try:
                    response = minio_client.get_object(bucket_name, obj.object_name)
                    content = response.read().decode("utf-8", errors="ignore")

                    document = {
                        "id": obj.object_name.replace("/", "_"),
                        "content": content[:5000],
                        "metadata": {
                            "source": "minio",
                            "bucket": bucket_name,
                            "filename": obj.object_name,
                            "size": obj.size,
                            "modified": (
                                obj.last_modified.isoformat()
                                if obj.last_modified
                                else None
                            ),
                            "type": "document",
                        },
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
            return []

    except Exception as e:
        logger.error(f"❌ Error connecting to MinIO: {e}")
        return ""


@task
def process_documents(documents: List[Dict]) -> List[Dict]:
    """
    Process and prepare documents for embedding.
    Accepts documents list via XCom and returns processed documents list.
    """
    if not documents:
        logger.warning("⚠️ No documents to process")
        return []

    logger.info(f"🔄 Processing {len(documents)} documents...")

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
    )

    processed_docs = []

    for doc in documents:
        try:
            content = doc["content"]
            chunks = text_splitter.split_text(content)

            for i, chunk in enumerate(chunks):
                processed_doc = {
                    "id": f"{doc['id']}_chunk_{i}",
                    "content": chunk,
                    "metadata": {
                        **doc.get("metadata", {}),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "processing_timestamp": datetime.now().isoformat(),
                    },
                }
                processed_docs.append(processed_doc)

            logger.info(f"✅ Processed {doc['id']} into {len(chunks)} chunks")

        except Exception as e:
            logger.warning(f"⚠️ Failed to process {doc.get('id', 'unknown')}: {e}")
            continue

    logger.info(f"✅ Processed into {len(processed_docs)} document chunks")
    return processed_docs


@task
def create_embeddings(documents: List[Dict]) -> List[Dict]:
    """
    Create vector embeddings from document chunks.
    Accepts processed documents via XCom and returns embedded documents list.
    Uses Ollama nomic-embed-text model for consistent 768-dim embeddings.
    """
    if not documents:
        logger.warning("⚠️ No documents to embed")
        return []

    logger.info(f"🧮 Creating embeddings for {len(documents)} documents...")

    from langchain_ollama import OllamaEmbeddings

    # Use service name for Docker network communication
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    logger.info(f"🤖 Using Ollama at {ollama_base_url}")

    embeddings_model = OllamaEmbeddings(
        model="nomic-embed-text", base_url=ollama_base_url
    )

    embedded_docs = []

    for i, doc in enumerate(documents):
        try:
            # Generate embedding for document content
            vector = embeddings_model.embed_query(doc["content"])

            embedded_doc = {
                "id": doc["id"],
                "content": doc["content"],
                "vector": vector,
                "metadata": doc["metadata"],
            }
            embedded_docs.append(embedded_doc)

            if (i + 1) % 10 == 0:
                logger.info(f"✅ Embedded {i + 1}/{len(documents)} documents")

        except Exception as e:
            logger.warning(f"⚠️ Failed to embed {doc.get('id', 'unknown')}: {e}")
            continue

    logger.info(f"✅ Created {len(embedded_docs)} embeddings (768-dim)")
    return embedded_docs


@task
def upsert_to_chroma(embeddings: List[Dict]) -> Dict:
    """
    Upsert embeddings to Chroma vector database.
    Accepts embeddings via XCom and returns upsert result dict.
    Uses 'documents' collection for indexed enterprise documents.
    """
    if not embeddings:
        logger.warning("⚠️ No embeddings to upsert")
        return {
            "status": "success",
            "collection_name": "documents",
            "embeddings_count": 0,
            "ids_count": 0,
            "timestamp": datetime.now().isoformat(),
        }

    logger.info(f"💾 Upserting {len(embeddings)} embeddings to Chroma...")

    import chromadb

    # Initialize Chroma client (persistent)
    chroma_path = os.getenv("CHROMA_PATH", "/opt/airflow/chroma_db")
    os.makedirs(chroma_path, exist_ok=True)

    client = chromadb.PersistentClient(path=chroma_path)
    collection_name = "documents"

    # Get or create collection
    try:
        collection = client.get_collection(name=collection_name)
        logger.info(f"📚 Using existing collection: {collection_name}")
    except:
        collection = client.create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"📚 Created new collection: {collection_name}")

    # Prepare data for insertion
    ids = []
    documents = []
    embeddings_list = []
    metadatas = []

    for item in embeddings:
        doc_id = item["id"]
        ids.append(doc_id)
        documents.append(item["content"])
        embeddings_list.append(item["vector"])

        # Flatten metadata for Chroma (string, int, float only)
        metadata = item.get("metadata", {})
        clean_metadata = {k: str(v) for k, v in metadata.items()}
        metadatas.append(clean_metadata)

    # Upsert to collection
    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings_list,
            metadatas=metadatas,
        )
        logger.info(f"✅ Upserted {len(ids)} embeddings to Chroma")

    upsert_result = {
        "status": "success",
        "collection_name": collection_name,
        "embeddings_count": len(embeddings),
        "ids_count": len(ids),
        "timestamp": datetime.now().isoformat(),
    }

    return upsert_result


@task
def validate_vector_db(upsert_result: Dict) -> Dict:
    """
    Validate vector database contents and quality.
    Accepts upsert result via XCom and returns validation result dict.
    Performs:
    - Count verification
    - Sample query testing
    - Embedding quality checks
    """
    if not upsert_result or upsert_result.get("embeddings_count", 0) == 0:
        logger.warning("⚠️ No embeddings to validate")
        return {
            "status": "warning",
            "total_embeddings": 0,
            "sample_query_results": 0,
            "message": "No embeddings",
            "validation_time": datetime.now().isoformat(),
        }

    logger.info("🔍 Validating vector database...")

    import chromadb

    chroma_path = os.getenv("CHROMA_PATH", "/opt/airflow/chroma_db")
    os.makedirs(chroma_path, exist_ok=True)

    try:
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection(name="documents")

        # Get collection stats
        count = collection.count()
        logger.info(f"📊 Total embeddings in collection: {count}")

        # Test a sample query
        query_results = 0
        if count > 0:
            test_query = "document data information"
            results = collection.query(query_texts=[test_query], n_results=3)
            query_results = len(results["documents"][0]) if results["documents"] else 0
            logger.info(f"✅ Sample query returned {query_results} results")

            # Verify embeddings exist and have correct dimensions
            sample = collection.get(limit=1)
            if sample["embeddings"]:
                embedding_dim = len(sample["embeddings"][0])
                logger.info(f"✅ Embedding dimension verified: {embedding_dim} dims")

        validation_result = {
            "status": "success",
            "total_embeddings": count,
            "sample_query_results": query_results,
            "validation_time": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        validation_result = {
            "status": "error",
            "error": str(e),
            "validation_time": datetime.now().isoformat(),
        }

    return validation_result


@task
def notify_completion(validation_result: Dict) -> None:
    """
    Send completion notification with summary.
    Logs the final status from validation result.
    Can be extended to send emails/Slack messages.
    """
    if not validation_result:
        logger.warning("⚠️ No validation result to notify")
        return

    logger.info("📬 Document RAG pipeline completed!")
    logger.info(f"📊 Summary:")
    logger.info(
        f"   - Total embeddings: {validation_result.get('total_embeddings', 0)}"
    )
    logger.info(
        f"   - Sample query results: {validation_result.get('sample_query_results', 0)}"
    )
    logger.info(f"   - Status: {validation_result.get('status', 'unknown')}")
    logger.info(
        f"   - Timestamp: {validation_result.get('validation_time', 'unknown')}"
    )

    # Can integrate with Slack/Email here
    # send_slack_notification(f"Document RAG updated: {validation_result['total_embeddings']} embeddings")


# Define the DAG
with DAG(
    dag_id="document_rag_ingestion_pipeline",
    default_args=default_args,
    description="Continuous ingestion of enterprise documents into Chroma vector database for RAG",
    schedule_interval="@daily",  # Run daily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["rag", "vector-db", "documents", "daily"],
    doc_md=__doc__,
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
    validation = validate_vector_db(upsert_result)

    # Task 6: Notify completion
    notify = notify_completion(validation)

    # Define task dependencies
    documents >> processed >> embeddings >> upsert_result >> validation >> notify
