# 🚀 Trino Data Lake with Apache Iceberg, PostgreSQL Metastore & MinIO

![Datalake Architecture](datalake.jpg)

## 🧠 Overview

This project sets up a modern **data lake architecture** using:

- **Trino** as the distributed SQL query engine
- **Apache Iceberg** as the table format for large analytical datasets
- **PostgreSQL** as the Iceberg metastore (catalog)
- **MinIO** as the object storage (S3-compatible)
- **Apache Airflow** for data orchestration and ETL pipelines

It is containerized with Docker Compose and designed to demonstrate the integration of modular data lake components for querying, governance, and workflow automation.

## 🏗️ Components

| Component       | Role                                                                 |
|----------------|----------------------------------------------------------------------|
| **Trino**       | SQL query engine supporting federated querying over Iceberg tables   |
| **Apache Iceberg** | Table format with support for time travel, schema evolution, and ACID |
| **PostgreSQL**  | Catalog/metastore for Iceberg                                        |
| **MinIO**       | Acts as an S3-compatible storage backend                             |
| **Apache Airflow** | DAG scheduler for running batch pipelines and analytics jobs        |

## 🐳 Quick Start

### Start Trino + Iceberg + MinIO + PostgreSQL

```bash
cd trino-dlake
docker-compose up
```

Access Trino CLI:

```bash
docker-compose exec controller trino
```

Tear down:

```bash
docker-compose down
```

### Set Up Airflow (Optional)

The Airflow setup lives in `airflow-db/`. A custom Docker image is used.

```bash
cd airflow-db
docker build -t airflow-trino -f Dockerfile . --no-cache
docker-compose up -d
```

## 📂 Project Structure

```
datalake-main/
├── trino-dlake/         # Docker-compose setup for Trino, Iceberg, Postgres, MinIO
├── airflow-db/          # Custom Dockerized Airflow DAG engine
├── datalake.jpg         # Architecture diagram
└── ReadMe.md            # This file
```

## 🎯 Use Cases

- Prototyping a cloud-native data lake
- Learning how Iceberg works with Trino
- Creating reproducible, containerized data platforms
- Running SQL over object storage
- Experimenting with Airflow DAGs over data lake tables

## 🛠️ Future Enhancements

- Add sample ETL DAGs using Airflow
- Integrate DBT for transformations
- Add monitoring (Prometheus + Grafana)

## 📘 References

- [Trino](https://trino.io/)
- [Apache Iceberg](https://iceberg.apache.org/)
- [MinIO](https://min.io/)
- [Apache Airflow](https://airflow.apache.org/)

