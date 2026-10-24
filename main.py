"""DataGit API Entrypoint."""
import uvicorn
from datagit.api.app import app

if __name__ == "__main__":
    uvicorn.run(
        "datagit.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["datagit"],
        reload_excludes=["datagit-frontend", "exports", "*.db*", ".git"]
    )