# Killing Floor Turbo Server Status Discord Bot
# Accepts connections on a defined port and creates/updates/deletes embeds in a specified Discord channel based on received payloads.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import discord
import asyncio
import json
import datetime
import socket
import sys
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BotConfig:
    discord_token: str
    channel_id: int
    listen_port: int
    steam_api_key: str
    steam_api_url: str

@dataclass
class SteamProfile:
    steam_id: str
    persona_name: str

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
    player_count: Optional[str]
    player_list: list[str] = field(default_factory=list)
    spectator_list: list[str] = field(default_factory=list)
    session_id: Optional[str] = None

@dataclass
class ActiveEmbed:
    msg: discord.Message
    last_update: datetime.datetime

# Load configuration from config.json
try:
    with open('serverstatusconfig.json') as f:
        raw_config = json.load(f)
except Exception as e:
    print(f"Error loading config file: {e}")
    sys.exit(1)

bot_config = BotConfig(
    discord_token=raw_config['discord_token'],
    channel_id=int(raw_config['channel_id']),
    listen_port=int(raw_config['listen_port']),
    steam_api_key=raw_config['steam_api_key'],
    steam_api_url=raw_config['steam_api_url'],
)

intents = discord.Intents.default()
client = discord.Client(intents=intents)

session_payloads: dict[str, ServerPayload] = {}
active_embeds: dict[str, ActiveEmbed] = {}

steam_profile_cache: dict[str, SteamProfile] = {}

async def get_steam_profiles(steam_ids: list[str], retry_count: int = 1, retry_delay: int = 15) -> dict[str, SteamProfile]:
    # Only fetch uncached IDs
    ids_to_fetch = [sid for sid in steam_ids if sid not in steam_profile_cache]
    if not ids_to_fetch:
        return {sid: steam_profile_cache[sid] for sid in steam_ids}
    params = {
        "key": bot_config.steam_api_key,
        "steamids": ",".join(ids_to_fetch)
    }
    async with aiohttp.ClientSession() as session:
        for attempt in range(retry_count + 1):
            try:
                response = await session.get(bot_config.steam_api_url, params=params)
                if response.status == 200:
                    data = await response.json()
                    for player in data['response']['players']:
                        sid = player['steamid']
                        name = player.get('personaname', 'Unknown User')
                        steam_profile_cache[sid] = SteamProfile(steam_id=sid, persona_name=name)
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
    # Return profiles for all requested IDs (from cache, fallback to unknown)
    return {sid: steam_profile_cache.get(sid, SteamProfile(steam_id=sid, persona_name=sid)) for sid in steam_ids}

def parse_payload(data: dict) -> ServerPayload:
    return ServerPayload(
        name=data.get('serv'),
        game=data.get('game'),
        difficulty=data.get('diff'),
        map_file=data.get('mapf'),
        map_name=data.get('mapn'),
        final_wave=data.get('fw'),
        match_state=data.get('ms'),
        wave_state=data.get('ws'),
        player_count=data.get('pc'),
        player_list=data.get('pl', []),
        spectator_list=data.get('sl', []),
        session_id=data.get('sid'),
    )

def info_changed(old: ServerPayload, new: ServerPayload) -> bool:
    return old != new

async def update_active_embeds(channel):
        global active_embeds
        now = datetime.datetime.now()
        # Create/update embeds for sessions
        for sid, info in session_payloads.items():
            session_id = info.session_id
            match_state = info.match_state if info.match_state is not None else -1
            if not session_id:
                continue
            # Creation: match_state != -1 and not already displayed
            if match_state != -1 and session_id not in active_embeds:
                embed = discord.Embed(
                    title=info.name or session_id,
                    color=0x7891ff
                )
                embed.set_author(
                    name="Killing Floor Turbo Session",
                    icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
                )
                game_type = info.game or "Unknown"
                difficulty = info.difficulty or "Unknown"
                map_name = info.map_name or info.map_file or "Unknown"
                embed.add_field(
                    name="Game",
                    value=f"{game_type}\n{difficulty}\n{map_name}",
                    inline=False
                )
                # Batch query SteamIDs for display names
                if info.player_list:
                    profiles = await get_steam_profiles(info.player_list)
                    player_list_str = "\n".join([profiles[sid].persona_name for sid in info.player_list])
                else:
                    player_list_str = "None"
                embed.add_field(
                    name="Player List",
                    value=player_list_str,
                    inline=False
                )
                embed.set_footer(
                    text=f"Last updated {now.strftime('%d/%m/%Y %H:%M')}",
                    icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
                )
                msg = await channel.send(embed=embed)
                active_embeds[session_id] = ActiveEmbed(msg=msg, last_update=now)
            # Update: sid/session_id is in active_embeds
            elif session_id in active_embeds:
                embed = discord.Embed(
                    title=info.name or session_id,
                    color=0x7891ff
                )
                embed.set_author(
                    name="Killing Floor Turbo Session",
                    icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
                )
                game_type = info.game or "Unknown"
                difficulty = info.difficulty or "Unknown"
                map_name = info.map_name or info.map_file or "Unknown"
                embed.add_field(
                    name="Game",
                    value=f"{game_type}\n{difficulty}\n{map_name}",
                    inline=False
                )
                # Batch query SteamIDs for display names
                if info.player_list:
                    profiles = await get_steam_profiles(info.player_list)
                    player_list_str = "\n".join([profiles[sid].persona_name for sid in info.player_list])
                else:
                    player_list_str = "None"
                embed.add_field(
                    name="Player List",
                    value=player_list_str,
                    inline=False
                )
                embed.set_footer(
                    text=f"Last updated {now.strftime('%d/%m/%Y %H:%M')}",
                    icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
                )
                await active_embeds[session_id].msg.edit(embed=embed)
                active_embeds[session_id].last_update = now
        # Deletion: remove embeds older than 4 hours
        four_hours_ago = now - datetime.timedelta(hours=4)
        to_delete = [sid for sid, v in active_embeds.items() if v.last_update < four_hours_ago]
        for sid in to_delete:
            await active_embeds[sid].msg.delete()
            del active_embeds[sid]

async def tcp_listener(channel):
    loop = asyncio.get_event_loop()
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", bot_config.listen_port))
        server.listen(10)
        server.setblocking(False)
        print(f"Listening for TurboInfo packets on 127.0.0.1:{bot_config.listen_port}...")
    except Exception as e:
        print(f"Error starting TCP listener: {e}")
        return
    while True:
        try:
            conn, addr = await loop.sock_accept(server)
            print(f"Accepted connection from {addr}")
            loop.create_task(handle_client(conn, channel))
        except Exception as e:
            print(f"Error accepting connection: {e}")
            await asyncio.sleep(2)  # Prevent tight loop on repeated errors

async def handle_client(conn: socket.socket, channel):
    buffer = ""
    loop = asyncio.get_event_loop()
    while True:
        try:
            data = await loop.sock_recv(conn, 8192)
            if not data:
                break
            buffer += data.decode('utf-8')
            lines = buffer.split("\r\n")
            buffer = lines.pop()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    sid = payload.get('sid')
                    if not sid:
                        continue
                    new_info = parse_payload(payload)
                    old_info = session_payloads.get(sid)
                    if not old_info or info_changed(old_info, new_info):
                        session_payloads[sid] = new_info
                        await update_active_embeds(channel)
                except Exception as e:
                    print(f"Error parsing packet: {line} - {e}")
        except Exception as e:
            print(f"Error receiving data: {e}")
            break
    conn.close()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    channel = client.get_channel(bot_config.channel_id)
    await tcp_listener(channel)

client.run(bot_config.discord_token)
