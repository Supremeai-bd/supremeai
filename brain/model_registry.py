from typing import Dict, Any, List

class ModelRegistry:
    """
    Registry of the Top 50 AI Models categorized by Tiers.
    Provides metadata such as provider, tier, context length, estimated cost, and OpenRouter/Ollama IDs.
    """
    
    MODELS: Dict[str, Dict[str, Any]] = {
        # TIER 1: FRONTIER MODELS (Ranks 1-10)
        "claude-opus-4.7": {
            "rank": 1,
            "tier": 1,
            "provider": "anthropic",
            "name": "Claude 4.7 Opus",
            "openrouter_id": "anthropic/claude-3-opus",  # Fallback to Opus
            "context_length": 200000,
            "cost_input_per_million": 15.00,
            "cost_output_per_million": 75.00,
            "strengths": ["complex coding", "agentic workflows", "deep reasoning"]
        },
        "gpt-5.5": {
            "rank": 2,
            "tier": 1,
            "provider": "openai",
            "name": "GPT-5.5",
            "openrouter_id": "openai/gpt-4o",  # Fallback to 4o
            "context_length": 128000,
            "cost_input_per_million": 5.00,
            "cost_output_per_million": 15.00,
            "strengths": ["general intelligence", "low hallucination", "structured output"]
        },
        "qwen-3.7-max": {
            "rank": 3,
            "tier": 1,
            "provider": "alibaba",
            "name": "Qwen 3.7 Max",
            "openrouter_id": "qwen/qwen-2.5-72b-instruct",
            "context_length": 128000,
            "cost_input_per_million": 2.50,
            "cost_output_per_million": 7.50,
            "strengths": ["tool calling", "long contexts", "coding"]
        },
        "claude-opus-4.6": {
            "rank": 4,
            "tier": 1,
            "provider": "anthropic",
            "name": "Claude 4.6 Opus",
            "openrouter_id": "anthropic/claude-3-opus",
            "context_length": 1000000,
            "cost_input_per_million": 15.00,
            "cost_output_per_million": 75.00,
            "strengths": ["large codebase", "agent teams"]
        },
        "claude-sonnet-4.6": {
            "rank": 5,
            "tier": 1,
            "provider": "anthropic",
            "name": "Claude 4.6 Sonnet",
            "openrouter_id": "anthropic/claude-3.5-sonnet",
            "context_length": 1000000,
            "cost_input_per_million": 3.00,
            "cost_output_per_million": 15.00,
            "strengths": ["coding", "balanced performance", "vision"]
        },
        "deepseek-v4-pro": {
            "rank": 6,
            "tier": 1,
            "provider": "deepseek",
            "name": "DeepSeek V4 Pro",
            "openrouter_id": "deepseek/deepseek-chat",
            "context_length": 128000,
            "cost_input_per_million": 0.14,
            "cost_output_per_million": 0.28,
            "strengths": ["math", "coding", "extreme cost efficiency"]
        },
        "gemini-3.1-pro": {
            "rank": 7,
            "tier": 1,
            "provider": "google",
            "name": "Gemini 3.1 Pro",
            "openrouter_id": "google/gemini-pro-1.5",
            "context_length": 1000000,
            "cost_input_per_million": 1.25,
            "cost_output_per_million": 5.00,
            "strengths": ["native tool calling", "massive context", "multimodal"]
        },
        "kimi-k2.6": {
            "rank": 8,
            "tier": 1,
            "provider": "moonshot",
            "name": "Kimi K2.6",
            "openrouter_id": "moonshot/kimi-chat",
            "context_length": 128000,
            "cost_input_per_million": 1.00,
            "cost_output_per_million": 4.00,
            "strengths": ["agent swarms", "autonomous tasks"]
        },
        "gpt-5.4-pro": {
            "rank": 9,
            "tier": 1,
            "provider": "openai",
            "name": "GPT-5.4 Pro",
            "openrouter_id": "openai/gpt-4-turbo",
            "context_length": 128000,
            "cost_input_per_million": 10.00,
            "cost_output_per_million": 30.00,
            "strengths": ["reasoning", "academic questions"]
        },
        "claude-opus-4.8": {
            "rank": 10,
            "tier": 1,
            "provider": "anthropic",
            "name": "Claude 4.8 Opus",
            "openrouter_id": "anthropic/claude-3-opus",
            "context_length": 1000000,
            "cost_input_per_million": 15.00,
            "cost_output_per_million": 75.00,
            "strengths": ["sustained coding", "ide assistance"]
        },

        # TIER 2: HIGH-PERFORMANCE (Ranks 11-20)
        "gemini-3.5-flash": {
            "rank": 11,
            "tier": 2,
            "provider": "google",
            "name": "Gemini 3.5 Flash",
            "openrouter_id": "google/gemini-flash-1.5",
            "context_length": 1000000,
            "cost_input_per_million": 0.075,
            "cost_output_per_million": 0.30,
            "strengths": ["speed", "multimodal", "value coding"]
        },
        "gpt-5.2": {
            "rank": 12,
            "tier": 2,
            "provider": "openai",
            "name": "GPT-5.2",
            "openrouter_id": "openai/gpt-4o-mini",
            "context_length": 128000,
            "cost_input_per_million": 0.15,
            "cost_output_per_million": 0.60,
            "strengths": ["general knowledge", "agent routing"]
        },
        "llama-4-maverick": {
            "rank": 13,
            "tier": 2,
            "provider": "meta",
            "name": "Llama 4 Maverick",
            "openrouter_id": "meta-llama/llama-3.1-405b-instruct",
            "context_length": 1000000,
            "cost_input_per_million": 2.66,
            "cost_output_per_million": 2.66,
            "strengths": ["open source", "vision", "complex reasoning"]
        },
        "grok-4.3": {
            "rank": 14,
            "tier": 2,
            "provider": "xai",
            "name": "Grok 4.3",
            "openrouter_id": "x-ai/grok-chat",
            "context_length": 131000,
            "cost_input_per_million": 2.00,
            "cost_output_per_million": 10.00,
            "strengths": ["real-time info", "fast chat"]
        },
        "glm-5": {
            "rank": 15,
            "tier": 2,
            "provider": "zhipu",
            "name": "GLM-5",
            "openrouter_id": "thm/glm-4-9b-chat",
            "context_length": 128000,
            "cost_input_per_million": 0.50,
            "cost_output_per_million": 1.50,
            "strengths": ["multilingual", "chinese translation"]
        },

        # TIER 5: FREE TIER (Ranks 41-50)
        "deepseek-r1-free": {
            "rank": 41,
            "tier": 5,
            "provider": "deepseek",
            "name": "DeepSeek-R1 (Free)",
            "openrouter_id": "deepseek/deepseek-r1:free",
            "context_length": 64000,
            "cost_input_per_million": 0.00,
            "cost_output_per_million": 0.00,
            "strengths": ["reasoning", "math", "coding"]
        },
        "llama-4-scout-free": {
            "rank": 42,
            "tier": 5,
            "provider": "meta",
            "name": "Llama 4 Scout (Free)",
            "openrouter_id": "meta-llama/llama-3.2-3b-instruct:free",
            "context_length": 1000000,
            "cost_input_per_million": 0.00,
            "cost_output_per_million": 0.00,
            "strengths": ["zero cost vision", "summaries"]
        },
        "qwen3-free": {
            "rank": 43,
            "tier": 5,
            "provider": "alibaba",
            "name": "Qwen 3 (Free)",
            "openrouter_id": "qwen/qwen-2-7b-instruct:free",
            "context_length": 128000,
            "cost_input_per_million": 0.00,
            "cost_output_per_million": 0.00,
            "strengths": ["coding", "general automation"]
        },
        # Local Fallbacks (Tier 0)
        "local-qwen-0.5b": {
            "rank": 50,
            "tier": 0,
            "provider": "ollama",
            "name": "Qwen 0.5B (Local)",
            "ollama_id": "qwen:0.5b",
            "context_length": 32000,
            "cost_input_per_million": 0.00,
            "cost_output_per_million": 0.00,
            "strengths": ["fast offline replies", "local security"]
        }
    }

    @classmethod
    def get_model(cls, model_id: str) -> Dict[str, Any]:
        return cls.MODELS.get(model_id, {})

    @classmethod
    def get_by_tier(cls, tier: int) -> List[str]:
        return [mid for mid, m in cls.MODELS.items() if m["tier"] == tier]
