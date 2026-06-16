import re

class GenerationMonitor:
    def __init__(self):
        self.confidence_threshold = 0.7

    def track_token_confidence(self, token: str, probability: float) -> dict:
        if probability < self.confidence_threshold:
            return {
                "is_low_confidence": True,
                "token": token,
                "probability": probability,
                "suggestion": "Flag for review"
            }
        return {"is_low_confidence": False}

    def flag_factual_claims(self, text: str) -> list:
        fact_patterns = [
            r"\b(is|are|was|were)\s+\w+",
            r"\b(has|have|had)\s+\w+",
            r"\d+\s+(percent|%|million|billion)",
        ]
        claims = []
        for pattern in fact_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                claims.append({
                    "claim": match.group(),
                    "position": match.span(),
                    "needs_verification": True
                })
        return claims

    def require_source_attribution(self, text: str) -> dict:
        claims = self.flag_factual_claims(text)
        unattributed = []
        for claim in claims:
            surrounding_text = text[max(0, claim["position"][0]-100):claim["position"][1]+100]
            if not re.search(r"\[Source:\s*\w+\]", surrounding_text):
                unattributed.append(claim)
        return {
            "unattributed_claims": unattributed,
            "must_add_sources": len(unattributed) > 0
        }

    def check_consistency(self, new_text: str, conversation_history: list) -> dict:
        has_contradictions = False
        contradictions = []
        for prev in conversation_history[-5:]:
            if "not" in new_text.lower() and "not" not in prev.lower() and len(set(new_text.split()) & set(prev.split())) > 5:
                has_contradictions = True
                contradictions.append(f"Potential contradiction between: '{new_text}' and '{prev}'")
        return {
            "has_contradictions": has_contradictions,
            "contradictions": contradictions
        }
