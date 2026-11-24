"""Structured-output DeepEval judge for an operator-configured OpenAI compatible service."""

import asyncio
import json
import httpx
from deepeval.models import DeepEvalBaseLLM
from .adapters import setting


class StructuredJudge(DeepEvalBaseLLM):
    def load_model(self):
        return self.model_name

    def get_model_name(self):
        return self.model_name

    def generate(self, prompt, schema=None):
        messages = [{"role": "user", "content": prompt}]
        if schema:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": "Return JSON conforming to "
                    + json.dumps(schema.model_json_schema()),
                },
            )
        r = httpx.post(
            setting("JUDGE_URL").rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + setting("JUDGE_KEY")},
            json={"model": self.model_name, "temperature": 0, "messages": messages},
            timeout=25,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(text) if schema else text

    async def a_generate(self, prompt, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)
