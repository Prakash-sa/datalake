"""
Data Lake Query Engine
Provides SQL query execution on Apache Iceberg tables via Trino.
"""

import os
from typing import Optional
from datetime import datetime
import logging

import trino

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLakeQueryEngine:
    """
    Query Engine for Apache Iceberg tables on Trino.
    Executes SQL queries and returns results.
    """

    def __init__(self, trino_host: str = "localhost", trino_port: int = 8080):
        """
        Initialize the query engine.
        
        Args:
            trino_host: Trino server hostname
            trino_port: Trino server port
        """
        self.trino_host = trino_host
        self.trino_port = trino_port
        self._initialize_trino_connection()

    def _initialize_trino_connection(self):
        """Initialize Trino connection for metadata and query execution."""
        try:
            self.conn = trino.dbapi.connect(
                host=self.trino_host,
                port=self.trino_port,
                user="trino"
            )
            logger.info("✅ Trino connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Trino: {e}")
            raise

    def get_tables_info(self) -> dict:
        """
        Retrieve list of available tables and their schemas.
        
        Returns:
            Dictionary of tables and columns
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema LIKE 'iceberg%'
                ORDER BY table_schema, table_name
            """)
            
            tables = {}
            for schema, table, column, dtype in cursor.fetchall():
                table_key = f"{schema}.{table}"
                if table_key not in tables:
                    tables[table_key] = []
                tables[table_key].append({"column": column, "type": dtype})
            
            cursor.close()
            return tables
        except Exception as e:
            logger.error(f"❌ Failed to retrieve table info: {e}")
            return {}

    def _setup_rag_pipeline(self):
        """Setup RAG components: vector store, metadata indexing."""
        # Initialize vector store (Chroma)
        self.vector_store = Chroma(
            collection_name="iceberg_metadata",
            persist_directory="./chroma_db"
        )
        logger.info("✅ Vector store initialized")

    def index_metadata(self):
        """
        Index data lake metadata (tables, columns, schemas) into vector store.
        Enables semantic search over data lake structure.
        """
        try:
            cursor = self.conn.cursor()
            
            # Fetch all Iceberg tables and their schemas
            cursor.execute("""
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema LIKE 'iceberg%'
                ORDER BY table_schema, table_name
            """)
            
            metadata_docs = []
            for schema, table, column, dtype in cursor.fetchall():
                doc_text = f"""
                Table: {schema}.{table}
                Column: {column}
                Type: {dtype}
                """
                metadata_docs.append(doc_text)
                self.metadata_cache[f"{schema}.{table}"] = {"column": column, "type": dtype}
            
            # Index metadata into vector store
            if metadata_docs:
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                splits = text_splitter.split_text("\n".join(metadata_docs))
                self.vector_store.add_texts(texts=splits)
                logger.info(f"✅ Indexed {len(splits)} metadata chunks")
            
            cursor.close()
        except Exception as e:
            logger.error(f"❌ Metadata indexing failed: {e}")
            raise

    def retrieve_relevant_tables(self, user_query: str, k: int = 5) -> str:
        """
        Retrieve relevant table metadata using semantic search.
        
        Args:
            user_query: Natural language query
            k: Number of relevant results to retrieve
            
        Returns:
            Formatted metadata context
        """
        try:
            results = self.vector_store.similarity_search(user_query, k=k)
            context = "\n".join([doc.page_content for doc in results])
            return context if context else "No relevant tables found."
        except Exception as e:
            logger.warning(f"⚠️ Semantic search failed: {e}")
            return "Metadata retrieval unavailable."

    def generate_sql_query(self, user_query: str, metadata_context: str) -> str:
        """
        Generate SQL query from natural language using LLM.
        
        Args:
            user_query: User's natural language query
            metadata_context: Retrieved metadata context
            
        Returns:
            Generated SQL query
        """
        prompt = ChatPromptTemplate.from_template("""
You are an expert SQL query generator for Apache Iceberg tables in Trino.
Your task is to convert natural language queries to SQL.

Available Iceberg Tables and Metadata:
{metadata}

User Query: {query}

Instructions:
1. Generate valid Trino SQL syntax
2. Use the correct schema and table names from metadata
3. For time-based queries, use Iceberg's time-travel syntax if needed
4. Return ONLY the SQL query without explanation
5. Ensure the query is optimized for analytical workloads

Generated SQL:
""")
        
        response = self.llm.invoke(prompt.format(metadata=metadata_context, query=user_query))
        return response.strip()

    def execute_query(self, sql_query: str) -> dict:
        """
        Execute SQL query on Trino.
        
        Args:
            sql_query: SQL query to execute
            
        Returns:
            Query results as dictionary
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql_query)
            
            # Fetch column names and data
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            cursor.close()
            
            return {
                "status": "success",
                "rows": rows,
                "columns": columns,
                "row_count": len(rows),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "row_count": 0,
                "timestamp": datetime.now().isoformat()
            }

    def validate_and_correct_query(self, user_query: str, sql_query: str, execution_error: Optional[str] = None) -> str:
        """
        Self-correcting mechanism: regenerate query if execution fails.
        Implements adaptive error handling and query refinement.
        
        Args:
            user_query: Original user query
            sql_query: Previously generated SQL
            execution_error: Error message from failed execution
            
        Returns:
            Corrected SQL query
        """
        if not execution_error:
            return sql_query
        
        logger.info("🔄 Attempting query self-correction...")
        
        prompt = ChatPromptTemplate.from_template("""
The following SQL query failed with an error. Fix it and generate a corrected version.

Original User Query: {user_query}
Failed SQL: {sql_query}
Error: {error}

Instructions:
1. Analyze the error and identify the issue
2. Generate a corrected SQL query
3. Return ONLY the corrected SQL without explanation

Corrected SQL:
""")
        
        corrected = self.llm.invoke(prompt.format(
            user_query=user_query,
            sql_query=sql_query,
            error=execution_error
        ))
        return corrected.strip()

    def query_data_lake(self, user_query: str, max_retries: int = 2) -> dict:
        """
        End-to-end RAG pipeline: retrieve metadata → generate SQL → execute → validate.
        Improves answer accuracy through iterative refinement.
        
        Args:
            user_query: Natural language query
            max_retries: Number of self-correction attempts
            
        Returns:
            Query results with metadata
        """
        logger.info(f"📝 Processing query: {user_query}")
        
        # Step 1: Retrieve relevant metadata
        metadata = self.retrieve_relevant_tables(user_query)
        logger.info(f"📚 Retrieved metadata context ({len(metadata)} chars)")
        
        # Step 2: Generate initial SQL
        sql_query = self.generate_sql_query(user_query, metadata)
        logger.info(f"🔍 Generated SQL:\n{sql_query}")
        
        # Step 3: Execute with self-correction loop
        for attempt in range(max_retries + 1):
            result = self.execute_query(sql_query)
            
            if result["status"] == "success":
                logger.info(f"✅ Query executed successfully ({result['row_count']} rows)")
                return {
                    "user_query": user_query,
                    "sql_query": sql_query,
                    "results": result,
                    "attempts": attempt + 1,
                    "timestamp": datetime.now().isoformat()
                }
            elif attempt < max_retries:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed, self-correcting...")
                sql_query = self.validate_and_correct_query(user_query, sql_query, result.get("error"))
        
        # Return last attempt result
        return {
            "user_query": user_query,
            "sql_query": sql_query,
            "results": result,
            "attempts": max_retries + 1,
            "timestamp": datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Initialize query engine
    engine = DataLakeQueryEngine(trino_host="localhost", trino_port=8080)
    
    # Example SQL queries
    test_queries = [
        "SELECT COUNT(*) as total_count FROM iceberg.raw.sales",
        "SELECT * FROM iceberg.raw.customers LIMIT 5",
        "SELECT product_id, SUM(amount) as total FROM iceberg.raw.sales GROUP BY product_id"
    ]
    
    for query in test_queries:
        result = engine.execute_query(query)
        print(f"\n{'='*60}")
        print(f"SQL: {query}")
        print(f"Status: {result['status']}")
        if result['status'] == 'success':
            print(f"Rows: {result['row_count']}")
            print(f"Columns: {result['columns']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}")
        print(f"{'='*60}")
