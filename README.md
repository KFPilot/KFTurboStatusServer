# KFTurboStatusServer

Service that provides status information about currently active turbo servers via Discord embeds and an optional HTTP JSON output.

## Required config files

This app requires all three config files to be present in the repo root:

- `serverstatusconfig.json`
- `serverembedconfig.json`
- `serverportalconfig.json`

If any are missing or invalid, startup will fail.

### `serverstatusconfig.json`

```json
{
  "localhost": "0.0.0.0",
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "channel_id": "DISCORD_CHANNEL_ID",
  "listen_port": "TCP_LISTEN_PORT",
  "steam_api_key": "YOUR_STEAM_API_KEY",
  "steam_api_url": "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
  "update_cooldown": 0.5,
  "add_server_url": true,
  "http_host": "0.0.0.0",
  "http_port": "OPTIONAL_HTTP_PORT_OR_0"
}
```

### `serverembedconfig.json`

```json
{
  "servers": {
    "location one": {
      "flag_icon": "https://example.com/flags/location-one.png",
      "play_url": "play.server-one.example.com"
    },
    "location two": {
      "flag_icon": "https://example.com/flags/location-two.png",
      "play_url": "play.server-two.example.com"
    }
  },
  "perk_icons": {
    "med": "<:PerkMedic:<emoji_id_on_discord_server>>",
    "sup": "<:PerkSupport:<emoji_id_on_discord_server>>",
    "sha": "<:PerkSharpshooter:<emoji_id_on_discord_server>>",
    "com": "<:PerkCommando:<emoji_id_on_discord_server>>",
    "ber": "<:PerkBerserker:<emoji_id_on_discord_server>>",
    "fir": "<:PerkFirebug:<emoji_id_on_discord_server>>",
    "dem": "<:PerkDemolitions:<emoji_id_on_discord_server>>"
  },
  "defaults": {
    "flag_icon": "https://example.com/flags/default.png",
    "play_url": "play.default.example.com",
    "perk_icon": "<:PerkSharpshooter:<emoji_id_on_discord_server>>"
  }
}
```

### `serverportalconfig.json`

```json
{
  "server mapping": {
    "location suffix in server name": "output_key_for_http_json",
    "another suffix": "another_output_key"
  }
}
```

This file is used by the optional HTTP JSON output (`http_port` in `serverstatusconfig.json`) and can be used for server status pages or other integrations.

Example HTTP JSON output:

```json
{
  "server1": {
    "server": "KFTurbo Server #1",
    "current_players": 4,
    "max_players": 6,
    "current_map": "KF-BioticsLab"
  },
  "server2": {
    "server": "KFTurbo Server #2",
    "current_players": 0,
    "max_players": 6,
    "current_map": "KF-Offices"
  }
}
```

## Docker note

If running in Docker, keep `"localhost": "0.0.0.0"` in `serverstatusconfig.json`.
Only expose/map the HTTP port when `http_port` is enabled and you actually need the HTTP endpoint.
