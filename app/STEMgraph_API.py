import typer
import os
import uvicorn
import httpx
from dotenv import load_dotenv

app = typer.Typer()

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
    Starts the FastAPI application using CLI parameters or Docker secrets.

    - If CLI parameters are provided, they take priority.
    - If no CLI parameters are given, the application falls back to reading Docker secrets.
    - If `--test` is passed, the script only tests the Neo4j connection and exits.
    """

    if neo4j_user and neo4j_pw and write_token:
        # Use CLI-provided credentials
        os.environ.get["STEMgraph_user"] = neo4j_user
        os.environ.get["STEMgraph_pw"] = neo4j_pw
        os.environ.get["STEMgraph_write_access"] = write_token
    else:
        # If CLI parameters are not provided, read from Docker secrets
        def read_secret(secret_name: str) -> str:
            secret_path = f"/run/secrets/{secret_name}"
            try:
                with open(secret_path, "r") as file:
                    return file.read().strip()
            except FileNotFoundError:
                return None
            except Exception:
                return None

        os.environ.get["STEMgraph_user"] = read_secret("STEMgraph_user") or "default_user"
        os.environ.get["STEMgraph_pw"] = read_secret("STEMgraph_pw") or "default_password"
        os.environ.get["STEMgraph_write_access"] = read_secret("STEMgraph_write_access") or "default_token"

    if test:
        # Test Neo4j connection
        neo4j_auth = (os.environ.get["STEMgraph_user"], os.environ.get["STEMgraph_pw"])
        query = {"statements": [{"statement": "RETURN 'OK' AS status"}]}
        
        try:
            response = httpx.post(NEO4J_URL, json=query, auth=neo4j_auth, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data["results"][0]["data"][0]["row"][0] == "OK":
                print("✅ Successfully connected to Neo4j.")
                raise SystemExit(0)  # Clean exit without triggering the exception handler
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
