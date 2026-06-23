from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import subprocess

app = FastAPI(title="SupremeAI Skill Gateway")

class SkillRequest(BaseModel):
    prompt: str

@app.post("/generate")
def generate(req: SkillRequest):
    from generator import generate_skill, save_skill
    try:
        skill = generate_skill(req.prompt)
        skill_path = Path(__file__).parent / "generated_skills" / f"{skill['metadata']['name']}.json"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        save_skill(skill, skill_path)
        return {"status": "ok", "skill_path": str(skill_path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/execute/{skill_name}")
def execute(skill_name: str, input1: str):
    skill_file = Path(__file__).parent / "generated_skills" / f"{skill_name}.json"
    if not skill_file.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    skill = json.loads(skill_file.read_text())
    code = skill["implementation"]["code"]
    tmp_path = Path(__file__).parent / "tmp" / f"{skill_name}.py"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(code)
    result = subprocess.run(
        ["python", str(tmp_path), input1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {"output": result.stdout.strip(), "stderr": result.stderr.strip()}
