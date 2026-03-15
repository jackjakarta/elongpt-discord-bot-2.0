import threading

import discord

FRAME_SIZE = 3840  # 20ms at 48kHz stereo 16-bit
SILENCE = b"\x00" * FRAME_SIZE


class RealtimeAudioSource(discord.AudioSource):
    """Audio source that plays back OpenAI Realtime API responses in Discord."""

    def __init__(self):
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def read(self) -> bytes:
        with self._lock:
            if len(self._buffer) >= FRAME_SIZE:
                frame = bytes(self._buffer[:FRAME_SIZE])
                del self._buffer[:FRAME_SIZE]
                return frame
        return SILENCE

    def append_audio(self, data: bytes) -> None:
        with self._lock:
            self._buffer.extend(data)

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        self.clear_buffer()
