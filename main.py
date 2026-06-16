import uvicorn
from fastapi import FastAPI
from c.Users.n.supremeai.supremeai_2.0.core.config import settings
from c.Users.n.supremeai.supremeai_2.0.core.logging_config import setup_logging
from c.Users.n.supremeai.supremeai_2.0.api.v1.endpoints import system
from c.Users.n.supremeai.supremeai_2.0.skill_loader import SkillLoader

# Initialize logging
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Include Routers
app.include_router(system.router, prefix=settings.API_V1_STR, tags=["system"])

# Initialize Skill Loader (Phase 4 Logic)
skill_loader = SkillLoader()
skill_loader.load_skills(app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)