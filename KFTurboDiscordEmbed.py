# Killing Floor Turbo Server Status Embed Manager
# Manages the Discord client and embeds for server status display.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import discord
import asyncio
import json
import datetime
import os
import aiohttp
from typing import Callable, Coroutine
from pathlib import Path

from KFTurboServerStatusTypes import BotConfig, SteamProfile, PlayerEntry, ServerPayload

EmbedConfigPath = Path(__file__).parent / "serverembedconfig.json"
with open(EmbedConfigPath, "r", encoding="utf-8") as _f:
    EmbedConfig = json.load(_f)
ServerData = EmbedConfig["servers"]
PerkIcons = EmbedConfig["perk_icons"]
Defaults = EmbedConfig["defaults"]


class ActiveEmbed:
    def __init__(self, last_payload: ServerPayload, msg: discord.Message, last_update: datetime.datetime):
        self.last_payload = last_payload
        self.msg = msg
        self.last_update = last_update


class EmbedManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.active_embeds: dict[str, ActiveEmbed] = {}
        self.steam_profile_cache: dict[str, SteamProfile] = {}
        self.session_payloads: dict[str, ServerPayload] = {}

        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)

    def receive_payload(self, new_payload: ServerPayload):
        # Ignore sessions that have not begun.
        if new_payload.match_state == -1:
            return

        new_session_id = new_payload.session_id

        # If new session payload is in active embed list, update its last update time (regardless of whether we update).
        if new_session_id in self.active_embeds and new_payload.match_state == 0:
            self.active_embeds[new_session_id].last_update = datetime.datetime.now()

        # If the new session id is not in the active embeds, or we already queued an update for this session, update without checking diff.
        if (new_session_id not in self.active_embeds) or (new_session_id in self.session_payloads):
            self.session_payloads[new_session_id] = new_payload
            return

        # If info has changed since last embed update, update.
        if self.active_embeds[new_session_id].last_payload != new_payload:
            self.session_payloads[new_session_id] = new_payload

    def on_connection_closed(self, session_id: str):
        if session_id and session_id in self.active_embeds:
            if self.active_embeds[session_id].last_payload.match_state == 0:
                ending_payload = self.active_embeds[session_id].last_payload
                ending_payload.match_state = 3
                self.receive_payload(ending_payload)

    def run(self, on_ready_callback: Callable[[], Coroutine]):
        stop_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stop')

        @self.client.event
        async def on_ready():
            print(f'Logged in as {self.client.user}')
            channel = self.client.get_channel(self.config.channel_id)
            if channel is None:
                print(f"Error: Could not find channel {self.config.channel_id}.")
                return
            await self.delete_own_messages(channel)

            async def embed_update_loop():
                while True:
                    await asyncio.sleep(self.config.update_cooldown)
                    pending = dict(self.session_payloads)
                    self.session_payloads = dict()
                    if pending:
                        await self.process_session_updates(channel, pending)
                    else:
                        await self.delete_stale_embeds()

            async def stop_file_monitor():
                while True:
                    await asyncio.sleep(5)
                    if os.path.exists(stop_file_path):
                        print("Stop file detected. Shutting down gracefully...")
                        await self.client.close()
                        return

            asyncio.get_event_loop().create_task(embed_update_loop())
            asyncio.get_event_loop().create_task(stop_file_monitor())
            await on_ready_callback()

        self.client.run(self.config.discord_token)

    async def get_steam_profiles(self, players: list[PlayerEntry], retry_count: int = 1, retry_delay: int = 15) -> dict[str, SteamProfile]:
        steam_ids = [player.steam_id for player in players]
        ids_to_fetch = [player_id for player_id in steam_ids if player_id not in self.steam_profile_cache]
        if not ids_to_fetch:
            return {player_id: self.steam_profile_cache[player_id] for player_id in steam_ids}
        params = {
            "key": self.config.steam_api_key,
            "steamids": ",".join(ids_to_fetch)
        }
        async with aiohttp.ClientSession() as session:
            for attempt in range(retry_count + 1):
                try:
                    response = await session.get(self.config.steam_api_url, params=params)
                    if response.status == 200:
                        data = await response.json()
                        for player in data['response']['players']:
                            player_id = player['steamid']
                            name = player.get('personaname', 'Unknown User')
                            self.steam_profile_cache[player_id] = SteamProfile(steam_id=player_id, persona_name=name)
                        break
                    elif response.status == 429 and attempt < retry_count:
                        print(f"Rate limited. Waiting {retry_delay} seconds and retrying... (Attempt {attempt+1}/{retry_count})")
                        await asyncio.sleep(retry_delay)
                    else:
                        print(f"Failed to fetch profiles. API Response: {response.status}")
                        break
                except Exception as e:
                    print(f"Error fetching profiles: {e}")
                    break
        return {player_id: self.steam_profile_cache.get(player_id, SteamProfile(steam_id=player_id, persona_name=player_id)) for player_id in steam_ids}

    async def build_session_embed(self, info: ServerPayload, session_id: str) -> discord.Embed:
        embed = discord.Embed(
            color=0xf6731a
        )

        if info.match_state == 3:
            embed.color = 0x444444
        elif info.match_state > 0:
            embed.color = 0xef2e1c

        if self.config.add_server_url:
            embed.description=f"[Click to join!](https://{get_play_url(info)})"

        embed.set_author(
            name=info.name or session_id,
            icon_url=get_flag_icon(info)
        )

        game_type = get_game_type_name(info)
        map_name = get_map_name(info)
        state = get_match_state_name(info)
        difficulty = get_game_difficulty_name(info)

        wave = get_wave_text(info)

        if not wave or game_type == "Test Map":
            wave = ("\u200b", "\u200b")
        else:
            wave = ("Wave", wave)

        grid_fields = [
            ("Game Type", game_type),
            ("Map", map_name),
            ("State", state),
            ("Difficulty", difficulty),
            wave
        ]

        for name, value in grid_fields:
            embed.add_field(name=name, value=value, inline=True)

        if info.match_state == 0 and info.player_list:
            Col = 0
            Row = 0

            profiles = await self.get_steam_profiles(info.player_list)

            PlayerLists : list[list[PlayerEntry]] = list()
            PlayerLists.append([])
            PlayerLists.append([])
            PlayerLists.append([])
            for player in info.player_list:
                PlayerLists[Row].append(player)
                Col = Col + 1
                if (Col > 5):
                    Row = Row + 1
                    Col = 0


            player_list_str = "\u200b"
            if len(PlayerLists[0]) != 0:
                player_list_str = "".join([get_player_text(profiles[player.steam_id].persona_name, player.perk) for player in PlayerLists[0]])
            if len(PlayerLists[1]) != 0:
                player_list_str = player_list_str + "\n" + "".join([get_player_text(profiles[player.steam_id].persona_name, player.perk) for player in PlayerLists[1]])
            if len(PlayerLists[2]) != 0:
                player_list_str = player_list_str + "\n" + "".join([get_player_text(profiles[player.steam_id].persona_name, player.perk) for player in PlayerLists[2]])

            embed.add_field(
                name=f"Player List {info.player_count} / {info.player_max}",
                value=player_list_str,
                inline=True
            )

            spectator_count = info.spectator_count if info.spectator_count is not None else 0
            if spectator_count != 0:
                embed.add_field(
                    name="Spectators",
                    value=str(spectator_count),
                    inline=True
                )

        embed.set_footer(
            text=f"Last updated {datetime.datetime.now(datetime.timezone.utc).strftime('%d/%m/%Y %H:%M')}",
            icon_url="https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/TurboRelay.png"
        )

        return embed

    async def create_session_embed(self, channel, info: ServerPayload, session_id: str):
        embed = await self.build_session_embed(info, session_id)
        msg = await channel.send(embed=embed)
        self.active_embeds[session_id] = ActiveEmbed(msg=msg, last_update=datetime.datetime.now(), last_payload=info)

    async def update_session_embed(self, info: ServerPayload, session_id: str):
        embed = await self.build_session_embed(info, session_id)
        try:
            await self.active_embeds[session_id].msg.edit(embed=embed)
        except:
            print("Failed to edit message.")

        self.active_embeds[session_id].last_payload = info

    async def delete_stale_embeds(self):
        min_embed_age = datetime.datetime.now() - datetime.timedelta(minutes=15)
        to_delete = [sid for sid, v in self.active_embeds.items() if v.last_update < min_embed_age]
        for sid in to_delete:
            try:
                await self.active_embeds[sid].msg.delete()
            except:
                print("Failed to delete message.")
            del self.active_embeds[sid]

    async def process_session_updates(self, channel, session_updates: dict[str, ServerPayload]):
        for sid, info in session_updates.items():
            match_state = info.match_state
            session_id = info.session_id

            if (session_id not in self.active_embeds) and not (match_state == 3 or match_state == -1):
                print(f"Creating new embed for session {session_id}.")
                await self.create_session_embed(channel, info, session_id)
            elif (session_id in self.active_embeds):
                await self.update_session_embed(info, session_id)
        await self.delete_stale_embeds()

    async def delete_own_messages(self, channel):
        deleted = 0
        async for message in channel.history(limit=None):
            if message.author == self.client.user:
                try:
                    await message.delete()
                    deleted += 1
                except Exception as e:
                    print(f"Failed to delete message {message.id}: {e}")
        if deleted > 0:
            print(f"Deleted {deleted} previous message(s) from channel.")


def get_map_name(Payload: ServerPayload) -> str:
    if (not Payload.map_name) or Payload.map_name.lower() == "untitled":
        return Payload.map_file
    return Payload.map_name

def get_game_type_name(Payload: ServerPayload) -> str:
    if not Payload.game:
        return "Unknown"
    match Payload.game.lower():
        case "turbo":
            return "Turbo"
        case "turboplus":
            return "Turbo+"
        case "turbocardgame":
            return "Card Game"
        case "turborandomizer":
            return "Randomizer"
        case "turboholdoutgame":
            return "Holdout"
        case "turbotest":
            return "Test Map"
    return "Unknown"

def get_game_difficulty_name(Payload: ServerPayload) -> str:
    match Payload.difficulty:
        case "1":
            return "Beginner <:DifficultyBeginner:1478845463300931665>"
        case "2":
            return "Normal <:DifficultyNormal:1478845429750698144>"
        case "4":
            return "Hard <:DifficultyHard:1478845383751897320>"
        case "5":
            return "Suicidal <:DifficultySuicidal:1478845341422977159>"
        case "7":
            return "Hell on Earth <:DifficultyHellOnEarth:1478845268895076362>"
    return "Unknown"

def get_match_state_name(Payload: ServerPayload) -> str:
    match Payload.match_state:
        case -1:
            return "Waiting"
        case 0:
            if Payload.game and Payload.game.lower() == "turbotest":
                return "Active"
            return "In Progress"
        case 1:
            return "Wipe"
        case 2:
            return "Win"
        case 3:
            if Payload.game and Payload.game.lower() == "turbotest":
                return "Empty"
            return "Abort"

    return "Unknown"

def get_wave_text(Payload: ServerPayload) -> str:
    if Payload.wave_state is None:
        return ""
    wave_number = abs(Payload.wave_state)
    if wave_number == 0:
        return ""
    if Payload.final_wave is not None and Payload.final_wave > 0:
        return f"{wave_number} / {Payload.final_wave}"
    return f"{wave_number}"

def find_location_suffix(name: str) -> str | None:
    name = name.lower().rstrip()
    for loc in ServerData:
        if loc in name:
            return loc
    return None

def get_flag_icon(Payload: ServerPayload) -> str:
    if not Payload.name:
        return ""
    suffix = find_location_suffix(Payload.name)
    if suffix and suffix in ServerData:
        return ServerData[suffix]["flag_icon"]
    return Defaults["flag_icon"]

def get_play_url(Payload: ServerPayload) -> str:
    if not Payload.name:
        return ""
    suffix = find_location_suffix(Payload.name)
    if suffix and suffix in ServerData:
        return ServerData[suffix]["play_url"]
    return Defaults["play_url"]

def get_player_text(PlayerName: str, perk: str) -> str:
    return f"{get_perk_icon(perk)}"

def get_perk_icon(perk: str) -> str:
    return PerkIcons.get(perk.lower(), Defaults["perk_icon"])
