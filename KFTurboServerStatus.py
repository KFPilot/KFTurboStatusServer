# Killing Floor Turbo Server Status Discord Bot
# Accepts connections on a defined port and notifies the embed manager with received payloads.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import asyncio
import json
import socket
import sys
import dataclasses

from KFTurboServerStatusTypes import BotConfig, PlayerEntry, ServerPayload

# Load configuration from config.json
try:
    with open('serverstatusconfig.json') as f:
        raw_config = json.load(f)
except Exception as e:
    print(f"Error loading config file: {e}")
    sys.exit(1)

discord_token = raw_config.get('discord_token', '').strip() or None
channel_id_raw = raw_config.get('channel_id', '').strip() if raw_config.get('channel_id') else None

bot_config = BotConfig(
    localhost=raw_config['localhost'],
    discord_token=discord_token,
    channel_id=int(channel_id_raw) if channel_id_raw else None,
    listen_port=int(raw_config['listen_port']),
    steam_api_key=raw_config.get('steam_api_key', ''),
    steam_api_url=raw_config.get('steam_api_url', ''),
    update_cooldown=float(raw_config.get('update_cooldown', 0.5)),
    add_server_url=bool(raw_config.get('add_server_url', False))
)

embed_manager = None
if bot_config.discord_token:
    from KFTurboDiscordEmbed import EmbedManager
    embed_manager = EmbedManager(bot_config)

session_data: dict[str, ServerPayload] = {}

http_port = int(raw_config.get('http_port', 0))
http_host = raw_config.get('http_host', '0.0.0.0')

web_server = None
if http_port:
    from KFTurboWebServer import SessionDataServer
    web_server = SessionDataServer(http_host, http_port)
    web_server.start()

def update_session_data():
    if not web_server:
        return
    serialized = {}
    for sid, payload in session_data.items():
        serialized[sid] = dataclasses.asdict(payload)
    web_server.update(json.dumps(serialized))

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
                    session_data[sid] = new_info
                    update_session_data()
                    if embed_manager:
                        embed_manager.receive_payload(new_info)

                except Exception as e:
                    print(f"Error parsing packet: {line} - {e}")
        except Exception as e:
            print(f"Error receiving data: {e}")
            break
    print(f"Closing connection.")

    if embed_manager:
        embed_manager.on_connection_closed(last_known_session_id)

    conn.close()

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

if embed_manager:
    print("Attempting to start up Discord embed manager.")
    embed_manager.run(tcp_listener)


