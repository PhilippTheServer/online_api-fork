import typer
import os
import uvicorn

app = typer.Typer()

@app.command()
def run(
    neo4j_user: str = typer.Option(None, help="Neo4j username"),
    neo4j_pw: str = typer.Option(None, help="Neo4j password"),
    write_token: str = typer.Option(None, help="API write-access token")
):
    """
    Starts the FastAPI application using CLI parameters or Docker secrets.
    
    - If CLI parameters are provided, they take priority.
    - If no CLI parameters are given, the application falls back to reading Docker secrets.
    """

    if neo4j_user and neo4j_pw and write_token:
        # Use CLI-provided credentials
        os.environ["STEMgraph_user"] = neo4j_user
        os.environ["STEMgraph_pw"] = neo4j_pw
        os.environ["STEMgraph_write_access"] = write_token
    else:
        # If CLI parameters are not provided, read from Docker secrets
        def read_secret(secret_name: str) -> str:
            secret_path = f"/run/secrets/{secret_name}"
            try:
                with open(secret_path, 'r') as file:
                    return file.read().strip()
            except FileNotFoundError:
                return None
            except Exception:
                return None

        os.environ["STEMgraph_user"] = read_secret("STEMgraph_user") or "default_user"
        os.environ["STEMgraph_pw"] = read_secret("STEMgraph_pw") or "default_password"
        os.environ["STEMgraph_write_access"] = read_secret("STEMgraph_write_access") or "default_token"

    # Start the FastAPI application
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

if __name__ == "__main__":
    app()

