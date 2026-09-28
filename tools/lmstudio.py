from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LMStudioError(Exception):
    pass


class LMStudioClient:
    def __init__(self, api_url: str, model: str | None = None, timeout: int | None = None) -> None:
        self.api_url = api_url.rstrip("/")
        self.model = model or "local-model"
        self.timeout = timeout or int(os.getenv("LM_STUDIO_TIMEOUT", "100"))

    def chat(self, system: str, user: str, history: list[dict[str, str]] | None = None) -> str:
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user})
        payload = json.dumps({"model": self.model, "messages": messages,
            "temperature": 0.2}).encode("utf-8")
        request = Request(self.api_url + "/chat/completions", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except HTTPError as error:
            raise LMStudioError(f"HTTP {error.code}: {error.read().decode('utf-8', 'replace')[:300]}") from error
        except (URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as error:
            raise LMStudioError(
                f"Could not contact LM Studio or the request exceeded the {self.timeout}-second timeout. "
                "Check the server, or start the agent with a larger --timeout value."
            ) from error
