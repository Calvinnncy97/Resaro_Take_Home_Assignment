import asyncio
import json
import os
import re
from typing import Optional

from dotenv import load_dotenv
from huggingface_hub import AsyncInferenceClient
from pydantic import BaseModel, ValidationError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    wait_exponential,
)

ENV_FILE = os.getenv("RESARO_ENV")
load_dotenv(dotenv_path=ENV_FILE)


_HF_GLOBAL_SEMAPHORE = asyncio.Semaphore(256)


def extract_json_string(text: str) -> Optional[str]:
    """
    Extracts a JSON string from a larger text body.

    This function handles two common formats:
    1. A JSON string embedded within a ```json ... ``` code block.
    2. A raw JSON string, identified by the first '{' and the last '}'.

    Args:
        text: The input string to search for a JSON string.

    Returns:
        The extracted JSON string if found, otherwise None.
    """
    json_str = None

    # Case 1: Look for ```json ... ```
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Case 2: Find first '{' and last '}'
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            json_str = text[start : end + 1].strip()

    if json_str:
        return json_str
    return None


class OssBaseAgent:
    """
    BaseAgent that uses Hugging Face Inference API
    """

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
    ):
        if api_key is None:
            api_key = os.getenv("HF_TOKEN")
        
        self.client = AsyncInferenceClient(
            model=model_name,
            token=api_key,
        )
        self.model_name = model_name

    @retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def generate(
        self,
        input: str,
        schema: BaseModel,
        think: bool = True,
        temperature: Optional[float] = None,
    ) -> BaseModel:
        async with _HF_GLOBAL_SEMAPHORE:
            if think:
                raw_json = await self._generate_with_think(
                    input, schema, temperature
                )
            else:
                raw_json = await self._generate_without_think(input, schema, temperature)

            return self._parse_and_validate_json(raw_json, input, schema)

    async def _generate_with_think(
        self,
        input_str: str,
        schema: BaseModel,
        temperature: Optional[float] = None,
    ) -> str:
        if temperature is None:
            temperature = 0.6

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": input_str
                + "\n\nThink it through. If the answer is obvious, give it directly. If not, use ≤10 short steps. You have a budget of ≤500 words for reasoning. Don't exceed it./think"
                + f"\n\nRespond with valid JSON matching this schema: {json.dumps(schema.model_json_schema())}",
            },
        ]

        response = await self.client.chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=0.95,
            max_tokens=6144,
        )
        
        return response.choices[0].message.content

    async def _generate_without_think(
        self,
        input_str: str,
        schema: BaseModel,
        temperature: Optional[float] = None,
    ) -> str:
        if temperature is None:
            temperature = 0.7

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": input_str + "/no_think"
                + f"\n\nRespond with valid JSON matching this schema: {json.dumps(schema.model_json_schema())}",
            },
        ]

        response = await self.client.chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=0.8,
            max_tokens=6144,
        )
        
        return response.choices[0].message.content

    def _parse_and_validate_json(
        self, raw_json: str, input_str: str, schema: BaseModel
    ) -> BaseModel:
        extracted_json = extract_json_string(raw_json)
        if extracted_json is None:
            raise ValueError(f"No valid JSON found in response:\n{raw_json}")
        try:
            response = schema.model_validate_json(extracted_json)
        except Exception as e:
            raise e
        return response


if __name__ == "__main__":
    import asyncio

    class HelloWorld(BaseModel):
        output: str

    async def main():
        LONG_SYSTEM_PROMPT = (
            "You are a helpful assistant. Return output: 'Hello World' in JSON."
        )

        agent = OssBaseAgent(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
        )

        # normal generation (cache auto-attached)
        response = await agent.generate(
            input=LONG_SYSTEM_PROMPT,
            schema=HelloWorld,
            think=True,
        )
        print(response)

    # Run the async main function
    asyncio.run(main())
