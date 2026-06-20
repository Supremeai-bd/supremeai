import uvicorn
from core.app import app
from core.logging_config import setup_logging
from config import settings

# Initialize logging
setup_logging()

if __name__ == "__main__":
    is_local = settings.env.lower() == "local"
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=is_local)
