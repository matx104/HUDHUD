"""The commentary, spoken: Azure AI Speech reads each verified line aloud, for fans who can't
watch the screen.

Only lines that aired can be spoken. The studio asks for a cue by its id, never for free text, so
the voice says exactly what the Critic passed, in the language it aired in: English, Urdu or
Arabic, each with a neural voice. The voices live on the same Foundry resource as the models (one
AIServices account), and the studio signs in with Entra ID as it does everywhere: no keys. A daily
character budget caps the bill, as the daily model budget does for the narration.

    SPEECH_RESOURCE_ID   the Foundry resource's id (the token names it: aad#<id>#<token>)
    SPEECH_REGION        its region, for the endpoint (uaenorth)
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from xml.sax.saxutils import escape

# A voice for each language the broadcast speaks: (the SSML language, the neural voice).
VOICES = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "ur": ("ur-PK", "ur-PK-AsadNeural"),
    "ar": ("ar-AE", "ar-AE-HamdanNeural"),
}
FORMAT = "audio-24khz-48kbitrate-mono-mp3"
SCOPE = "https://cognitiveservices.azure.com/.default"
DAILY_CHARS = 150_000  # about 1,000 lines a day; neural voices cost about $15 per million

# Sends the request: (url, headers, body) -> (status, audio bytes). aiohttp in the studio; a fake
# in the tests.
Post = Callable[[str, dict[str, str], bytes], Awaitable[tuple[int, bytes]]]


class SpeechBudgetSpent(RuntimeError):
    """Today's character budget for the voice is spent."""


class SpeechUnavailable(RuntimeError):
    """The voice service didn't answer with audio."""


def ssml(text: str, lang: str) -> str:
    """The line as SSML for its language's voice. The text is escaped: it is never markup."""
    locale, voice = VOICES[lang]
    return (
        f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>"
        f"<prosody rate='+6%'>{escape(text)}</prosody></voice></speak>"
    )


class Voice:
    def __init__(
        self,
        *,
        resource_id: str,
        region: str,
        credential=None,
        post: Post | None = None,
        daily_chars: int = DAILY_CHARS,
    ) -> None:
        self.resource_id, self.daily_chars = resource_id, daily_chars
        self.url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self._credential = credential
        self._post = post or _aiohttp_post
        self._day, self.spent = None, 0

    def _charge(self, chars: int) -> None:
        today = datetime.now(UTC).date()
        if today != self._day:
            self._day, self.spent = today, 0
        if self.spent + chars > self.daily_chars:
            raise SpeechBudgetSpent("today's budget for the voice is spent")
        self.spent += chars

    async def speak(self, text: str, lang: str) -> bytes:
        """The line as MP3 audio."""
        if lang not in VOICES:
            raise ValueError(f"no voice for {lang!r}")
        self._charge(len(text))
        if self._credential is None:
            from .identity import credential

            self._credential = credential(aio=True)
        token = await self._credential.get_token(SCOPE)
        headers = {
            # Entra ID for Speech: the resource's id and the token, joined (no key exists).
            "Authorization": f"Bearer aad#{self.resource_id}#{token.token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": FORMAT,
            "User-Agent": "hudhud-studio",
        }
        status, audio = await self._post(self.url, headers, ssml(text, lang).encode())
        if status != 200 or not audio:
            raise SpeechUnavailable(f"the voice answered {status}")
        return audio


async def _aiohttp_post(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=20)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.post(url, headers=headers, data=body) as response,
    ):
        return response.status, await response.read()
