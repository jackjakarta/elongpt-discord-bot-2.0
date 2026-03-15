import struct


def discord_to_openai(pcm: bytes) -> bytes:
    """Convert 48kHz stereo PCM16 (Discord) to 24kHz mono PCM16 (OpenAI).

    Averages left and right channels, then decimates by 2 (take every other sample).
    """
    num_samples = len(pcm) // 4  # 2 bytes per sample, 2 channels
    samples = struct.unpack(f"<{num_samples * 2}h", pcm)

    mono = []
    for i in range(0, len(samples), 4):  # step by 4: skip every other stereo pair
        if i + 1 < len(samples):
            avg = (samples[i] + samples[i + 1]) // 2
            mono.append(avg)

    return struct.pack(f"<{len(mono)}h", *mono)


def openai_to_discord(pcm: bytes) -> bytes:
    """Convert 24kHz mono PCM16 (OpenAI) to 48kHz stereo PCM16 (Discord).

    Duplicates each sample for 2x upsample, then duplicates to stereo.
    """
    num_samples = len(pcm) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm)

    stereo = []
    for s in samples:
        # Duplicate sample for upsample, duplicate channel for stereo
        stereo.extend([s, s, s, s])

    return struct.pack(f"<{len(stereo)}h", *stereo)
