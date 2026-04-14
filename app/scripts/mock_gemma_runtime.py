from __future__ import annotations

import argparse
import json
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None


app = FastAPI(title="Mock Gemma Runtime", version="0.1.0")


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": "gemma-mock-local",
                "object": "model",
                "owned_by": "hotel-chipre-pms",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(payload: ChatCompletionRequest) -> dict[str, Any]:
    latest_user_message = _extract_latest_user_message(payload.messages)
    normalized = latest_user_message.lower()

    if any(token in normalized for token in ("reducir noches sueltas", "estadias largas", "estadías largas")):
        response_payload = {
            "mode": "proposal",
            "summary": "Propuesta para reducir noches sueltas y proteger estadias largas.",
            "answer": "Prepare una propuesta controlada para ajustar la politica de asignacion sin ejecutar cambios automaticamente.",
            "warnings": [],
            "missing_information": [],
            "confidence": 0.84,
            "requires_confirmation": True,
            "suggested_follow_up": ["Confirma el borrador si queres crear una sugerencia de politica."],
        }
    else:
        response_payload = {
            "mode": "analysis",
            "summary": "Respuesta de prueba del runtime local.",
            "answer": "El runtime local mock de Gemma esta respondiendo correctamente.",
            "warnings": [],
            "missing_information": [],
            "confidence": 0.92,
            "requires_confirmation": False,
            "suggested_follow_up": ["Pedi una propuesta de politica para probar confirmacion y borradores."],
        }

    return {
        "id": "chatcmpl-mock-gemma",
        "object": "chat.completion",
        "created": 0,
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(response_payload, ensure_ascii=True, sort_keys=True),
                },
                "finish_reason": "stop",
            }
        ],
    }


def _extract_latest_user_message(messages: list[ChatMessage]) -> str:
    for item in reversed(messages):
        if item.role == "user":
            return item.content
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock local OpenAI-compatible runtime for Gemma integration tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
