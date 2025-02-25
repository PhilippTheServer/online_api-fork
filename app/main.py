import asyncio
import json
import logging
from typing import List, Dict, Any

import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# Use Uvicorn's logging engine for consistent log formatting.
logger = logging.getLogger("uvicorn.error")

# --------------------------------------------------------------------------------
# Utility function to read Docker secret files from /run/secrets/
# --------------------------------------------------------------------------------
def read_secret(secret_name: str) -> str:
    """
    Reads the content of a Docker secret file from the /run/secrets/ directory.

    Args:
        secret_name (str): The name of the secret file (without the path).

    Returns:
        str: The secret value as a string (trimmed), or None if an error occurs.
    """
    secret_path = f"/run/secrets/{secret_name}"
    try:
        with open(secret_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        logger.error("Secret file %s not found.", secret_path)
        return None
    except Exception as e:
        logger.error("Error reading secret file %s: %s", secret_path, e)
        return None

# --------------------------------------------------------------------------------
# Read Docker secrets and assign them to variables.
# --------------------------------------------------------------------------------
STEMgraph_user = read_secret("STEMgraph_user")
STEMgraph_pw = read_secret("STEMgraph_pw")
STEMgraph_write_access = read_secret("STEMgraph_write_access")

# Use the write access secret as the API key for write operations.
API_KEY = STEMgraph_write_access

# --------------------------------------------------------------------------------
# FastAPI API key security setup.
# --------------------------------------------------------------------------------
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def verify_api_key(api_key: str = Depends(api_key_header)):
    """
    Verifies that the provided API key matches the expected key.

    Args:
        api_key (str): API key from the request header.

    Raises:
        HTTPException: If the API key is invalid.
    """
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key - Access denied",
        )

# --------------------------------------------------------------------------------
# Pydantic models for caching and new node input.
# --------------------------------------------------------------------------------
class Cache(BaseModel):
    """
    Represents a cache for the graph, containing nodes and edges.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def print_cache(self):
        """
        Prints the current cache as a well-formatted JSON string.
        """
        logger.info("Updated Cache:")
        logger.info(json.dumps(self.dict(), indent=4, ensure_ascii=False))

class NewNode(BaseModel):
    """
    Represents the input model for creating a new node.
    """
    name: str
    uuid: str
    repo_link: str

# Global cache object for storing graph data.
graph_cache = Cache()

# --------------------------------------------------------------------------------
# FastAPI application setup with CORS middleware.
# --------------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict origins appropriately.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------------
# Neo4j database connection configuration.
# --------------------------------------------------------------------------------
NEO4J_URL = "http://neo4j.boekelmann.net:7474/db/neo4j/tx/commit"
NEO4J_AUTH = (STEMgraph_user, STEMgraph_pw)
HEADERS = {"Content-Type": "application/json"}

# Predefined payloads for node and edge queries.
NODE_QUERY_PAYLOAD = {
    "statements": [
        {
            "statement": "MATCH (n) RETURN {node: n} AS node"
        }
    ]
}

EDGE_QUERY_PAYLOAD = {
    "statements": [
        {
            "statement": "MATCH (source)-[r]->(target) RETURN {from: id(source), type: type(r), to: id(target)} AS edge"
        }
    ]
}

# --------------------------------------------------------------------------------
# Background task: update the graph cache periodically from Neo4j.
# --------------------------------------------------------------------------------
async def update_graph_cache():
    """
    Fetches nodes and edges from the Neo4j database and updates the global cache.
    Uses try/except blocks to catch exceptions during HTTP requests and logs outcomes.
    """
    global graph_cache
    async with httpx.AsyncClient() as client:
        # Fetch nodes from Neo4j.
        try:
            response_nodes = await client.post(
                NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=NODE_QUERY_PAYLOAD
            )
            nodes_data = response_nodes.json()
            logger.info("Successfully fetched nodes from Neo4j.")
        except Exception as e:
            logger.error("Error fetching nodes from Neo4j: %s", e)
            nodes_data = {}

        # Fetch edges from Neo4j.
        try:
            response_edges = await client.post(
                NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=EDGE_QUERY_PAYLOAD
            )
            edges_data = response_edges.json()
            logger.info("Successfully fetched edges from Neo4j.")
        except Exception as e:
            logger.error("Error fetching edges from Neo4j: %s", e)
            edges_data = {}

        # Process nodes: transform Neo4j node data into a simplified format.
        new_nodes = []
        if nodes_data.get("results"):
            neo4j_nodes = nodes_data["results"][0].get("data", [])
            for entry in neo4j_nodes:
                row = entry.get("row", [])
                meta = entry.get("meta", [])
                meta_entry = meta[0] if meta and len(meta) > 0 else {}
                if meta_entry.get("deleted", False):
                    continue
                node_properties = row[0].get("node", {}) if row and isinstance(row, list) and len(row) > 0 else {}
                new_nodes.append({
                    "id": meta_entry.get("id", "unknown"),
                    "uuid": node_properties.get("uuid", "unknown"),
                    "label": node_properties.get("name", "unknown"),
                    "repo_link": node_properties.get("repo_link", "unknown")
                })
        graph_cache.nodes = new_nodes

        # Process edges: transform Neo4j edge data into a format suitable for visualization.
        new_edges = []
        if edges_data.get("results"):
            neo4j_edges = edges_data["results"][0].get("data", [])
            for entry in neo4j_edges:
                meta = entry.get("meta", [])
                if any(m and m.get("deleted", False) for m in meta):
                    continue
                row = entry.get("row", [])
                if row and isinstance(row, list) and len(row) > 0:
                    edge_props = row[0]
                    new_edges.append({
                        "from": edge_props.get("from", "unknown"),
                        "to": edge_props.get("to", "unknown"),
                        "label": edge_props.get("type", "unknown"),
                        "arrows": "to"  # Indicates an arrow pointing towards the target node.
                    })
        graph_cache.edges = new_edges
        logger.info("Graph cache updated successfully.")

async def periodic_update_task():
    """
    Background task that updates the graph cache every 60 seconds.
    """
    while True:
        await update_graph_cache()
        await asyncio.sleep(60)

# --------------------------------------------------------------------------------
# Startup event: Launch the periodic background update task.
# --------------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """
    Startup event that triggers the background task to update the cache.
    """
    asyncio.create_task(periodic_update_task())
    logger.info("Background task for updating graph cache started.")

# --------------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------------
@app.get("/graph")
async def get_graph():
    """
    GET endpoint to retrieve the current graph cache.
    """
    try:
        logger.info("Graph cache retrieved successfully.")
        return JSONResponse(content=graph_cache.dict())
    except Exception as e:
        logger.error("Error retrieving graph cache: %s", e)
        raise HTTPException(status_code=500, detail="Error retrieving graph cache.")

@app.post("/node", dependencies=[Depends(verify_api_key)])
async def create_node(new_node: NewNode):
    """
    POST endpoint to create a new node in the Neo4j database.
    """
    cypher_query = """
    CREATE (n:Topic {name: $name, uuid: $uuid, repo_link: $repo_link})
    RETURN id(n) AS id
    """
    payload = {
        "statements": [
            {
                "statement": cypher_query,
                "parameters": {
                    "name": new_node.name,
                    "uuid": new_node.uuid,
                    "repo_link": new_node.repo_link
                }
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=payload
            )
            data = response.json()
            new_id = data["results"][0]["data"][0]["row"][0]
            logger.info("Node created successfully with id: %s", new_id)
        except Exception as e:
            logger.error("Error creating node in Neo4j: %s", e)
            raise HTTPException(status_code=500, detail=f"Failed to create node: {e}")
    return JSONResponse(content={"id": new_id})
