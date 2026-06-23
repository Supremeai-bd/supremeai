from __future__ import annotations

from typing import Dict, Any, List

from core.evolution_engine import EvolutionEngine as CoreEvolutionEngine


class EvolutionEngine:
    """
    Self-Evolver Engine for SupremeAI 2.0.
    Reuses backend/core/evolution_engine.py to avoid duplication.
    """
    def __init__(self):
        self._engine = CoreEvolutionEngine()
        
    def run_daily_evolution(self, task_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._engine.run_daily_evolution(task_history)
