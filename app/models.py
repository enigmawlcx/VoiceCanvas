from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ALLOWED_BITRATES = (32000, 64000, 128000, 256000)
Bitrate = Literal[32000, 64000, 128000, 256000]


def _default_save_dir() -> str:
    return str(Path.home() / "Music" / "VoiceCanvas")


class AppConfig(BaseModel):
    default_model: str = "speech-2.8-hd"
    default_format: str = "mp3"
    default_sample_rate: int = 32000
    default_bitrate: Bitrate = 256000
    save_dir: str = Field(default_factory=_default_save_dir)
    base_url: str = "https://api.minimaxi.com"
    group_id: str = ""
    price_per_1k_chars: float = 0
    price_per_1k_tokens: float = 0
