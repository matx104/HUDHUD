"""The commentary, spoken: Azure AI Speech reads each verified line aloud, for fans who can't
watch the screen, and hears a question asked out loud (court.ask), for fans who can't type it.

Only lines that aired can be spoken. The studio asks for a cue by its id, never for free text, so
the voice says exactly what the Critic passed, in the language it aired in: English, Urdu or
Arabic, each with a neural voice. The voices live on the same Foundry resource as the models (one
AIServices account), and the studio signs in with Entra ID as it does everywhere: no keys. A daily
character budget caps the bill, as the daily model budget does for the narration.

A question asked out loud is recorded in the page as 16 kHz mono WAV, at most MAX_LISTEN_S long,
and sent to speech to text (the REST API for short audio) in the session's language. Only the words
come back: the audio is kept nowhere. A daily budget of seconds caps what listening costs.

    SPEECH_RESOURCE_ID   the Foundry resource's id (the token names it: aad#<id>#<token>)
    SPEECH_REGION        its region, for the endpoint (uaenorth)
"""

import json
import struct
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from xml.sax.saxutils import escape

# A voice for each language the broadcast speaks: (the SSML language, the neural voice).
VOICES = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "ur": ("ur-PK", "ur-PK-AsadNeural"),
    "ar": ("ar-AE", "ar-AE-HamdanNeural"),
}
# Speech to text knows each language by its own locale: Urdu is heard as ur-IN (the service
# lists no ur-PK for it), though it's spoken in the ur-PK voice.
LISTEN = {"en": "en-GB", "ur": "ur-IN", "ar": "ar-AE"}
FORMAT = "audio-24khz-48kbitrate-mono-mp3"
SCOPE = "https://cognitiveservices.azure.com/.default"
DAILY_CHARS = 150_000  # about 1,000 lines a day; neural voices cost about $15 per million
MAX_LISTEN_S = 15  # one question, said aloud
DAILY_LISTEN_S = 1800  # half an hour of questions a day; speech to text costs about $1 an hour
WAV_RATE = 16_000  # samples a second, 16-bit mono: what the short-audio API takes

# Sends the request: (url, headers, body) -> (status, audio bytes). aiohttp in the studio; a fake
# in the tests.
Post = Callable[[str, dict[str, str], bytes], Awaitable[tuple[int, bytes]]]


class SpeechBudgetSpent(RuntimeError):
    """Today's character budget for the voice is spent."""


class SpeechUnavailable(RuntimeError):
    """The voice service didn't answer with audio, or with words."""


class NothingHeard(ValueError):
    """The recording held no words the service could make out, or wasn't a recording it takes."""


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
        self.region = region
        self._listen_day, self.listened_s = None, 0.0

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

    async def listen(self, wav: bytes, lang: str) -> str:
        """The words of a question said aloud, in the session's language."""
        if lang not in VOICES:
            raise ValueError(f"no voice for {lang!r}")
        seconds = _wav_seconds(wav)
        today = datetime.now(UTC).date()
        if today != self._listen_day:
            self._listen_day, self.listened_s = today, 0.0
        if self.listened_s + seconds > DAILY_LISTEN_S:
            raise SpeechBudgetSpent("today's budget for listening is spent")
        self.listened_s += seconds
        if self._credential is None:
            from .identity import credential

            self._credential = credential(aio=True)
        token = await self._credential.get_token(SCOPE)
        locale = LISTEN[lang]
        url = (
            f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/"
            f"cognitiveservices/v1?language={locale}&format=simple"
        )
        headers = {
            "Authorization": f"Bearer aad#{self.resource_id}#{token.token}",
            "Content-Type": f"audio/wav; codecs=audio/pcm; samplerate={WAV_RATE}",
            "Accept": "application/json",
            "User-Agent": "hudhud-studio",
        }
        status, body = await self._post(url, headers, wav)
        if status != 200:
            raise SpeechUnavailable(f"listening answered {status}")
        result = json.loads(body or b"{}")
        text = (result.get("DisplayText") or "").strip()
        if result.get("RecognitionStatus") != "Success" or not text:
            raise NothingHeard("no words could be made out: try again, a little closer")
        return text


def _wav_seconds(wav: bytes) -> float:
    """How long a recording is, if it's the 16 kHz mono 16-bit WAV the page records, and short."""
    if len(wav) < 44 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise NothingHeard("that isn't a WAV recording")
    channels, rate = struct.unpack_from("<HI", wav, 22)
    bits = struct.unpack_from("<H", wav, 34)[0]
    if (channels, rate, bits) != (1, WAV_RATE, 16):
        raise NothingHeard("the recording must be 16 kHz mono, 16-bit")
    seconds = (len(wav) - 44) / (WAV_RATE * 2)
    if seconds > MAX_LISTEN_S + 0.5:
        raise NothingHeard(f"a question can be at most {MAX_LISTEN_S} seconds long")
    return seconds


async def _aiohttp_post(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=20)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.post(url, headers=headers, data=body) as response,
    ):
        return response.status, await response.read()
