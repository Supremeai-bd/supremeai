"""Shared helper factories for seed data modules."""
import uuid
import time


def _ts():
    return int(time.time() * 1000)

def _uid():
    return str(uuid.uuid4())

def _learning(type_, category, content, solutions, severity,
              confidence, resolved=True, resolution=None,
              error_count=0, times_applied=0, context=None):
    """Match SystemLearning.java model exactly."""
    return {
        "id": _uid(),
        "type": type_,
        "category": category,
        "content": content,
        "errorCount": error_count,
        "solutions": solutions,
        "context": context or {},
        "timestamp": _ts(),
        "severity": severity,
        "resolved": resolved,
        "resolution": resolution or (solutions[0] if solutions else ""),
        "timesApplied": times_applied,
        "confidenceScore": confidence,
    }

def _pattern(name, category, description, when_to_use, code_example,
             framework, confidence, times_used=0):
    """Reusable pattern document for patterns collection."""
    return {
        "id": _uid(),
        "name": name,
        "category": category,
        "description": description,
        "when_to_use": when_to_use,
        "code_example": code_example,
        "framework": framework,
        "confidence": confidence,
        "times_used": times_used,
        "timestamp": _ts(),
        "source": "COPILOT_MASSIVE_SEED",
    }

def _error_fix(error_msg, cause, fix, language, framework,
               confidence, occurrences=0, ai_fixed="Claude"):
    """Error-fix pair for generation_errors_and_fixes collection."""
    return {
        "id": _uid(),
        "error_message": error_msg,
        "cause": cause,
        "fix": fix,
        "language": language,
        "framework": framework,
        "confidence": confidence,
        "occurrences": occurrences,
        "ai_that_fixed": ai_fixed,
        "timestamp": _ts(),
        "source": "COPILOT_MASSIVE_SEED",
    }

def _code_template(name, language, framework, template_type,
                   code, description, tags):
    """Code template/snippet for code_templates collection."""
    return {
        "id": _uid(),
        "name": name,
        "language": language,
        "framework": framework,
        "template_type": template_type,
        "code": code,
        "description": description,
        "tags": tags,
        "timestamp": _ts(),
        "usage_count": 0,
        "source": "COPILOT_MASSIVE_SEED",
    }

def _best_practice(title, category, description, do_list, dont_list,
                   severity, applies_to):
    """Best practice rule for best_practices collection."""
    return {
        "id": _uid(),
        "title": title,
        "category": category,
        "description": description,
        "do": do_list,
        "dont": dont_list,
        "severity": severity,
        "applies_to": applies_to,
        "timestamp": _ts(),
        "source": "COPILOT_MASSIVE_SEED",
    }
