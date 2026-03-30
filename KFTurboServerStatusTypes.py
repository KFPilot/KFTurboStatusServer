# Killing Floor Turbo Server Status Shared Types
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BotConfig:
    localhost: str
    discord_token: Optional[str]
    channel_id: Optional[int]
    listen_port: int
    steam_api_key: str
    steam_api_url: str
    update_cooldown: float
    add_server_url : bool

@dataclass
class SteamProfile:
    steam_id: str
    persona_name: str

@dataclass
class PlayerEntry:
    steam_id: str
    perk : str

@dataclass
class ServerPayload:
    name: Optional[str]
    game: Optional[str]
    difficulty: Optional[str]
    map_file: Optional[str]
    map_name: Optional[str]
    final_wave: Optional[int]
    match_state: Optional[int]
    wave_state: Optional[int]
    player_count: Optional[int]
    player_max: Optional[int]
    spectator_count: Optional[int]
    player_list: list[PlayerEntry] = field(default_factory=list)
    spectator_list: list[str] = field(default_factory=list)
    session_id: Optional[str] = None
