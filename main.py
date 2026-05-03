import os
import sys
import uvicorn
from fastapi import FastAPI
from api.webhook import router

# Ensure venv binaries (semgrep) are on PATH
venv_bin = os.path.join(sys.prefix, "bin")
os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")

app = FastAPI(title="Sentinel")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
