# STEMgraph API

This project implements a FastAPI-based API for interacting with the STEMgraph database. The API is designed to allow regular users to perform specific actions on the database while securing sensitive data using Docker Secrets.

## Overview

- **Use Case:**  
  Provides endpoints for normal user interactions with the STEMgraph database, including retrieving graph data and creating new nodes.

- **Security:**  
  Uses Docker Secrets to securely handle sensitive information such as database credentials and API keys.  
  Endpoints requiring write access are protected via an API key passed in the header (`X-API-Key`).

- **Architecture:**  
  - **FastAPI** is used as the web framework.  
  - **Uvicorn's logging engine** is employed to ensure consistent log formatting.  
  - A background task periodically updates a local cache of the graph data from a Neo4j database.

## File Structure

- **`app/main.py`**  
  Contains the FastAPI application, API endpoints, background tasks, and functions to read Docker secrets.
  
- **`requirements.txt`**  
  Lists all Python dependencies required by the application.

- **`Dockerfile`**  
  Defines the Docker image build instructions.

- **`docker-compose.yml`**  
  Provides the Docker Compose configuration to deploy the application as a service in Docker Swarm, using Docker Secrets.

## Prerequisites

- Docker installed.
- Docker Swarm initialized (Docker Secrets only work in Swarm mode).
- Docker Compose installed.

## Setup & Deployment

### 1. Build the Docker Image

Navigate to the project root (where the `Dockerfile` is located) and run:

```bash
docker build -t stemgraph_api:v1 .
```

This command builds the image using Python 3.12 and installs all necessary dependencies from `requirements.txt`.

### 2. Configure Docker Secrets

The required secrets are stored in the organization's Vaultwarden under **Admin-Büro/Dev-Ops**. Retrieve them from Vaultwarden and create the Docker Secrets manually. For example:

```bash
echo "your_neo4j_username" | docker secret create STEMgraph_user -
echo "your_neo4j_password" | docker secret create STEMgraph_pw -
echo "your_api_key" | docker secret create STEMgraph_write_access -
```

These secrets will be available inside your container at `/run/secrets/<secret_name>`.

### 3. Deploy the Stack Using Docker Compose

Deploy your service with Docker Swarm using the provided `docker-compose.yml`:

```bash
docker stack deploy --compose-file docker-compose.yml stemgraph_stack
```

This command creates the stack named `stemgraph_stack` and deploys the `stemgraph_api` service with the secrets mounted.

### 4. View Uvicorn Logs

To see the output of Uvicorn (and thus your API logs), run:

```bash
docker service logs -f stemgraph_stack_stemgraph_api
```

This command streams logs from your service so you can monitor API activity and debug if necessary.

## API Endpoints

### GET `/graph`

- **Description:**  
  Retrieves the current graph cache, which contains nodes and edges fetched from the Neo4j database.

- **Response:**  
  JSON data suitable for visualization libraries (e.g., vis.js).

### POST `/node`

- **Description:**  
  Creates a new node in the Neo4j database.

- **Security:**  
  Requires an API key via the `X-API-Key` header. The API key is read from the Docker secret `STEMgraph_write_access`.

- **Request Payload Example:**

  ```json
  {
      "name": "Example Node",
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "repo_link": "https://github.com/example/repo"
  }
  ```

- **Curl Example:**

  ```bash
  curl -v -X POST http://<your-host>:80/node \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key" \
    -d '{
          "name": "Example Node",
          "uuid": "123e4567-e89b-12d3-a456-426614174000",
          "repo_link": "https://github.com/example/repo"
        }'
  ```

## Logging

The application uses Uvicorn's logging engine (accessed via `logging.getLogger("uvicorn.error")`) for consistent output. Logs are written to STDOUT/STDERR, which can be viewed with Docker service logs.

## Author

Created by [MaxClerkwell](https://x.com/MaxClerkwell)

