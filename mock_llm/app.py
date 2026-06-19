import json
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field

app = FastAPI(title="mock-llm", version="0.1.0")


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool | None = False


def _estimate_tokens(value: str) -> int:
    return max(1, len(value) // 4)


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return " ".join(parts)
    return json.dumps(content, ensure_ascii=False)


def build_mock_content(messages: list[ChatMessage]) -> str:
    _ = messages
    payload = {
        "oplysninger": (
            "Borger kontakter kommunen vedrørende opfølgning på en igangværende sag. "
            "Borger oplyser, at dokumentation tidligere er indsendt, og ønsker status på den videre behandling."
        ),
        "status": (
            "Borger er vejledt om den aktuelle sagsstatus og om forventet næste skridt i behandlingen. "
            "Det aftales, at borger afventer videre besked, hvis der bliver behov for supplerende oplysninger."
        ),
    }
    return f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"


@app.post("/openai/deployments/{deployment}/chat/completions")
def chat_completions(
    deployment: str,
    request: ChatCompletionRequest,
    api_version: str | None = Query(default=None, alias="api-version"),
    api_key: str | None = Header(default=None, alias="api-key"),
) -> dict[str, Any]:
    _ = api_version
    _ = api_key

    content = build_mock_content(request.messages)
    prompt_text = "\n".join(_stringify_content(message.content) for message in request.messages)
    prompt_tokens = _estimate_tokens(prompt_text)
    completion_tokens = _estimate_tokens(content)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model or deployment,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                },
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def run() -> None:
    import uvicorn

    uvicorn.run(
        "mock_llm.app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
