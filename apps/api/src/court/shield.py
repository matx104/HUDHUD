"""Prompt Shields on a viewer's question before any model reads it (court.ask).

A question is free text that goes to a model, so it is the one place in the studio a viewer can
try to instruct the model instead of asking about the match. Azure AI Content Safety's Prompt
Shields, on the same Foundry resource and signed in with Entra ID as everything else, reads each
question first. One it flags as an attack gets fixed words back, and no model is given it.

If the shield can't be reached, the question still gets an answer, but not from a model: the
offline answerer (code, no model) takes it. So a model only ever reads a question the shield
passed, and an outage costs the models' answer, never the answer.

    CONTENT_SAFETY_ENDPOINT   the Foundry resource's endpoint (https://<name>.cognitiveservices...)
"""

import asyncio
import json

from .speech import Post, _aiohttp_post

API = "contentsafety/text:shieldPrompt?api-version=2024-09-01"
SCOPE = "https://cognitiveservices.azure.com/.default"


class Shield:
    def __init__(
        self,
        endpoint: str,
        *,
        credential=None,
        post: Post | None = None,
        timeout_s: float = 6.0,
    ) -> None:
        self.url = f"{endpoint.rstrip('/')}/{API}"
        self._credential = credential
        self._post = post or _aiohttp_post
        self.timeout_s = timeout_s

    async def attack(self, question: str) -> bool | None:
        """True if the shield flags the question as an attack, False if it passes, None if the
        shield couldn't say."""
        try:
            if self._credential is None:
                from .identity import credential

                self._credential = credential(aio=True)
            # The sign-in is outside the time limit: the first token can be slow to fetch, and
            # it is cached after that. The limit is for the shield itself.
            token = await self._credential.get_token(SCOPE)
            return await asyncio.wait_for(self._screen(question, token.token), self.timeout_s)
        except Exception:  # no verdict: the caller keeps the models away from the question
            return None

    async def _screen(self, question: str, token: str) -> bool | None:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "hudhud-studio",
        }
        body = json.dumps({"userPrompt": question, "documents": []}).encode()
        status, reply = await self._post(self.url, headers, body)
        if status != 200:
            return None
        return bool(json.loads(reply)["userPromptAnalysis"]["attackDetected"])
