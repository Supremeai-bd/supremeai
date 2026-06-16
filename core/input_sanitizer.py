import re

class InputSanitizer:
    def __init__(self):
        self.vague_patterns = [r"\bsomething\b", r"\banything\b", r"\betc\b"]
        self.forbidden_patterns = [
            r"predict lottery",
            r"hack into",
            r"generate fake news",
            r"create malware",
            r"impersonate real person"
        ]

    def detect_ambiguity(self, prompt: str) -> dict:
        vague_matches = [p for p in self.vague_patterns if re.search(p, prompt, re.I)]
        is_ambiguous = len(vague_matches) > 0
        clarifying_questions = []
        if is_ambiguous:
            clarifying_questions.append("Could you specify exactly what you mean by 'something/anything/etc.'?")
        return {
            "is_ambiguous": is_ambiguous,
            "vague_terms": vague_matches,
            "clarifying_questions": clarifying_questions
        }

    def validate_scope(self, prompt: str) -> dict:
        for forbidden in self.forbidden_patterns:
            if re.search(forbidden, prompt, re.I):
                return {
                    "is_valid": False,
                    "reason": f"Request involves: {forbidden}",
                    "suggestion": "I cannot help with this request."
                }
        return {"is_valid": True}

    def extract_constraints(self, prompt: str) -> dict:
        budget_match = re.search(r"under\s+\$?(\d+)", prompt, re.I)
        time_match = re.search(r"in\s+(\d+)\s+(hour|day|week|minute)", prompt, re.I)
        return {
            "budget": float(budget_match.group(1)) if budget_match else None,
            "time": time_match.group(0) if time_match else None
        }

    def strip_pii(self, text: str) -> str:
        # Email pattern
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        text = re.sub(email_pattern, "[EMAIL]", text)
        
        # IP Address pattern
        ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        text = re.sub(ip_pattern, "[IP_ADDRESS]", text)
        
        # Phone pattern
        phone_pattern = r"\b\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
        text = re.sub(phone_pattern, "[PHONE_NUMBER]", text)
        
        return text

    def sanitize(self, prompt: str) -> dict:
        scope = self.validate_scope(prompt)
        if not scope["is_valid"]:
            return {"is_valid": False, "reason": scope["reason"]}
        
        # Strip PII
        sanitized_prompt = self.strip_pii(prompt)
        
        ambiguity = self.detect_ambiguity(sanitized_prompt)
        constraints = self.extract_constraints(sanitized_prompt)
        return {
            "is_valid": True,
            "is_ambiguous": ambiguity["is_ambiguous"],
            "clarifying_questions": ambiguity["clarifying_questions"],
            "constraints": constraints,
            "prompt": sanitized_prompt
        }

