# hermes/core/model_router.py
import os
from enum import Enum
from openai import AsyncOpenAI
import hermes.core.config as config

class TaskType(Enum):
    FAST_CHAT = "fast_chat"
    CODING = "coding"
    REASONING = "reasoning"
    PLANNING = "planning"
    RESEARCH = "research"
    VISION = "vision"
    EMBEDDING = "embedding"
    VOICE_STT = "voice_stt"
    HIGH_VOLUME = "high_volume"
    DEFAULT = "default"

MODEL_ROUTES = {
    TaskType.FAST_CHAT: {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
    TaskType.CODING: {
        "provider": "openrouter",
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    TaskType.REASONING: {
        "provider": "openrouter",
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    TaskType.PLANNING: {
        "provider": "openrouter",
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    TaskType.RESEARCH: {
        "provider": "openrouter",
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    TaskType.VISION: {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GOOGLE_API_KEY",
    },
    TaskType.HIGH_VOLUME: {
        "provider": "cerebras",
        "model": "llama-3.3-70b",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
    },
    TaskType.DEFAULT: {
        "provider": "openrouter",
        "model": "openrouter/free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    }
}

class ModelRouter:
    @staticmethod
    def get_route(task_type_str: str) -> dict:
        try:
            task_type = TaskType(task_type_str)
        except ValueError:
            task_type = TaskType.DEFAULT
            
        route = MODEL_ROUTES.get(task_type, MODEL_ROUTES[TaskType.DEFAULT])
        api_key = getattr(config, route["api_key_env"], None)
        
        # Graceful fallback if key is missing
        if not api_key:
            route = MODEL_ROUTES[TaskType.DEFAULT]
            api_key = getattr(config, route["api_key_env"], None)
            
        return {
            "model": route["model"],
            "base_url": route["base_url"],
            "api_key": api_key,
            "provider": route["provider"],
        }

    @staticmethod
    def get_client(task_type_str: str):
        route = ModelRouter.get_route(task_type_str)
        return AsyncOpenAI(
            base_url=route["base_url"],
            api_key=route["api_key"]
        )
