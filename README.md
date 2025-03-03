# STEMgraph API

This project implements a FastAPI-based API for interacting with the STEMgraph database. The API allows users to query graph data, retrieve node details, and add new nodes while ensuring security through Docker Secrets and API keys.

## Overview

### Use Case
Provides endpoints for user interactions with the STEMgraph database, including:
- Retrieving graph data
- Fetching details of specific nodes
- Creating new nodes with relationships
- Fetching dependency information in both list and tree formats

### Security
- Uses **Docker Secrets** to securely manage sensitive credentials.
- Protects write-access endpoints with an API key passed in the `X-API-Key` header.

### Architecture
- **FastAPI** as the web framework
- **Typer** to wrap the application execution
- **Uvicorn** for running the API
- **Neo4j** as the graph database
- A background task periodically updates a local cache of the graph data.
- A health check on startup ensures connectivity to Neo4j before the API starts.

## File Structure

- **`app/main.py`** - Defines the FastAPI application, endpoints, and logic.
- **`app/STEMgraph_API.py`** - Uses Typer to wrap the FastAPI application and handle CLI or Docker Secrets-based execution.
- **`requirements.txt`** - Contains the dependencies required for running the API.
- **`Dockerfile`** - Defines the containerized deployment.
- **`docker-compose.yml`** - Configures Docker services, including Docker Secrets for sensitive credentials.

## Prerequisites

- Python 3.12 installed (for local execution)
- Docker installed (for containerized execution)
- Docker Swarm initialized (for Docker Secrets functionality)
- Docker Compose installed

## Running the API

### **Running Locally**

1. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the API with credentials:**
   ```bash
   python app/STEMgraph_API.py --neo4j-user "<neo4j-user>" --neo4j-pw "<neo4j-pw>" --write-token "<write-token>"
   ```
4. **Test Neo4j connectivity before starting:**
   ```bash
   python app/STEMgraph_API.py --neo4j-user "<neo4j-user>" --neo4j-pw "<neo4j-pw>" --test
   ```
   If the connection is successful, it will print:
   ```
   ✅ Successfully connected to Neo4j.
   ```
   Otherwise, an error message will indicate the issue.

### **Running with Docker**

When running in Docker, credentials are managed through Docker Secrets and do not need to be passed via CLI.

1. **Build the Docker Image:**
   ```bash
   docker build -t stemgraph_api:v1 .
   ```

2. **Create Docker Secrets:**
   ```bash
   echo "your_neo4j_username" | docker secret create STEMgraph_user -
   echo "your_neo4j_password" | docker secret create STEMgraph_pw -
   echo "your_api_key" | docker secret create STEMgraph_write_access -
   ```

3. **Deploy with Docker Compose:**
   ```bash
   docker stack deploy --compose-file docker-compose.yml stemgraph_stack
   ```

4. **View logs:**
   ```bash
   docker service logs -f stemgraph_stack_stemgraph_api
   ```

## API Endpoints

### **GET `/graph`**
- **Description:** Retrieves all nodes and edges from the Neo4j database.
- **Response Format:** JSON with `nodes` and `edges` arrays.

### **GET `/get_detail/{identifier}`**
- **Description:** Fetches details of a single node by ID, UUID, or name.
- **Request Parameter:**
  - `identifier`: Node ID, UUID, or name.
- **Response Format:** JSON containing node details.

### **POST `/add_node`** (Requires API Key)
- **Description:** Creates a new node in Neo4j and establishes "Builds On" relationships.
- **Security:** Requires an API key in the `X-API-Key` header.
- **Request Body Example:**
  ```json
  {
      "name": "Example Node",
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "repo_domain": "https://github.com/example/repo",
      "description": "A sample project node",
      "builds_on": ["uuid-of-related-node"]
  }
  ```

### **GET `/builds_on_list/{uuid}`**
- **Description:** Retrieves all UUIDs that a given node "builds_on" recursively and returns them as a flat list.
- **Response Format:**
  ```json
  {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "builds_on": [
          "abcdef12-3456-7890-abcd-ef1234567890",
          "7890abcd-ef12-3456-7890-abcdef123456"
      ]
  }
  ```

### **GET `/builds_on_tree/{uuid}`**
- **Description:** Retrieves all UUIDs that a given node "builds_on" recursively and returns them as a nested tree structure.
- **Response Format:**
  ```json
  {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "builds_on_tree": {
          "uuid": "123e4567-e89b-12d3-a456-426614174000",
          "children": [
              {
                  "uuid": "abcdef12-3456-7890-abcd-ef1234567890",
                  "children": [
                      {
                          "uuid": "7890abcd-ef12-3456-7890-abcdef123456",
                          "children": []
                      }
                  ]
              }
          ]
      }
  }
  ```

### **GET `/healthcheck`**
- **Description:** Verifies API and Neo4j connectivity before allowing startup.
- **Response:**
  ```json
  { "status": "API is running and connected to Neo4j" }
  ```

## Logging

- The API uses Uvicorn's logging engine (`logging.getLogger("uvicorn.error")`).
- Logs can be viewed via Docker using:
  ```bash
  docker service logs -f stemgraph_stack_stemgraph_api
  ```

## Author

Created by [MaxClerkwell](https://x.com/MaxClerkwell)