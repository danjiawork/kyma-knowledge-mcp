"""DeepEval custom LLM backed by GitHub Models (free via GITHUB_TOKEN)."""

from __future__ import annotations

import os

from deepeval.models.base_model import DeepEvalBaseLLM
from openai import OpenAI


class GitHubModelsLLM(DeepEvalBaseLLM):
    """Wraps GitHub Models OpenAI-compatible endpoint as a DeepEval judge model."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=os.environ["GITHUB_TOKEN"],
        )

    def load_model(self) -> OpenAI:
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model
