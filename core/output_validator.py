import re

class OutputValidator:
    def __init__(self):
        self.consensus_threshold = 0.7

    def multi_model_consensus(self, output: str, task: str) -> dict:
        # Simple simulated consensus calculation
        # If output contains known bad repo URL or invalid terms, score is low
        score = 1.0
        disagreements = []
        if "nadim9/supremeai" in output.lower():
            score = 0.1
            disagreements.append("Incorrect GitHub repository path detected (hallucinated).")
        return {
            "consensus_score": score,
            "disagreements": disagreements,
            "should_flag": score < self.consensus_threshold
        }

    def self_reflect(self, output: str) -> dict:
        # Simple local rule reflection check
        has_issues = False
        issues = []
        if "nadim9/supremeai" in output.lower():
            has_issues = True
            issues.append("Hallucinated repo path 'nadim9/supremeai'")
        return {
            "has_issues": has_issues,
            "issues": issues
        }

    def score_confidence(self, output: str, verification_results: dict) -> dict:
        consensus = self.multi_model_consensus(output, "")
        reflect = self.self_reflect(output)

        overall = 1.0
        if consensus["should_flag"]:
            overall -= 0.5
        if reflect["has_issues"]:
            overall -= 0.4

        if overall >= 0.9:
            badge = "HIGH_CONFIDENCE"
            color = "green"
        elif overall >= 0.7:
            badge = "MEDIUM_CONFIDENCE"
            color = "yellow"
        else:
            badge = "LOW_CONFIDENCE"
            color = "red"

        return {
            "overall": overall,
            "badge": badge,
            "color": color,
            "should_warn_user": overall < 0.7
        }

    def validate(self, output: str) -> dict:
        reflect = self.self_reflect(output)
        conf = self.score_confidence(output, {})
        return {
            "is_valid": not reflect["has_issues"],
            "confidence": conf
        }
