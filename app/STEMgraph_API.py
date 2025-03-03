import typer
import os
import uvicorn
import httpx
from dotenv import load_dotenv

app = typer.Typer()

# Load environment variables from a local .env file
load_dotenv()

NEO4J_URL = "http://neo4j.boekelmann.net:7474/db/neo4j/tx/commit"

@app.command()
def run(
    neo4j_user: str = typer.Option(None, help="Neo4j username"),
    neo4j_pw: str = typer.Option(None, help="Neo4j password"),
    write_token: str = typer.Option(None, help="API write-access token"),
    test: bool = typer.Option(False, help="Test Neo4j connection and exit"),
):
    """
    Starts the FastAPI application using CLI parameters or the .env file.

    - If CLI parameters are provided, they take priority.
    - If no CLI parameters are given, the application uses values loaded from the .env file.
    - If `--test` is passed, the script tests the Neo4j connection and exits.
    """

    if neo4j_user and neo4j_pw and write_token:
        # Use CLI-provided credentials
        os.environ["STEMgraph_user"] = neo4j_user
        os.environ["STEMgraph_pw"] = neo4j_pw
        os.environ["STEMgraph_write_access"] = write_token
    else:
        # Use credentials from the .env file (or fallback defaults if not set)
        os.environ.setdefault("STEMgraph_user", "default_user")
        os.environ.setdefault("STEMgraph_pw", "default_password")
        os.environ.setdefault("STEMgraph_write_access", "default_token")

    if test:
        # Test Neo4j connection
        neo4j_auth = (os.environ["STEMgraph_user"], os.environ["STEMgraph_pw"])
        query = {"statements": [{"statement": "RETURN 'OK' AS status"}]}
        
        try:
            response = httpx.post(NEO4J_URL, json=query, auth=neo4j_auth, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data["results"][0]["data"][0]["row"][0] == "OK":
                print("✅ Successfully connected to Neo4j.")
                raise SystemExit(0)
            else:
                print("❌ Unexpected response from Neo4j.")
                raise SystemExit(1)
        
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error while connecting to Neo4j: {e.response.status_code}")
            raise SystemExit(1)
        
        except httpx.RequestError as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            raise SystemExit(1)
        
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            raise SystemExit(1)
    
    # Start the FastAPI application
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)


if __name__ == "__main__":
    app()
