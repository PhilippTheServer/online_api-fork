import asyncio
import os
import json
import logging
from typing import List

import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# Logging setup
logger = logging.getLogger("uvicorn.error")

# Read credentials from environment variables (set via CLI or Docker secrets)
STEMgraph_user = os.getenv("STEMgraph_user")
STEMgraph_pw = os.getenv("STEMgraph_pw")
STEMgraph_write_access = os.getenv("STEMgraph_write_access")

# API key security setup
API_KEY = STEMgraph_write_access
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verifies the API key before processing requests."""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key - Access denied",
        )

# FastAPI setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Neo4j connection settings
NEO4J_URL = "http://neo4j.boekelmann.net:7474/db/neo4j/tx/commit"
NEO4J_AUTH = (STEMgraph_user, STEMgraph_pw)
HEADERS = {"Content-Type": "application/json"}

async def health_check():
    """Performs a health check by querying Neo4j."""
    query = {"statements": [{"statement": "RETURN 'OK' AS status"}]}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=query)
            data = response.json()
            if data["results"][0]["data"][0]["row"][0] == "OK":
                logger.info("✅ Successfully connected to Neo4j.")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Health check failed: {e}")
    return False

@app.on_event("startup")
async def wait_for_healthcheck():
    """Retries the health check before allowing the API to start."""
    logger.info("⏳ Waiting for Neo4j to become available...")
    while not await health_check():
        logger.warning("🔄 Retrying in 5 seconds...")
        await asyncio.sleep(5)
    logger.info("🚀 API is starting now.")


# Pydantic model for adding nodes
class NewNode(BaseModel):
    name: str
    uuid: str
    repo_domain: str
    description: str
    builds_on: List[str] = []

@app.get("/graph")
async def get_graph():
    """Retrieves all nodes and edges from Neo4j."""
    node_query = {
        "statements": [{"statement": "MATCH (n) RETURN {id: id(n), uuid: n.uuid, label: n.name, repo_link: n.repo_domain} AS node"}]
    }
    edge_query = {
        "statements": [{"statement": "MATCH (a)-[r]->(b) RETURN {from: id(a), to: id(b), type: type(r)} AS edge"}]
    }

    async with httpx.AsyncClient() as client:
        try:
            # Fetch nodes
            response_nodes = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=node_query)
            nodes_data = response_nodes.json()
            nodes = [entry["row"][0] for entry in nodes_data["results"][0]["data"]]

            # Fetch edges
            response_edges = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=edge_query)
            edges_data = response_edges.json()
            edges = [entry["row"][0] for entry in edges_data["results"][0]["data"]]

            return JSONResponse(content={"nodes": nodes, "edges": edges})
        
        except Exception as e:
            logger.error("Error retrieving graph data: %s", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve graph data.")

@app.get("/get_detail/{identifier}")
async def get_node_detail(identifier: str):
    """Fetches a single node by ID, UUID, or name."""
    query = {
        "statements": [
            {
                "statement": """
                MATCH (n)
                WHERE id(n) = toInteger($identifier) OR n.uuid = $identifier OR n.name = $identifier
                RETURN {id: id(n), uuid: n.uuid, label: n.name, repo_link: n.repo_domain, description: n.description} AS node
                """,
                "parameters": {"identifier": identifier}
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=query)
            data = response.json()
            if not data["results"][0]["data"]:
                raise HTTPException(status_code=404, detail="Node not found")

            return JSONResponse(content=data["results"][0]["data"][0]["row"][0])

        except Exception as e:
            logger.error("Error retrieving node: %s", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve node.")

@app.post("/add_node", dependencies=[Depends(verify_api_key)])
async def add_node(new_node: NewNode):
    """Creates a new node in Neo4j and connects it to existing nodes via 'Builds On' relationships."""
    
    # Query to create the main node
    create_node_query = """
    MERGE (n:Challenge {uuid: $uuid})
    SET n.name = $name, n.repo_domain = $repo_domain, n.description = $description
    RETURN id(n) AS id
    """

    # Query to establish "Builds On" relationships
    builds_on_query = """
    UNWIND $builds_on AS builds_on_uuid
    MERGE (n:Challenge {uuid: $uuid})
    MERGE (b:Challenge {uuid: builds_on_uuid})
    MERGE (n)-[:BUILDS_ON]->(b)
    """

    async with httpx.AsyncClient() as client:
        try:
            # Send request to create the node
            response = await client.post(
                NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH,
                json={"statements": [{"statement": create_node_query, "parameters": {
                    "uuid": new_node.uuid,
                    "name": new_node.name,
                    "repo_domain": new_node.repo_domain,
                    "description": new_node.description
                }}]}
            )
            data = response.json()
            new_id = data["results"][0]["data"][0]["row"][0]

            # If there are "Builds On" relationships, create them
            if new_node.builds_on:
                await client.post(
                    NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH,
                    json={"statements": [{"statement": builds_on_query, "parameters": {
                        "uuid": new_node.uuid,
                        "builds_on": new_node.builds_on
                    }}]}
                )

        except Exception as e:
            logger.error("Error creating node in Neo4j: %s", e)
            raise HTTPException(status_code=500, detail=f"Failed to create node: {e}")

    return JSONResponse(content={"id": new_id, "message": "Node created successfully."})

@app.get("/healthcheck")
async def health_check():
    """Health check endpoint to verify API and Neo4j connectivity."""
    query = {"statements": [{"statement": "RETURN 'OK' AS status"}]}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=query)
            data = response.json()
            if data["results"][0]["data"][0]["row"][0] == "OK":
                return JSONResponse(content={"status": "API is running and connected to Neo4j"})
            else:
                raise Exception("Unexpected response from Neo4j")

        except Exception as e:
            logger.error("Health check failed: %s", e)
            raise HTTPException(status_code=500, detail="API cannot connect to Neo4j")

@app.get("/builds_on_list/{uuid}")
async def get_builds_on_list(uuid: str):
    """Recursively retrieves all UUIDs a given node 'builds_on'."""
    query = {
        "statements": [
            {
                "statement": """
                MATCH (n:Challenge {uuid: $uuid})-[:BUILDS_ON*]->(dependency)
                RETURN DISTINCT dependency.uuid AS uuid
                """,
                "parameters": {"uuid": uuid}
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=query)
            data = response.json()
            uuids = [entry["row"][0] for entry in data["results"][0]["data"]]

            return JSONResponse(content={"uuid": uuid, "builds_on": uuids})
        
        except Exception as e:
            logger.error("Error retrieving builds_on list: %s", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve builds_on list.")


@app.get("/builds_on_tree/{uuid}")
async def get_builds_on_tree(uuid: str):
    """Recursively retrieves all UUIDs a given node 'builds_on' and returns them as a tree structure."""
    query = {
        "statements": [
            {
                "statement": """
                MATCH path = (n:Challenge {uuid: $uuid})-[:BUILDS_ON*]->(dependency)
                WITH collect(path) AS paths
                CALL apoc.convert.toTree(paths) YIELD value
                RETURN value
                """,
                "parameters": {"uuid": uuid}
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(NEO4J_URL, headers=HEADERS, auth=NEO4J_AUTH, json=query)
            data = response.json()

            if not data["results"][0]["data"]:
                return JSONResponse(content={"uuid": uuid, "builds_on_tree": {}})
            
            builds_on_tree = data["results"][0]["data"][0]["row"][0]
            return JSONResponse(content={"uuid": uuid, "builds_on_tree": builds_on_tree})

        except Exception as e:
            logger.error("Error retrieving builds_on tree: %s", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve builds_on tree.")
