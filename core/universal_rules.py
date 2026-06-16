import os
import json
from typing import Dict, Any

class UniversalRulesEngine:
    """
    Admin-defined rules that override ALL agent behavior.
    These are Constitutional Laws - non-negotiable.
    """
    
    def __init__(self, rules_path: str = None):
        if rules_path is None:
            # Default location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.rules_path = os.path.join(base_dir, "data", "admin_rules.json")
        else:
            self.rules_path = rules_path
            
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """Loads rules from secure JSON file. If file does not exist, uses default rules."""
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                # Fallback to default in case of corruption
                pass
                
        # Default fallback rules (Admin definitions)
        default_rules = {
            "directions": {
                "count": 5,
                "names": ["North", "South", "East", "West", "Center"],
                "description": "Admin has defined 5 directions. Center is the reference point."
            },
            "image_generation": {
                "allowed": True,
                "max_cost_per_image": 0.01,
                "require_consent": False,
                "preferred_providers": ["pollinations", "huggingface", "local"]
            },
            "skill_installation": {
                "sandbox_duration_hours": 24,
                "auto_install": True,
                "max_install_time_seconds": 30
            },
            "cost_management": {
                "monthly_budget": 30.00,
                "alert_at_percent": 80.0,
                "hard_stop_at_percent": 100.0
            }
        }
        
        # Save defaults if not present
        os.makedirs(os.path.dirname(self.rules_path), exist_ok=True)
        try:
            with open(self.rules_path, "w", encoding="utf-8") as f:
                json.dump(default_rules, f, indent=4)
        except Exception:
            pass
            
        return default_rules
        
    def save_rules(self, new_rules: Dict[str, Any]) -> bool:
        """Saves updated rules to the rules file."""
        self.rules = new_rules
        try:
            os.makedirs(os.path.dirname(self.rules_path), exist_ok=True)
            with open(self.rules_path, "w", encoding="utf-8") as f:
                json.dump(new_rules, f, indent=4)
            return True
        except Exception:
            return False
    
    def apply(self, decision_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injects rules into EVERY decision.
        Returns modified context with rules enforced.
        """
        # Rule: Direction definition override
        if "direction" in decision_context or "directions" in decision_context:
            decision_context["direction_count"] = self.rules["directions"]["count"]
            decision_context["direction_names"] = self.rules["directions"]["names"]
            decision_context["direction_override_applied"] = True
        
        # Rule: Cost check
        if "cost" in decision_context:
            task_type = decision_context.get("task_type", "")
            max_cost = float("inf")
            if task_type == "image_generation":
                max_cost = self.rules["image_generation"]["max_cost_per_image"]
                
            if decision_context["cost"] > max_cost:
                decision_context["blocked"] = True
                decision_context["reason"] = f"Exceeds Universal Rule: Max cost per task ({max_cost})"
                
        return decision_context
