from brain.model_router import ModelRouter

class NineRouter:
    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router or ModelRouter()
        self.provider_cost_map = {
            "openrouter": 0.0005,
            "gemini": 0.0002,
            "groq": 0.0001,
            "deepseek": 0.0003,
            "nvidia": 0.0004,
            "huggingface": 0.0,
            "ollama": 0.0,
        }

    def pick(self, task_type: str, prompt: str, max_cost: float) -> Dict[str, Any]:
        provider, model = self.router._pick_provider(task_type, prompt, max_cost)
        unit_cost = self.provider_cost_map.get(provider, 0.0005)
        estimated_cost = max(0.0, unit_cost)
        return {
            "provider": provider,
            "model": model,
            "route": "cheap" if "flash" in model or "free" in model or estimated_cost == 0 else "premium",
            "estimated_cost": estimated_cost,
        }
