import base64
import json
import logging
from datetime import datetime

import websockets

from ...utils.settings import (
    OPENAI_API_KEY,
    OPENAI_REALTIME_MODEL,
    OPENAI_REALTIME_VOICE,
)
from ..prompts import VOICE_SYSTEM_PROMPT

log = logging.getLogger(__name__)


class RealtimeClient:
    """Async WebSocket client for the OpenAI Realtime API."""

    def __init__(self, user_name: str):
        self._ws = None
        self._user_name = user_name

    async def connect(self) -> None:
        url = f"wss://api.openai.com/v1/realtime?model={OPENAI_REALTIME_MODEL}"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(
            url, additional_headers=headers, max_size=None
        )

        instructions = VOICE_SYSTEM_PROMPT.format(
            user_name=self._user_name,
            today_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": OPENAI_REALTIME_VOICE,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "language": "en",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "silence_duration_ms": 500,
                },
            },
        }
        await self._ws.send(json.dumps(session_config))
        log.info("OpenAI Realtime session config sent for user %s", self._user_name)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if self._ws is None:
            return
        event = {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm_bytes).decode(),
        }
        await self._ws.send(json.dumps(event))

    async def receive_events(self):
        """Async generator yielding parsed JSON events from the WebSocket."""
        if self._ws is None:
            return
        async for message in self._ws:
            yield json.loads(message)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
