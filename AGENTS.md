# SupremeAI Agent Configuration Guide

This document defines the configuration, behavior, and operational guidelines for all AI agents in the SupremeAI platform.

## Table of Contents

1. [Overview](#overview)
2. [Agent Lifecycle](#agent-lifecycle)
3. [Configuration Schema](#configuration-schema)
4. [Memory System](#memory-system)
5. [Tool System](#tool-system)
6. [HITL Guidelines](#hitl-guidelines)
7. [Safety Protocols](#safety-protocols)
8. [Anti-Pattern Prevention](#anti-pattern-prevention)
9. [Best Practices](#best-practices)
10. [Spec-Driven Development (Spec Kit)](#spec-driven-development-spec-kit)

---

## Overview

SupremeAI agents are autonomous AI entities that use Large Language Models (LLMs) to perform tasks, interact with users, and utilize external tools. Each agent operates within defined boundaries with human oversight for sensitive operations.

### Core Principles

1. **Autonomy with Oversight** - Agents operate independently but require approval for sensitive actions
2. **Transparency** - All agent decisions and actions are logged and auditable
3. **Safety First** - Built-in guards against harmful outputs and actions
4. **Context Awareness** - Agents maintain awareness of conversation history and user preferences
5. **Graceful Degradation** - Handle failures gracefully without data loss

---

## Agent Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Create  │───>│ Active   │───>│ Paused   │───>│ Archived │
│          │    │          │    │          │    │          │
└──────────┘    └────┬─────┘    └────┬─────┘    └──────────┘
                      │               │
                      v               v
                 ┌──────────┐   ┌──────────┐
                 │ Error    │   │ Deleted  │
                 │ State    │   │          │
                 └──────────┘   └──────────┘
```

### States

| State | Description | Transitions |
|-------|-------------|-------------|
| `active` | Agent is fully operational | From: create, paused |
| `paused` | Temporarily suspended | From: active, error |
| `archived` | Read-only, preserved | From: active, paused |
| `error` | Requires intervention | From: active (on failure) |
| `deleted` | Scheduled for removal | From: any state |

---

## Configuration Schema

### Base Configuration

```json
{
  "id": "uuid",
  "name": "Agent Name",
  "description": "What this agent does",
  "version": "1.0.0",
  
  "model": {
    "primary": "gpt-4-turbo",
    "fallback": "gpt-4o-mini",
    "max_tokens": 2048,
    "temperature": 0.7,
    "top_p": 0.9,
    "frequency_penalty": 0.5,
    "presence_penalty": 0.3
  },
  
  "system_prompt": "You are a helpful assistant...",
  
  "behavior": {
    "response_style": "professional",
    "language": "auto-detect",
    "formality_level": 0.7,
    "verbosity": "balanced"
  }
}
```

### Memory Configuration

```json
{
  "memory": {
    "working_memory": {
      "enabled": true,
      "max_tokens": 8000,
      "summarize_threshold": 6000,
      "summary_model": "gpt-4o-mini"
    },
    
    "long_term_memory": {
      "enabled": true,
      "vector_store": "pgvector",
      "embedding_model": "text-embedding-ada-002",
      "dimensions": 1536,
      "similarity_threshold": 0.75,
      "max_results": 10,
      "auto_store": true,
      "importance_threshold": 0.6
    },
    
    "episodic_memory": {
      "enabled": true,
      "store_interactions": true,
      "retention_days": 365,
      "auto_tag": true
    }
  }
}
```

### Tool Configuration

```json
{
  "tools": {
    "enabled": ["web_search", "calculator", "code_interpreter"],
    
    "tool_settings": {
      "web_search": {
        "max_results": 5,
        "search_depth": "basic",
        "include_snippets": true
      },
      
      "calculator": {
        "precision": 6,
        "allow_scientific": true
      },
      
      "code_interpreter": {
        "timeout_seconds": 30,
        "allowed_libraries": ["numpy", "pandas", "matplotlib"],
        "sandboxed": true,
        "memory_limit": "512MB"
      }
    },
    
    "constraints": {
      "max_tools_per_message": 5,
      "max_tool_chain_depth": 3,
      "require_intent_declaration": true
    }
  }
}
```

### HITL Configuration

```json
{
  "hitl": {
    "enabled": true,
    
    "approval_required_for": [
      "file_write",
      "file_delete", 
      "file_modify",
      "external_api_call",
      "database_write",
      "database_delete",
      "code_execution",
      "data_export",
      "user_management",
      "config_change"
    ],
    
    "auto_approve": [
      "web_search",
      "calculator",
      "read_operation",
      "internal_lookup"
    ],
    
    "settings": {
      "default_priority": "medium",
      "timeout_minutes": 30,
      "escalate_on_timeout": true,
      "require_reason": true,
      "allow_payload_modification": true
    },
    
    "notifications": {
      "on_request": true,
      "on_approval": true,
      "on_rejection": true,
      "on_expiry": true,
      "channels": ["in_app", "email"]
    }
  }
}
```

### Safety Configuration

```json
{
  "safety": {
    "content_filtering": {
      "enabled": true,
      "block_harmful_content": true,
      "block_pii": true,
      "custom_blocklist": []
    },
    
    "output_validation": {
      "check_code_execution": true,
      "check_urls": true,
      "check_file_paths": true,
      "max_output_length": 50000
    },
    
    "rate_limits": {
      "messages_per_minute": 20,
      "tokens_per_hour": 100000,
      "tools_per_conversation": 100
    },
    
    "emergency_stop": {
      "enabled": true,
      "trigger_keywords": ["emergency stop", "halt all operations"],
      "notify_admins": true
    }
  }
}
```

---

## Memory System

### Working Memory (Short-Term)

Working memory holds the current conversation context and is cleared when the session ends.

**Structure:**
```json
{
  "conversation_id": "uuid",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "current_goals": [],
  "intermediate_results": {},
  "token_count": 1500
}
```

**Management Rules:**
- Auto-summarize when approaching token limit
- Prioritize recent messages over older ones
- Preserve system prompt always
- Maintain tool call context for continuity

### Episodic Memory (Long-Term)

Significant interactions stored as vector embeddings for semantic search.

**Storage Triggers:**
- User explicitly states preference/fact
- Agent learns new information during task
- Important decision or conclusion reached
- Error encountered and resolved

**Schema:**
```json
{
  "memory_id": "uuid",
  "agent_id": "uuid",
  "user_id": "uuid",
  "content": "User prefers dark mode interface",
  "embedding": [0.0012, -0.0034, ...],
  "memory_type": "preference|fact|interaction|knowledge",
  "metadata": {
    "source": "conversation",
    "confidence": 0.9,
    "context": {...}
  },
  "importance": 0.8,
  "tags": ["ui", "preferences"],
  "created_at": "2025-01-01T00:00:00Z"
}
```

### Procedural Memory

Pre-defined knowledge and skills configured by developers.

**Types:**
1. **Response Templates** - Standard formats for common queries
2. **SOPs** - Step-by-step procedures for complex tasks
3. **Domain Knowledge** - Subject-matter expertise
4. **Error Handling** - Known issues and resolutions

---

## Tool System

### Available Tools

#### web_search
Search the internet for current information.

```json
{
  "name": "web_search",
  "description": "Search the web for real-time information",
  "parameters": {
    "query": {"type": "string", "required": true, "description": "Search query"},
    "num_results": {"type": "integer", "default": 5, "min": 1, "max": 20},
    "search_type": {"type": "enum", "values": ["news", "general", "scholar"]}
  },
  "returns": {
    "results": [{"title", "url", "snippet", "source"}]
  },
  "hitl_required": false
}
```

#### calculator
Perform mathematical calculations safely.

```json
{
  "name": "calculator",
  "description": "Evaluate mathematical expressions",
  "parameters": {
    "expression": {"type": "string", "required": true},
    "precision": {"type": "integer", "default": 6}
  },
  "returns": {
    "result": "number|string",
    "formatted": "string"
  },
  "hitl_required": false
}
```

#### code_interpreter
Execute Python code in a sandboxed environment.

```json
{
  "name": "code_interpreter",
  "description": "Execute Python code for data analysis, visualization, computation",
  "parameters": {
    "code": {"type": "string", "required": true},
    "timeout": {"type": "integer", "default": 30, "max": 120},
    "libraries": {"type": "array", "items": "string"}
  },
  "returns": {
    "stdout": "string",
    "stderr": "string",
    "images": [{"format", "data"}],
    "execution_time_ms": "number"
  },
  "hitl_required": true
}
```

#### file_manager
Read, write, list, and manage files within allowed directories.

```json
{
  "name": "file_manager",
  "description": "Perform file system operations within allowed directories",
  "parameters": {
    "action": {"type": "enum", "values": ["read", "write", "append", "delete", "list"], "required": true},
    "path": {"type": "string", "required": true},
    "content": {"type": "string"},
    "encoding": {"type": "enum", "values": ["utf-8", "ascii"], "default": "utf-8"}
  },
  "returns": {
    "success": "boolean",
    "content": "string",
    "files": ["string"]
  },
  "hitl_required": true
}
```

#### sql_query
Execute read-only SQL queries against the database.

```json
{
  "name": "sql_query",
  "description": "Execute read-only SQL queries for data retrieval",
  "parameters": {
    "query": {"type": "string", "required": true},
    "database": {"type": "string", "default": "primary"},
    "limit": {"type": "integer", "default": 1000, "max": 10000}
  },
  "returns": {
    "columns": ["string"],
    "rows": [[...]],
    "row_count": "number",
    "execution_time_ms": "number"
  },
  "hitl_required": true
}
```

#### api_client
Make HTTP requests to external APIs.

```json
{
  "name": "api_client",
  "description": "Make HTTP requests to external APIs and services",
  "parameters": {
    "url": {"type": "string", "required": true},
    "method": {"type": "enum", "values": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
    "headers": {"type": "object"},
    "body": {"type": "object|string"},
    "timeout": {"type": "integer", "default": 30}
  },
  "returns": {
    "status_code": "number",
    "headers": "object",
    "body": "object|string"
  },
  "hitl_required": true
}
```

### Tool Usage Protocol

1. **Declare Intent** - Before using any tool, explain what you want to accomplish
2. **Validate Parameters** - Ensure all required parameters are provided and valid
3. **Execute Safely** - Use tools only for their intended purpose
4. **Report Results** - Clearly communicate tool results to user
5. **Handle Errors** - Gracefully handle tool failures with helpful messages

---

## HITL Guidelines

### When HITL is Triggered

The Human-in-the-Loop system activates when an agent attempts:

**Always Require Approval:**
- Writing/modifying/deleting files
- Making external API calls
- Executing database modifications
- Running code execution
- Exporting bulk data
- Managing user accounts
- Changing system configuration

**Never Require Approval:**
- Web searches
- Calculations
- Reading files/data
- Internal lookups
- Formatting responses

### Approval Process Flow

```
Agent Action Request
        │
        ▼
┌───────────────────┐
│ Classify Action   │──> Is it auto-approved?
└────────┬──────────┘         │
         │              Yes  │ No
         ▼                   ▼
┌───────────────────┐  ┌───────────────────┐
│ Queue for Review  │  │ Execute Immediately│
│ Set Priority      │  └───────────────────┘
│ Set Expiry        │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Notify Reviewers  │
│ (In-app + Email)  │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐     ┌───────────────────┐
│ Awaiting Decision │────>│ Approved           │
│                   │     │ Execute & Log      │
├───────────────────┤     ├───────────────────┤
│                   │────>│ Rejected           │
│                   │     │ Notify Agent       │
├───────────────────┤     ├───────────────────┤
│                   │────>│ Expired            │
│                   │     │ Cancel & Notify    │
└───────────────────┘     └───────────────────┘
```

### Best Practices for Agents

1. **Batch Related Actions** - Group multiple related actions into one approval request when possible
2. **Provide Context** - Include clear explanation of why action is needed
3. **Estimate Impact** - Describe potential effects of the action
4. **Suggest Alternatives** - If action seems risky, suggest safer alternatives
5. **Respect Timeouts** - Don't queue actions that might expire before review

---

## Safety Protocols

### Content Filtering

Agents must automatically detect and handle:

**PII Patterns to Redact:**
- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- Physical addresses
- IP addresses (when not necessary)

**Content to Block:**
- Hate speech
- Violence promotion
- Illegal activities
- Self-harm content
- Sexual explicit material (unless appropriate context)
- Malicious code generation

### Input Validation

All user inputs must be validated:
- SQL injection prevention (parameterized queries only)
- XSS prevention (output encoding)
- Path traversal prevention (allowed directories only)
- Command injection prevention (no shell execution)
- Prompt injection detection (special handling)

### Output Sanitization

Before returning responses:
- Remove accidental PII disclosure
- Validate URLs are safe
- Check file paths don't expose sensitive locations
- Ensure code examples are safe
- Limit output length to prevent abuse

---

## Anti-Pattern Prevention

### Known Anti-Patterns and Mitigations

| Anti-Pattern | Description | Our Mitigation |
|--------------|-------------|----------------|
| **Prompt-and-Pray** | Sending vague prompts hoping for good results | Structured prompts with validation schemas |
| **Memory Amnesia** | Forgetting important context between sessions | Three-tier memory with persistent storage |
| **Silent Failure** | Failing without notification or logging | Comprehensive error handling + alerting |
| **Loop Trap** | Getting stuck in repetitive action loops | Max iteration limits + timeout guards |
| **Context Overflow** | Exceeding context window limits | Automatic summarization + pruning |
| **Tool Hallucination** | Using non-existent tools or wrong parameters | Schema validation + result checking |
| **Permission Creep** | Gradually gaining unauthorized access | RBAC + HITL for all sensitive ops |
| **Cascade Failure** | One failure causing system-wide outage | Circuit breakers + isolation |
| **Observability Gap** | Unable to understand agent behavior | Full OpenTelemetry tracing |
| **Cost Runaway** | Uncontrolled API spending | Token budgets + spend alerts |

### Implementation Details

#### Loop Trap Prevention
```python
MAX_ITERATIONS = 10
TIMEOUT_SECONDS = 300

async def execute_with_guardrails(agent, task):
    iterations = 0
    start_time = time.time()
    
    while iterations < MAX_ITERATIONS:
        if time.time() - start_time > TIMEOUT_SECONDS:
            raise TimeoutError("Agent exceeded maximum execution time")
        
        result = await agent.step(task)
        
        if result.is_complete():
            return result
        
        if result.is_repeating():
            raise LoopDetectedError("Agent detected in repetition loop")
        
        iterations += 1
    
    raise MaxIterationsError(f"Agent exceeded {MAX_ITERATIONS} iterations")
```

#### Context Overflow Prevention
```python
def manage_context(messages, max_tokens=8000):
    current_tokens = count_tokens(messages)
    
    if current_tokens > max_tokens * 0.8:
        # Summarize oldest messages
        summary = summarize_messages(messages[:-3])
        # Keep system prompt + summary + recent messages
        return [
            messages[0],  # System prompt
            Message(role="system", content=f"Previous context summary: {summary}"),
            *messages[-3:]  # Keep last 3 messages
        ]
    
    return messages
```

---

## Best Practices

### For Agent Developers

1. **Clear System Prompts**
   ```
   Bad: "You are an assistant."
   Good: "You are a research assistant specializing in academic papers.
         Your role is to help users find, analyze, and summarize research.
         Always cite sources and distinguish facts from opinions."
   ```

2. **Define Tool Boundaries**
   - Only enable tools the agent actually needs
   - Set appropriate timeouts
   - Configure HITL for risky operations

3. **Memory Strategy**
   - Decide what's worth remembering long-term
   - Set appropriate importance thresholds
   - Regularly review and clean old memories

4. **Error Handling**
   - Anticipate failure modes
   - Provide helpful error messages
   - Enable graceful degradation

5. **Testing**
   - Test with various input types
   - Test edge cases and boundaries
   - Test failure scenarios

### For Agent Operators

1. **Monitor HITL Queue**
   - Review pending approvals promptly
   - Set up notifications
   - Escalate if overloaded

2. **Review Agent Performance**
   - Check success rates
   - Monitor response times
   - Review user feedback

3. **Update Configurations**
   - Adjust prompts based on performance
   - Update tool permissions as needed
   - Tune safety settings

4. **Security Hygiene**
   - Rotate secrets regularly
   - Review access logs
   - Update blocklists

### For Users Interacting with Agents

1. **Be Specific**
   - Provide clear, detailed requests
   - Include relevant context
   - Specify desired output format

2. **Provide Feedback**
   - Rate helpful responses
   - Report issues
   - Suggest improvements

3. **Understand Limitations**
   - Agents can make mistakes
   - Verify important information
   - Use HITL for sensitive tasks

---

## Spec-Driven Development (Spec Kit)

This document governs **AI-agent operating behavior**. Engineering principles for
feature work are governed separately by the Spec Kit constitution. The two must
never contradict; if a conflict is found, stop and resolve it before implementation.

For feature development using Spec-Driven Development, see:

| Artifact | Path | Purpose |
|---|---|---|
| SDD Engineering Constitution | `.specify/memory/constitution.md` | Project-level engineering principles for SDD |
| Adoption policy & artifact ownership | `docs/SPEC_KIT_ADOPTION.md` | Feature classification, quality gates, governance |
| Agent workflows | `.clinerules/workflows/speckit-*.md` | `/speckit.*` slash-command workflows |

### Operating Rule

Before implementing a Class B or Class C feature (see
`docs/SPEC_KIT_ADOPTION.md`), determine whether there is an active Spec Kit
feature specification. If none exists, create one through the approved Spec Kit
workflow (`/speckit.specify` and related commands). Do not implement major
behavior directly from a loose request when the change affects security, data,
architecture, deployment, billing, tenancy, or external integrations.

### Additional Agent Obligations

1. Read `AGENTS.md` (this file) before major work.
2. Read the Spec Kit constitution (`.specify/memory/constitution.md`) before planning SDD work.
3. Reuse existing architecture before creating new subsystems (Principle VI).
4. Never store secrets in specs, plans, or tasks.
5. Run `analyze` before major implementation.
6. Run tests and security checks after implementation.
7. Run `converge` before declaring a Class C feature complete; if convergence
   identifies gaps, implement the added tasks and converge again.
8. Do not delete historical feature artifacts under `specs/`.
9. Do not rewrite unrelated architecture while implementing a bounded feature.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-08-29 | Added Spec-Driven Development (Spec Kit) section; fixed heading prefix |
| 1.0.0 | 2025-08-26 | Initial release |

---

## Support

For questions about agent configuration:
- Documentation: See main README.md
- Issues: GitHub Issues
- Discussions: GitHub Discussions

For security concerns: security@supremeai.app
