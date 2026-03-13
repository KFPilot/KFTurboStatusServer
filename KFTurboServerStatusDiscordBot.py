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
    localhost: str
    discord_token: str
    channel_id: int
    listen_port: int
    steam_api_key: str
    steam_api_url: str
    update_cooldown: float

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

@dataclass
class ActiveEmbed:
    last_payload : ServerPayload
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
    localhost=raw_config['localhost'],
    discord_token=raw_config['discord_token'],
    channel_id=int(raw_config['channel_id']),
    listen_port=int(raw_config['listen_port']),
    steam_api_key=raw_config['steam_api_key'],
    steam_api_url=raw_config['steam_api_url'],
    update_cooldown=float(raw_config.get('update_cooldown', 0.5)),
)

intents = discord.Intents.default()
client = discord.Client(intents=intents)

session_payloads: dict[str, ServerPayload] = {}
active_embeds: dict[str, ActiveEmbed] = {}

steam_profile_cache: dict[str, SteamProfile] = {}

async def get_steam_profiles(players: list[PlayerEntry], retry_count: int = 1, retry_delay: int = 15) -> dict[str, SteamProfile]:
    steam_ids = [player.steam_id for player in players]
    # Only fetch uncached IDs
    ids_to_fetch = [player_id for player_id in steam_ids if player_id not in steam_profile_cache]
    if not ids_to_fetch:
        return {player_id: steam_profile_cache[player_id] for player_id in steam_ids}
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
                        player_id = player['steamid']
                        name = player.get('personaname', 'Unknown User')
                        steam_profile_cache[player_id] = SteamProfile(steam_id=player_id, persona_name=name)
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
    return {player_id: steam_profile_cache.get(player_id, SteamProfile(steam_id=player_id, persona_name=player_id)) for player_id in steam_ids}

def parse_payload(data: dict) -> ServerPayload:
    PlayerCount = data.get('pc', '0|0|0').split('|')

    #Once game ends, just cleanup player data.
    PlayerList = []
    if data.get('ms') > 0:
        PlayerCount[0] = 0
        PlayerCount[2] = 0
        PlayerList = []
        data['sl'] = []
    else:
        PlayerDataList = data.get('pl', [])
        for Player in PlayerDataList:
            PlayerData = Player.split('|')
            PlayerList.append(PlayerEntry(steam_id=PlayerData[0], perk=PlayerData[1]))

    return ServerPayload(
        name=data.get('serv'),
        game=data.get('game'),
        difficulty=data.get('diff'),
        map_file=data.get('mapf'),
        map_name=data.get('mapn'),
        final_wave=data.get('fw'),
        match_state=data.get('ms'),
        wave_state=data.get('ws'),
        player_count=int(PlayerCount[0]),
        player_max=int(PlayerCount[1]),
        spectator_count=int(PlayerCount[2]),
        player_list=PlayerList,
        spectator_list=data.get('sl', []),
        session_id=data.get('sid'),
    )

def info_changed(old: ServerPayload, new: ServerPayload) -> bool:
    return old != new

def get_map_name(Payload:ServerPayload)-> str:
    if (not Payload.map_name) or Payload.map_name.lower() == "untitled":
        return Payload.map_file
    return Payload.map_name

def get_game_type_name(Payload:ServerPayload)-> str:
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

def get_game_difficulty_name(Payload:ServerPayload)-> str:
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

def get_match_state_name(Payload:ServerPayload)-> str:
    match Payload.match_state:
        case -1:
            return "Waiting"
        case 0:
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

def get_wave_text(Payload:ServerPayload)-> str:
    if Payload.wave_state is None:
        return ""
    wave_number = abs(Payload.wave_state)
    if wave_number == 0:
        return ""
    if Payload.final_wave is not None and Payload.final_wave > 0:
        return f"{wave_number} / {Payload.final_wave}"
    return f"{wave_number}"

def get_flag_icon(Payload:ServerPayload) -> str:
    if not Payload.name:
        return ""
    name = Payload.name.lower().rstrip()
    # Extract the last word(s) for matching
    suffix = None
    for loc in ["new york", "los angeles", "frankfurt", "sao paulo", "london", "singapore", "tokyo", "warsaw"]:
        if name.endswith(loc):
            suffix = loc
            break
    match suffix:
        case "new york" | "los angeles":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-united-states.png"
        case "frankfurt":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-germany.png"
        case "sao paulo":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-brazil.png"
        case "london":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-united-kingdom.png"
        case "singapore":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-singapore.png"
        case "tokyo":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-japan.png"
        case "warsaw":
            return "https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/flag-poland.png"
        case _:
            return "https://cdn.discordapp.com/embed/avatars/0.png"
        
        
def get_player_text(PlayerName:str, perk:str)-> str:
    return f"{get_perk_icon(perk)}"

def get_perk_icon(perk:str)-> str:
    match (perk.lower()):
        case "med":
            return "<:PerkMedic:1478637214148595894>"
        case "sup":
            return "<:PerkSupport:1478637310068260988>"
        case "sha":
            return "<:PerkSharpshooter:1478637191046496438>"
        case "com":
            return "<:PerkCommando:1478637293240848456>"
        case "ber":
            return "<:PerkBerserker:1478637275066798201>"
        case "fir":
            return "<:PerkFirebug:1478637233287331951>"
        case "dem":
            return "<:PerkDemolitions:1478637253571121173>"
    return "<:PerkSharpshooter:1478637191046496438>"
            

async def build_session_embed(info: ServerPayload, session_id: str) -> discord.Embed:
    now = datetime.datetime.now()

    embed = discord.Embed(
        title="Killing Floor Turbo Session",
        color=0xf6731a
    )
    if info.match_state > 0:
        embed.color = 0xef2e1c

    embed.set_author(
        name=info.name or session_id,
        icon_url=get_flag_icon(info)
    )

    game_type = get_game_type_name(info)
    map_name = get_map_name(info)
    state = get_match_state_name(info)
    difficulty = get_game_difficulty_name(info)

    wave = get_wave_text(info)

    #Optional fields should evaluate their entry fully.
    if not wave or game_type == "Test Map":
        wave = ("\u200b", "\u200b")
    else:
        wave = ("Wave", wave)

    # Grid: left to right, top to bottom
    # Discord automatically wraps after 3 fields if inline, so we can just add them in order
    grid_fields = [
        ("Game Type", game_type),
        ("Map", map_name),
        ("State", state),
        ("Difficulty", difficulty),
        wave
    ]

    for name, value in grid_fields:
        embed.add_field(name=name, value=value, inline=True)

    # Player list
    if info.match_state == 0 and info.player_list:
        Col = 0
        Row = 0

        profiles = await get_steam_profiles(info.player_list)

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
        text=f"Last updated {now.strftime('%d/%m/%Y %H:%M')}",
        icon_url="https://raw.githubusercontent.com/KFPilot/KFTurboStatusServer/refs/heads/main/img/TurboRelay.png"
    )
    
    return embed

async def create_session_embed(channel, info: ServerPayload, session_id: str):
    global active_embeds
    embed = await build_session_embed(info, session_id)
    msg = await channel.send(embed=embed)
    active_embeds[session_id] = ActiveEmbed(msg=msg, last_update=datetime.datetime.now(), last_payload=info)

async def update_session_embed(info: ServerPayload, session_id: str):
    global active_embeds
    embed = await build_session_embed(info, session_id)
    try:
        await active_embeds[session_id].msg.edit(embed=embed)
    except:
        print("Failed to edit message.")

    active_embeds[session_id].last_payload = info

async def delete_stale_embeds():
    global active_embeds
    min_embed_age = datetime.datetime.now() - datetime.timedelta(minutes=15)
    to_delete = [sid for sid, v in active_embeds.items() if v.last_update < min_embed_age]
    for sid in to_delete:
        try:
            await active_embeds[sid].msg.delete()
        except:
            print("Failed to delete message.")
        del active_embeds[sid]

async def update_active_embeds(channel):
    global session_payloads
    new_session_payloads = dict(session_payloads)
    session_payloads = dict()
    session_keys = list(new_session_payloads.keys())
    for sid in session_keys:
        info = new_session_payloads[sid]

        match_state = info.match_state
        session_id = info.session_id

        if (session_id not in active_embeds) and not (match_state == 3 or match_state == -1):
            print(f"Creating new embed for session {session_id}.")
            await create_session_embed(channel, info, session_id)
        elif (session_id in active_embeds):
            await update_session_embed(info, session_id)
    await delete_stale_embeds()

async def embed_update_loop(channel):
    while True:
        await asyncio.sleep(bot_config.update_cooldown)
        await update_active_embeds(channel)


async def tcp_listener():
    loop = asyncio.get_event_loop()
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((bot_config.localhost, bot_config.listen_port))
        server.listen(10)
        server.setblocking(False)
        print(f"Listening for TurboInfo packets on {bot_config.localhost}:{bot_config.listen_port}...")
    except Exception as e:
        print(f"Error starting TCP listener: {e}")
        return
    while True:
        try:
            conn, addr = await loop.sock_accept(server)
            print(f"Accepted connection from {addr}")
            loop.create_task(handle_client(conn))
        except Exception as e:
            print(f"Error accepting connection: {e}")
            await asyncio.sleep(2)  # Prevent tight loop on repeated errors

def receive_payload(new_payload: ServerPayload):
    global session_payloads

    # Ignore sessions that have not begun.
    if new_payload.match_state == -1:
        return

    new_session_id = new_payload.session_id

    # If new session payload is in active embed list, update its last update time (regardless of whether we update).
    if new_session_id in active_embeds and new_payload.match_state == 0:
        active_embeds[new_session_id].last_update = datetime.datetime.now()

    # If the new session id is not in the active embeds, or we already queued an update for this session, update without checking diff.
    if (not (new_session_id in active_embeds)) or (new_session_id in session_payloads):
        session_payloads[new_session_id] = new_payload
        return

    # If info has changed since last embed update, update.
    if info_changed(active_embeds[new_session_id].last_payload, new_payload):
        session_payloads[new_session_id] = new_payload

async def handle_client(conn: socket.socket):
    buffer = ""
    loop = asyncio.get_event_loop()
    last_known_session_id = ""
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

                if (line == "keepalive"):
                    continue
                
                try:
                    payload = json.loads(line)
                    sid = payload.get('sid')
                    if not sid:
                        continue

                    if last_known_session_id != sid:
                        print(f"New session ID {sid}")
                        last_known_session_id = sid

                    new_info = parse_payload(payload)
                    receive_payload(new_info)
                            
                except Exception as e:
                    print(f"Error parsing packet: {line} - {e}")
        except Exception as e:
            print(f"Error receiving data: {e}")
            break
    print(f"Closing connection.")

    if last_known_session_id and last_known_session_id in active_embeds:
        if active_embeds[last_known_session_id].last_payload.match_state == 0:
            ending_payload = active_embeds[last_known_session_id].last_payload
            ending_payload.match_state = 3
            receive_payload(ending_payload)


    conn.close()

async def delete_own_messages(channel):
    deleted = 0
    async for message in channel.history(limit=None):
        if message.author == client.user:
            try:
                await message.delete()
                deleted += 1
            except Exception as e:
                print(f"Failed to delete message {message.id}: {e}")
    if deleted > 0:
        print(f"Deleted {deleted} previous message(s) from channel.")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    channel = client.get_channel(bot_config.channel_id)
    if channel is None:
        print(f"Error: Could not find channel {bot_config.channel_id}.")
        return
    await delete_own_messages(channel)
    asyncio.get_event_loop().create_task(embed_update_loop(channel))
    await tcp_listener()

client.run(bot_config.discord_token)
