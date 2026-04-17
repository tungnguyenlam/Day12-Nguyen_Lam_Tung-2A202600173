"""
Mock LLM for the final 06 app.
"""
from __future__ import annotations

import random
import time


MOCK_RESPONSES = {
    "default": [
        "This is a mock response from the Day 12 final agent.",
        "The final agent is running in mock mode for this request.",
        "I am a mock assistant response used for deployment and reliability demos.",
    ],
    "docker": ["Docker packages the application and its runtime dependencies together."],
    "redis": ["Redis is used here for shared session state across instances."],
    "deploy": ["Deployment publishes the service so other users can access it."],
}


def ask(question: str, delay: float = 0.05) -> str:
    time.sleep(delay + random.uniform(0, 0.03))
    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
