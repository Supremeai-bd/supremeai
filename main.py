import uvicorn
from core.app import app
from core.logging_config import setup_logging

# Initialize logging
setup_logging()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)