import asyncio
import base64
import logging

from discord.ext import voice_recv

from .audio import discord_to_openai, openai_to_discord
from .realtime import RealtimeClient
from .sink import OpenAIRealtimeSink
from .source import RealtimeAudioSource

log = logging.getLogger(__name__)


class VoiceSession:
    """Orchestrates bidirectional audio between Discord and OpenAI Realtime API."""

    def __init__(self, voice_client, user_id: int, user_name: str):
        self._voice_client: voice_recv.VoiceRecvClient = voice_client
        self._user_id = user_id
        self._user_name = user_name
        self._realtime = RealtimeClient(user_name)
        self._source = RealtimeAudioSource()
        self._sink: OpenAIRealtimeSink | None = None
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        await self._realtime.connect()

        self._voice_client.play(self._source)

        self._sink = OpenAIRealtimeSink(self._user_id, loop)
        self._voice_client.listen(self._sink)

        self._tasks = [
            asyncio.create_task(self._send_audio_loop()),
            asyncio.create_task(self._receive_events_loop()),
        ]

    async def _send_audio_loop(self) -> None:
        log.info("Send audio loop started")
        count = 0
        try:
            while True:
                pcm = await self._sink.queue.get()
                converted = discord_to_openai(pcm)
                await self._realtime.send_audio(converted)
                count += 1
                if count % 50 == 0:
                    log.debug("Sent %d audio chunks to OpenAI", count)
        except asyncio.CancelledError:
            log.info("Send audio loop cancelled after %d chunks", count)
        except Exception as e:
            log.error("Send audio loop error: %s", e, exc_info=True)

    async def _receive_events_loop(self) -> None:
        log.info("Receive events loop started")
        try:
            async for event in self._realtime.receive_events():
                event_type = event.get("type", "")
                log.debug("OpenAI event: %s", event_type)

                if event_type == "response.audio.delta":
                    audio_bytes = base64.b64decode(event["delta"])
                    converted = openai_to_discord(audio_bytes)
                    self._source.append_audio(converted)

                elif event_type == "input_audio_buffer.speech_started":
                    self._source.clear_buffer()

                elif event_type == "error":
                    log.error("OpenAI Realtime error: %s", event.get("error"))

                elif event_type == "session.created":
                    log.info("OpenAI Realtime session created")

            log.warning("OpenAI event stream ended")
        except asyncio.CancelledError:
            log.info("Receive events loop cancelled")
        except Exception as e:
            log.error("Receive events loop error: %s", e, exc_info=True)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._voice_client.is_playing():
            self._voice_client.stop()

        if self._voice_client.is_listening():
            self._voice_client.stop_listening()

        await self._realtime.close()

        if self._voice_client.is_connected():
            await self._voice_client.disconnect()
