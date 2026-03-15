import asyncio
import logging

from discord.ext import voice_recv
from discord.opus import Decoder as OpusDecoder
from discord.opus import OpusError

log = logging.getLogger(__name__)


class OpenAIRealtimeSink(voice_recv.AudioSink):
    """Audio sink that captures voice from a specific user and queues it."""

    def __init__(self, target_user_id: int, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.target_user_id = target_user_id
        self.loop = loop
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = OpusDecoder()

    def wants_opus(self) -> bool:
        return True

    def write(self, user, data):
        if user is None or user.id != self.target_user_id:
            return

        opus_data = data.opus
        if not opus_data:
            return

        try:
            pcm = self._decoder.decode(opus_data, fec=False)
        except OpusError as e:
            log.debug("Opus decode error (packet dropped): %s", e)
            return

        self.loop.call_soon_threadsafe(self.queue.put_nowait, pcm)

    def cleanup(self):
        pass
