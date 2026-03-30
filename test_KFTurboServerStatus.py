# Killing Floor Turbo Server Status Discord Bot Tests
# Test cases written by chat gipity.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import unittest
import asyncio
import datetime
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Mock external dependencies before importing the bot module.
# discord and aiohttp may not be installed in the test environment.
mock_discord = MagicMock()
mock_discord.Intents.default.return_value = MagicMock()
mock_discord.Client.return_value = MagicMock()
mock_discord.Embed = MagicMock()
mock_discord.Message = MagicMock

mock_aiohttp = MagicMock()

sys.modules['discord'] = mock_discord
sys.modules['aiohttp'] = mock_aiohttp

_fake_config = {
    "discord_token": "fake-token",
    "channel_id": "123456789",
    "listen_port": "9999",
    "steam_api_key": "fake-key",
    "steam_api_url": "https://fake.steam.api/ISteamUser/GetPlayerSummaries/v0002/",
    "localhost": "0.0.0.0",
}

with patch("builtins.open", mock_open(read_data=json.dumps(_fake_config))):
    import KFTurboServerStatus as bot

import KFTurboDiscordEmbed as embed_mgr
from KFTurboServerStatusTypes import BotConfig, SteamProfile, PlayerEntry, ServerPayload


def _make_payload(**overrides):
    base = dict(
        name="S", game="G", difficulty="D", map_file="M",
        map_name="N", final_wave=7, match_state=0,
        wave_state=1, player_count=1, player_max=6,
        spectator_count=0,
        player_list=[], spectator_list=[], session_id="sess1",
    )
    base.update(overrides)
    return ServerPayload(**base)


def _make_active_embed(last_update=None, **payload_overrides):
    mock_msg = MagicMock()
    mock_msg.edit = AsyncMock()
    mock_msg.delete = AsyncMock()
    if last_update is None:
        last_update = datetime.datetime.now()
    return embed_mgr.ActiveEmbed(
        last_payload=_make_payload(**payload_overrides),
        msg=mock_msg, last_update=last_update,
    )


class TestBotConfig(unittest.TestCase):
    def test_config_fields(self):
        self.assertEqual(bot.bot_config.discord_token, "fake-token")
        self.assertEqual(bot.bot_config.channel_id, 123456789)
        self.assertEqual(bot.bot_config.listen_port, 9999)
        self.assertEqual(bot.bot_config.steam_api_key, "fake-key")
        self.assertIn("ISteamUser", bot.bot_config.steam_api_url)

    def test_config_types(self):
        self.assertIsInstance(bot.bot_config, BotConfig)
        self.assertIsInstance(bot.bot_config.channel_id, int)
        self.assertIsInstance(bot.bot_config.listen_port, int)

    def test_update_cooldown_defaults(self):
        self.assertEqual(bot.bot_config.update_cooldown, 0.5)
        self.assertIsInstance(bot.bot_config.update_cooldown, float)


class TestSteamProfile(unittest.TestCase):
    def test_fields(self):
        profile = SteamProfile(steam_id="12345", persona_name="Player1")
        self.assertEqual(profile.steam_id, "12345")
        self.assertEqual(profile.persona_name, "Player1")

    def test_equality(self):
        a = SteamProfile(steam_id="1", persona_name="A")
        b = SteamProfile(steam_id="1", persona_name="A")
        c = SteamProfile(steam_id="1", persona_name="B")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestPlayerEntry(unittest.TestCase):
    def test_fields(self):
        entry = PlayerEntry(steam_id="12345", perk="med")
        self.assertEqual(entry.steam_id, "12345")
        self.assertEqual(entry.perk, "med")

    def test_equality(self):
        a = PlayerEntry(steam_id="1", perk="med")
        b = PlayerEntry(steam_id="1", perk="med")
        c = PlayerEntry(steam_id="1", perk="sup")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestServerPayload(unittest.TestCase):
    def test_defaults(self):
        payload = ServerPayload(
            name=None, game=None, difficulty=None, map_file=None,
            map_name=None, final_wave=None, match_state=None,
            wave_state=None, player_count=None, player_max=None,
            spectator_count=None,
        )
        self.assertEqual(payload.player_list, [])
        self.assertEqual(payload.spectator_list, [])
        self.assertIsNone(payload.session_id)

    def test_default_factory_independence(self):
        """Each instance should get its own list, not a shared reference."""
        a = _make_payload()
        b = _make_payload()
        a.player_list.append(PlayerEntry(steam_id="test", perk="med"))
        self.assertEqual(b.player_list, [])

    def test_equality(self):
        kwargs = dict(
            name="Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=3, player_count=2,
            player_max=6, spectator_count=0,
            player_list=[PlayerEntry(steam_id="id1", perk="med")],
            spectator_list=[], session_id="abc",
        )
        self.assertEqual(ServerPayload(**kwargs), ServerPayload(**kwargs))

        changed = dict(kwargs, wave_state=4)
        self.assertNotEqual(ServerPayload(**kwargs), ServerPayload(**changed))


class TestParsePayload(unittest.TestCase):
    def _make_raw(self, **overrides):
        base = {
            "serv": "Test Server", "game": "KFTurbo", "diff": "Hard",
            "mapf": "KF-Farm", "mapn": "Farm", "fw": 10,
            "ms": 0, "ws": 3, "pc": "2|6|0",
            "pl": ["id1|med", "id2|sup"], "sl": ["id3"], "sid": "session1",
        }
        base.update(overrides)
        return base

    def test_full_payload(self):
        raw = self._make_raw()
        result = bot.parse_payload(raw)
        self.assertIsInstance(result, ServerPayload)
        self.assertEqual(result.name, "Test Server")
        self.assertEqual(result.game, "KFTurbo")
        self.assertEqual(result.difficulty, "Hard")
        self.assertEqual(result.map_file, "KF-Farm")
        self.assertEqual(result.map_name, "Farm")
        self.assertEqual(result.final_wave, 10)
        self.assertEqual(result.match_state, 0)
        self.assertEqual(result.wave_state, 3)
        self.assertEqual(result.player_count, 2)
        self.assertEqual(result.player_max, 6)
        self.assertEqual(result.spectator_count, 0)
        self.assertEqual(result.player_list, [
            PlayerEntry(steam_id="id1", perk="med"),
            PlayerEntry(steam_id="id2", perk="sup"),
        ])
        self.assertEqual(result.spectator_list, ["id3"])
        self.assertEqual(result.session_id, "session1")

    def test_missing_optional_fields(self):
        result = bot.parse_payload({"sid": "s1", "pc": "0|0|0", "ms": 0})
        self.assertIsInstance(result, ServerPayload)
        self.assertIsNone(result.name)
        self.assertIsNone(result.game)
        self.assertIsNone(result.map_name)
        self.assertEqual(result.player_list, [])
        self.assertEqual(result.spectator_list, [])
        self.assertEqual(result.session_id, "s1")

    def test_empty_payload(self):
        result = bot.parse_payload({"pc": "0|0|0", "ms": 0})
        self.assertIsNone(result.session_id)

    def test_key_mapping(self):
        """Verify each JSON key maps to the correct ServerPayload field."""
        raw = self._make_raw()
        result = bot.parse_payload(raw)
        self.assertEqual(result.name, raw["serv"])
        self.assertEqual(result.difficulty, raw["diff"])
        self.assertEqual(result.map_file, raw["mapf"])
        self.assertEqual(result.map_name, raw["mapn"])
        self.assertEqual(result.final_wave, raw["fw"])
        self.assertEqual(result.match_state, raw["ms"])
        self.assertEqual(result.wave_state, raw["ws"])
        self.assertEqual(result.player_count, 2)
        self.assertEqual(result.player_max, 6)
        self.assertEqual(result.spectator_count, 0)
        self.assertEqual(len(result.player_list), 2)
        self.assertIsInstance(result.player_list[0], PlayerEntry)
        self.assertEqual(result.spectator_list, raw["sl"])
        self.assertEqual(result.session_id, raw["sid"])

    def test_game_over_clears_player_data(self):
        """When match_state > 0, player data should be cleared."""
        raw = self._make_raw(ms=1)
        result = bot.parse_payload(raw)
        self.assertEqual(result.player_count, 0)
        self.assertEqual(result.spectator_count, 0)
        self.assertEqual(result.player_list, [])
        self.assertEqual(result.spectator_list, [])


class TestReceivePayload(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.session_payloads.clear()
        bot.embed_manager.active_embeds.clear()

    def test_ignores_pre_match_state(self):
        bot.embed_manager.receive_payload(_make_payload(match_state=-1))
        self.assertEqual(bot.embed_manager.session_payloads, {})

    def test_queues_new_session(self):
        bot.embed_manager.receive_payload(_make_payload(session_id="new1"))
        self.assertIn("new1", bot.embed_manager.session_payloads)

    def test_updates_last_update_time_for_active_session(self):
        old_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed(last_update=old_time)
        bot.embed_manager.receive_payload(_make_payload(wave_state=2))
        self.assertGreater(bot.embed_manager.active_embeds["sess1"].last_update, old_time)

    def test_skips_unchanged_payload(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed()
        # Same payload as what's already in the active embed
        bot.embed_manager.receive_payload(_make_payload())
        self.assertNotIn("sess1", bot.embed_manager.session_payloads)

    def test_queues_changed_payload(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed()
        bot.embed_manager.receive_payload(_make_payload(wave_state=99))
        self.assertIn("sess1", bot.embed_manager.session_payloads)

    def test_always_queues_if_already_pending(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed()
        bot.embed_manager.session_payloads["sess1"] = _make_payload()
        # Even identical payload gets queued when one is already pending
        bot.embed_manager.receive_payload(_make_payload())
        self.assertIn("sess1", bot.embed_manager.session_payloads)


class TestOnConnectionClosed(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.session_payloads.clear()
        bot.embed_manager.active_embeds.clear()

    def test_sets_match_state_to_abort_on_active_session(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed(match_state=0)
        bot.embed_manager.on_connection_closed("sess1")
        self.assertIn("sess1", bot.embed_manager.session_payloads)
        self.assertEqual(bot.embed_manager.session_payloads["sess1"].match_state, 3)

    def test_ignores_empty_session_id(self):
        bot.embed_manager.on_connection_closed("")
        self.assertEqual(bot.embed_manager.session_payloads, {})

    def test_ignores_unknown_session_id(self):
        bot.embed_manager.on_connection_closed("unknown")
        self.assertEqual(bot.embed_manager.session_payloads, {})

    def test_ignores_already_ended_session(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed(match_state=1)
        bot.embed_manager.on_connection_closed("sess1")
        self.assertEqual(bot.embed_manager.session_payloads, {})


class TestGetSteamProfiles(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.steam_profile_cache.clear()

    def _players(self, *steam_ids):
        return [PlayerEntry(steam_id=sid, perk="med") for sid in steam_ids]

    def test_returns_cached_profiles(self):
        bot.embed_manager.steam_profile_cache["111"] = SteamProfile(steam_id="111", persona_name="CachedPlayer")
        result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.get_steam_profiles(self._players("111")))
        self.assertIsInstance(result["111"], SteamProfile)
        self.assertEqual(result["111"].persona_name, "CachedPlayer")

    def test_returns_multiple_cached_profiles(self):
        bot.embed_manager.steam_profile_cache["111"] = SteamProfile(steam_id="111", persona_name="Player1")
        bot.embed_manager.steam_profile_cache["222"] = SteamProfile(steam_id="222", persona_name="Player2")
        result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.get_steam_profiles(self._players("111", "222")))
        self.assertEqual(len(result), 2)
        self.assertEqual(result["111"].persona_name, "Player1")
        self.assertEqual(result["222"].persona_name, "Player2")

    def test_fallback_on_api_failure(self):
        """When API fails, uncached IDs should fall back to steam_id as persona_name."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_response)

        with patch("KFTurboDiscordEmbed.aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.get_steam_profiles(self._players("999")))
            self.assertIsInstance(result["999"], SteamProfile)
            self.assertEqual(result["999"].steam_id, "999")
            self.assertEqual(result["999"].persona_name, "999")

    def test_successful_api_response(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "response": {
                "players": [
                    {"steamid": "222", "personaname": "FetchedPlayer"}
                ]
            }
        })

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_response)

        with patch("KFTurboDiscordEmbed.aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.get_steam_profiles(self._players("222")))

        self.assertIsInstance(result["222"], SteamProfile)
        self.assertEqual(result["222"].persona_name, "FetchedPlayer")
        self.assertIn("222", bot.embed_manager.steam_profile_cache)
        self.assertEqual(bot.embed_manager.steam_profile_cache["222"].persona_name, "FetchedPlayer")

    def test_only_fetches_uncached_ids(self):
        """Should not make an API call when all IDs are cached."""
        bot.embed_manager.steam_profile_cache["111"] = SteamProfile(steam_id="111", persona_name="Cached")

        with patch("KFTurboDiscordEmbed.aiohttp.ClientSession") as mock_cls:
            result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.get_steam_profiles(self._players("111")))
            mock_cls.assert_not_called()

        self.assertEqual(result["111"].persona_name, "Cached")


class TestActiveEmbed(unittest.TestCase):
    def test_fields(self):
        mock_msg = MagicMock()
        now = datetime.datetime.now()
        payload = _make_payload()
        embed = embed_mgr.ActiveEmbed(last_payload=payload, msg=mock_msg, last_update=now)
        self.assertEqual(embed.msg, mock_msg)
        self.assertEqual(embed.last_update, now)
        self.assertEqual(embed.last_payload, payload)

    def test_mutability(self):
        mock_msg = MagicMock()
        now = datetime.datetime.now()
        embed = embed_mgr.ActiveEmbed(last_payload=_make_payload(), msg=mock_msg, last_update=now)
        new_time = now + datetime.timedelta(hours=1)
        embed.last_update = new_time
        self.assertEqual(embed.last_update, new_time)


class TestGetPlayerText(unittest.TestCase):
    def test_formats_player_text(self):
        result = embed_mgr.get_player_text("TestPlayer", "med")
        self.assertIn("TestPlayer", result)
        self.assertIn("PerkMedic", result)


class TestGetPerkIcon(unittest.TestCase):
    def test_known_perks(self):
        self.assertIn("PerkMedic", embed_mgr.get_perk_icon("med"))
        self.assertIn("PerkSupport", embed_mgr.get_perk_icon("sup"))
        self.assertIn("PerkSharpshooter", embed_mgr.get_perk_icon("sha"))
        self.assertIn("PerkCommando", embed_mgr.get_perk_icon("com"))
        self.assertIn("PerkBerserker", embed_mgr.get_perk_icon("ber"))
        self.assertIn("PerkFirebug", embed_mgr.get_perk_icon("fir"))
        self.assertIn("PerkDemolitions", embed_mgr.get_perk_icon("dem"))

    def test_unknown_perk_defaults_to_sharpshooter(self):
        self.assertIn("PerkSharpshooter", embed_mgr.get_perk_icon("unknown"))

    def test_case_insensitive(self):
        self.assertIn("PerkMedic", embed_mgr.get_perk_icon("MED"))
        self.assertIn("PerkMedic", embed_mgr.get_perk_icon("Med"))


class TestBuildSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.steam_profile_cache.clear()

    def test_returns_embed(self):
        info = _make_payload()
        result = asyncio.get_event_loop().run_until_complete(bot.embed_manager.build_session_embed(info, "sess1"))
        self.assertIsNotNone(result)

    def test_uses_name_as_author(self):
        info = _make_payload(name="My Server")
        mock_discord.Embed.reset_mock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.build_session_embed(info, "sess1"))
        embed_instance = mock_discord.Embed.return_value
        embed_instance.set_author.assert_called_once()
        call_kwargs = embed_instance.set_author.call_args[1]
        self.assertEqual(call_kwargs['name'], "My Server")

    def test_falls_back_to_session_id_when_no_name(self):
        info = _make_payload(name=None)
        mock_discord.Embed.reset_mock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.build_session_embed(info, "sess1"))
        embed_instance = mock_discord.Embed.return_value
        call_kwargs = embed_instance.set_author.call_args[1]
        self.assertEqual(call_kwargs['name'], "sess1")

    def test_falls_back_to_map_file_when_no_map_name(self):
        info = _make_payload(map_name=None, map_file="KF-Offices")
        mock_discord.Embed.reset_mock()
        embed = asyncio.get_event_loop().run_until_complete(bot.embed_manager.build_session_embed(info, "sess1"))
        # Map is the second field added (index 1)
        map_field_call = embed.add_field.call_args_list[1]
        self.assertIn("KF-Offices", map_field_call[1]['value'])


class TestCreateSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.active_embeds.clear()
        bot.embed_manager.steam_profile_cache.clear()

    def test_sends_embed_and_stores_active_embed(self):
        info = _make_payload(
            name="Test Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
        )
        mock_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=mock_msg)

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.create_session_embed(channel, info, "sess1"))
        channel.send.assert_called_once()
        self.assertIn("sess1", bot.embed_manager.active_embeds)
        self.assertIsInstance(bot.embed_manager.active_embeds["sess1"], embed_mgr.ActiveEmbed)
        self.assertEqual(bot.embed_manager.active_embeds["sess1"].msg, mock_msg)


class TestUpdateSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.active_embeds.clear()
        bot.embed_manager.steam_profile_cache.clear()

    def test_edits_existing_embed(self):
        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()
        now = datetime.datetime.now()
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed(last_update=now)

        info = _make_payload(wave_state=2)

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.update_session_embed(info, "sess1"))
        mock_msg = bot.embed_manager.active_embeds["sess1"].msg
        mock_msg.edit.assert_called_once()
        self.assertEqual(bot.embed_manager.active_embeds["sess1"].last_payload, info)


class TestDeleteStaleEmbeds(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.active_embeds.clear()

    def test_deletes_old_embeds(self):
        stale_time = datetime.datetime.now() - datetime.timedelta(hours=5)
        embed = _make_active_embed(last_update=stale_time, session_id="old_sess")
        bot.embed_manager.active_embeds["old_sess"] = embed

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.delete_stale_embeds())
        embed.msg.delete.assert_called_once()
        self.assertNotIn("old_sess", bot.embed_manager.active_embeds)

    def test_keeps_recent_embeds(self):
        recent_time = datetime.datetime.now() - datetime.timedelta(minutes=1)
        bot.embed_manager.active_embeds["recent_sess"] = _make_active_embed(last_update=recent_time, session_id="recent_sess")

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.delete_stale_embeds())
        self.assertIn("recent_sess", bot.embed_manager.active_embeds)

    def test_deletes_multiple_stale_keeps_recent(self):
        now = datetime.datetime.now()
        stale1 = _make_active_embed(last_update=now - datetime.timedelta(hours=5), session_id="stale1")
        stale2 = _make_active_embed(last_update=now - datetime.timedelta(hours=10), session_id="stale2")
        recent = _make_active_embed(last_update=now - datetime.timedelta(minutes=1), session_id="recent")

        bot.embed_manager.active_embeds["stale1"] = stale1
        bot.embed_manager.active_embeds["stale2"] = stale2
        bot.embed_manager.active_embeds["recent"] = recent

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.delete_stale_embeds())
        stale1.msg.delete.assert_called_once()
        stale2.msg.delete.assert_called_once()
        self.assertNotIn("stale1", bot.embed_manager.active_embeds)
        self.assertNotIn("stale2", bot.embed_manager.active_embeds)
        self.assertIn("recent", bot.embed_manager.active_embeds)


class TestProcessSessionUpdates(unittest.TestCase):
    def setUp(self):
        bot.embed_manager.active_embeds.clear()
        bot.embed_manager.steam_profile_cache.clear()

    def test_skips_payload_with_pre_match_state(self):
        updates = {"x": _make_payload(match_state=-1, wave_state=-1, player_count=0)}
        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.process_session_updates(channel, updates))
        channel.send.assert_not_called()

    def test_skips_new_payload_with_abort_match_state(self):
        updates = {"x": _make_payload(match_state=3)}
        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.process_session_updates(channel, updates))
        channel.send.assert_not_called()

    def test_creates_embed_for_active_match(self):
        updates = {"x": _make_payload(
            name="Test Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
        )}
        mock_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=mock_msg)

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.process_session_updates(channel, updates))
        channel.send.assert_called_once()
        self.assertIn("sess1", bot.embed_manager.active_embeds)
        self.assertIsInstance(bot.embed_manager.active_embeds["sess1"], embed_mgr.ActiveEmbed)
        self.assertEqual(bot.embed_manager.active_embeds["sess1"].msg, mock_msg)

    def test_updates_existing_embed(self):
        bot.embed_manager.active_embeds["sess1"] = _make_active_embed()
        updates = {"x": _make_payload(wave_state=2)}

        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.process_session_updates(channel, updates))
        bot.embed_manager.active_embeds["sess1"].msg.edit.assert_called_once()
        channel.send.assert_not_called()

    def test_deletes_stale_embeds(self):
        stale_time = datetime.datetime.now() - datetime.timedelta(hours=5)
        embed = _make_active_embed(last_update=stale_time, session_id="old_sess")
        bot.embed_manager.active_embeds["old_sess"] = embed

        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.embed_manager.process_session_updates(channel, {}))
        embed.msg.delete.assert_called_once()
        self.assertNotIn("old_sess", bot.embed_manager.active_embeds)


class TestDeleteOwnMessages(unittest.TestCase):
    def test_deletes_own_messages(self):
        own_msg = MagicMock()
        bot.embed_manager.client.user = MagicMock()
        own_msg.author = bot.embed_manager.client.user
        own_msg.delete = AsyncMock()

        other_msg = MagicMock()
        other_msg.author = MagicMock()
        other_msg.delete = AsyncMock()

        async def fake_history(**kwargs):
            for msg in [own_msg, other_msg]:
                yield msg

        channel = MagicMock()
        channel.history = fake_history

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.delete_own_messages(channel))
        own_msg.delete.assert_called_once()
        other_msg.delete.assert_not_called()

    def test_handles_empty_channel(self):
        async def fake_history(**kwargs):
            return
            yield

        channel = MagicMock()
        channel.history = fake_history

        asyncio.get_event_loop().run_until_complete(bot.embed_manager.delete_own_messages(channel))


if __name__ == '__main__':
    unittest.main()
