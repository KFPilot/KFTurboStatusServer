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
    "steam_api_url": "https://fake.steam.api/ISteamUser/GetPlayerSummaries/v0002/"
}

with patch("builtins.open", mock_open(read_data=json.dumps(_fake_config))):
    import KFTurboServerStatusDiscordBot as bot


class TestBotConfig(unittest.TestCase):
    def test_config_fields(self):
        self.assertEqual(bot.bot_config.discord_token, "fake-token")
        self.assertEqual(bot.bot_config.channel_id, 123456789)
        self.assertEqual(bot.bot_config.listen_port, 9999)
        self.assertEqual(bot.bot_config.steam_api_key, "fake-key")
        self.assertIn("ISteamUser", bot.bot_config.steam_api_url)

    def test_config_types(self):
        self.assertIsInstance(bot.bot_config, bot.BotConfig)
        self.assertIsInstance(bot.bot_config.channel_id, int)
        self.assertIsInstance(bot.bot_config.listen_port, int)

    def test_update_cooldown_defaults(self):
        self.assertEqual(bot.bot_config.update_cooldown, 0.1)
        self.assertIsInstance(bot.bot_config.update_cooldown, float)


class TestSteamProfile(unittest.TestCase):
    def test_fields(self):
        profile = bot.SteamProfile(steam_id="12345", persona_name="Player1")
        self.assertEqual(profile.steam_id, "12345")
        self.assertEqual(profile.persona_name, "Player1")

    def test_equality(self):
        a = bot.SteamProfile(steam_id="1", persona_name="A")
        b = bot.SteamProfile(steam_id="1", persona_name="A")
        c = bot.SteamProfile(steam_id="1", persona_name="B")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestServerPayload(unittest.TestCase):
    def test_defaults(self):
        payload = bot.ServerPayload(
            name=None, game=None, difficulty=None, map_file=None,
            map_name=None, final_wave=None, match_state=None,
            wave_state=None, player_count=None,
        )
        self.assertEqual(payload.player_list, [])
        self.assertEqual(payload.spectator_list, [])
        self.assertIsNone(payload.session_id)

    def test_default_factory_independence(self):
        """Each instance should get its own list, not a shared reference."""
        a = bot.ServerPayload(
            name=None, game=None, difficulty=None, map_file=None,
            map_name=None, final_wave=None, match_state=None,
            wave_state=None, player_count=None,
        )
        b = bot.ServerPayload(
            name=None, game=None, difficulty=None, map_file=None,
            map_name=None, final_wave=None, match_state=None,
            wave_state=None, player_count=None,
        )
        a.player_list.append("test")
        self.assertEqual(b.player_list, [])

    def test_equality(self):
        kwargs = dict(
            name="Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=3, player_count="2|6|0",
            player_list=["id1"], spectator_list=[], session_id="abc",
        )
        self.assertEqual(bot.ServerPayload(**kwargs), bot.ServerPayload(**kwargs))

        changed = dict(kwargs, wave_state=4)
        self.assertNotEqual(bot.ServerPayload(**kwargs), bot.ServerPayload(**changed))


class TestParsePayload(unittest.TestCase):
    def _make_raw(self, **overrides):
        base = {
            "serv": "Test Server", "game": "KFTurbo", "diff": "Hard",
            "mapf": "KF-Farm", "mapn": "Farm", "fw": 10,
            "ms": 0, "ws": 3, "pc": "2|6|0",
            "pl": ["id1", "id2"], "sl": ["id3"], "sid": "session1",
        }
        base.update(overrides)
        return base

    def test_full_payload(self):
        raw = self._make_raw()
        result = bot.parse_payload(raw)
        self.assertIsInstance(result, bot.ServerPayload)
        self.assertEqual(result.name, "Test Server")
        self.assertEqual(result.game, "KFTurbo")
        self.assertEqual(result.difficulty, "Hard")
        self.assertEqual(result.map_file, "KF-Farm")
        self.assertEqual(result.map_name, "Farm")
        self.assertEqual(result.final_wave, 10)
        self.assertEqual(result.match_state, 0)
        self.assertEqual(result.wave_state, 3)
        self.assertEqual(result.player_count, "2|6|0")
        self.assertEqual(result.player_list, ["id1", "id2"])
        self.assertEqual(result.spectator_list, ["id3"])
        self.assertEqual(result.session_id, "session1")

    def test_missing_optional_fields(self):
        result = bot.parse_payload({"sid": "s1"})
        self.assertIsInstance(result, bot.ServerPayload)
        self.assertIsNone(result.name)
        self.assertIsNone(result.game)
        self.assertIsNone(result.map_name)
        self.assertEqual(result.player_list, [])
        self.assertEqual(result.spectator_list, [])
        self.assertEqual(result.session_id, "s1")

    def test_empty_payload(self):
        result = bot.parse_payload({})
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
        self.assertEqual(result.player_count, raw["pc"])
        self.assertEqual(result.player_list, raw["pl"])
        self.assertEqual(result.spectator_list, raw["sl"])
        self.assertEqual(result.session_id, raw["sid"])


class TestInfoChanged(unittest.TestCase):
    def _make_payload(self, **overrides):
        base = dict(
            name="S", game="G", difficulty="D", map_file="M",
            map_name="N", final_wave=7, match_state=0,
            wave_state=1, player_count="1|6|0",
            player_list=[], spectator_list=[], session_id="x",
        )
        base.update(overrides)
        return bot.ServerPayload(**base)

    def test_identical(self):
        a = self._make_payload()
        b = self._make_payload()
        self.assertFalse(bot.info_changed(a, b))

    def test_different_wave(self):
        a = self._make_payload(wave_state=1)
        b = self._make_payload(wave_state=2)
        self.assertTrue(bot.info_changed(a, b))

    def test_different_player_list(self):
        a = self._make_payload(player_list=["id1"])
        b = self._make_payload(player_list=["id1", "id2"])
        self.assertTrue(bot.info_changed(a, b))

    def test_different_match_state(self):
        a = self._make_payload(match_state=-1)
        b = self._make_payload(match_state=0)
        self.assertTrue(bot.info_changed(a, b))

    def test_different_name(self):
        a = self._make_payload(name="Server A")
        b = self._make_payload(name="Server B")
        self.assertTrue(bot.info_changed(a, b))


class TestGetSteamProfiles(unittest.TestCase):
    def setUp(self):
        bot.steam_profile_cache.clear()

    def test_returns_cached_profiles(self):
        bot.steam_profile_cache["111"] = bot.SteamProfile(steam_id="111", persona_name="CachedPlayer")
        result = asyncio.get_event_loop().run_until_complete(bot.get_steam_profiles(["111"]))
        self.assertIsInstance(result["111"], bot.SteamProfile)
        self.assertEqual(result["111"].persona_name, "CachedPlayer")

    def test_returns_multiple_cached_profiles(self):
        bot.steam_profile_cache["111"] = bot.SteamProfile(steam_id="111", persona_name="Player1")
        bot.steam_profile_cache["222"] = bot.SteamProfile(steam_id="222", persona_name="Player2")
        result = asyncio.get_event_loop().run_until_complete(bot.get_steam_profiles(["111", "222"]))
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

        with patch("KFTurboServerStatusDiscordBot.aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.get_event_loop().run_until_complete(bot.get_steam_profiles(["999"]))
            self.assertIsInstance(result["999"], bot.SteamProfile)
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

        with patch("KFTurboServerStatusDiscordBot.aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.get_event_loop().run_until_complete(bot.get_steam_profiles(["222"]))

        self.assertIsInstance(result["222"], bot.SteamProfile)
        self.assertEqual(result["222"].persona_name, "FetchedPlayer")
        self.assertIn("222", bot.steam_profile_cache)
        self.assertEqual(bot.steam_profile_cache["222"].persona_name, "FetchedPlayer")

    def test_only_fetches_uncached_ids(self):
        """Should not make an API call when all IDs are cached."""
        bot.steam_profile_cache["111"] = bot.SteamProfile(steam_id="111", persona_name="Cached")

        with patch("KFTurboServerStatusDiscordBot.aiohttp.ClientSession") as mock_cls:
            result = asyncio.get_event_loop().run_until_complete(bot.get_steam_profiles(["111"]))
            mock_cls.assert_not_called()

        self.assertEqual(result["111"].persona_name, "Cached")


class TestActiveEmbed(unittest.TestCase):
    def test_fields(self):
        mock_msg = MagicMock()
        now = datetime.datetime.now()
        embed = bot.ActiveEmbed(msg=mock_msg, last_update=now)
        self.assertEqual(embed.msg, mock_msg)
        self.assertEqual(embed.last_update, now)

    def test_mutability(self):
        mock_msg = MagicMock()
        now = datetime.datetime.now()
        embed = bot.ActiveEmbed(msg=mock_msg, last_update=now)
        new_time = now + datetime.timedelta(hours=1)
        embed.last_update = new_time
        self.assertEqual(embed.last_update, new_time)


class TestBuildSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.steam_profile_cache.clear()

    def _make_info(self, **overrides):
        base = dict(
            name="Test Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=1, player_count="1|6|0",
            player_list=[], spectator_list=[], session_id="sess1",
        )
        base.update(overrides)
        return bot.ServerPayload(**base)

    def test_returns_embed(self):
        info = self._make_info()
        result = asyncio.get_event_loop().run_until_complete(bot.build_session_embed(info, "sess1"))
        self.assertIsNotNone(result)

    def test_uses_name_as_title(self):
        info = self._make_info(name="My Server")
        mock_discord.Embed.reset_mock()
        asyncio.get_event_loop().run_until_complete(bot.build_session_embed(info, "sess1"))
        mock_discord.Embed.assert_called_once()
        call_kwargs = mock_discord.Embed.call_args[1]
        self.assertEqual(call_kwargs['title'], "My Server")

    def test_falls_back_to_session_id_when_no_name(self):
        info = self._make_info(name=None)
        mock_discord.Embed.reset_mock()
        asyncio.get_event_loop().run_until_complete(bot.build_session_embed(info, "sess1"))
        call_kwargs = mock_discord.Embed.call_args[1]
        self.assertEqual(call_kwargs['title'], "sess1")

    def test_falls_back_to_map_file_when_no_map_name(self):
        info = self._make_info(map_name=None, map_file="KF-Offices")
        mock_discord.Embed.reset_mock()
        embed = asyncio.get_event_loop().run_until_complete(bot.build_session_embed(info, "sess1"))
        # Check that add_field was called with map_file in the value
        game_field_call = embed.add_field.call_args_list[0]
        self.assertIn("KF-Offices", game_field_call[1]['value'])


class TestCreateSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.active_embeds.clear()
        bot.steam_profile_cache.clear()

    def test_sends_embed_and_stores_active_embed(self):
        info = bot.ServerPayload(
            name="Test Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=1, player_count="1|6|0",
            session_id="sess1",
        )
        mock_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=mock_msg)

        asyncio.get_event_loop().run_until_complete(bot.create_session_embed(channel, info, "sess1"))
        channel.send.assert_called_once()
        self.assertIn("sess1", bot.active_embeds)
        self.assertIsInstance(bot.active_embeds["sess1"], bot.ActiveEmbed)
        self.assertEqual(bot.active_embeds["sess1"].msg, mock_msg)


class TestUpdateSessionEmbed(unittest.TestCase):
    def setUp(self):
        bot.active_embeds.clear()
        bot.steam_profile_cache.clear()

    def test_edits_existing_embed(self):
        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()
        now = datetime.datetime.now()
        bot.active_embeds["sess1"] = bot.ActiveEmbed(msg=mock_msg, last_update=now)

        info = bot.ServerPayload(
            name="Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=2, player_count="1|6|0",
            session_id="sess1",
        )

        asyncio.get_event_loop().run_until_complete(bot.update_session_embed(info, "sess1"))
        mock_msg.edit.assert_called_once()
        self.assertGreater(bot.active_embeds["sess1"].last_update, now)


class TestDeleteStaleEmbeds(unittest.TestCase):
    def setUp(self):
        bot.active_embeds.clear()

    def test_deletes_old_embeds(self):
        mock_msg = MagicMock()
        mock_msg.delete = AsyncMock()
        stale_time = datetime.datetime.now() - datetime.timedelta(hours=5)
        bot.active_embeds["old_sess"] = bot.ActiveEmbed(msg=mock_msg, last_update=stale_time)

        asyncio.get_event_loop().run_until_complete(bot.delete_stale_embeds())
        mock_msg.delete.assert_called_once()
        self.assertNotIn("old_sess", bot.active_embeds)

    def test_keeps_recent_embeds(self):
        mock_msg = MagicMock()
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        bot.active_embeds["recent_sess"] = bot.ActiveEmbed(msg=mock_msg, last_update=recent_time)

        asyncio.get_event_loop().run_until_complete(bot.delete_stale_embeds())
        self.assertIn("recent_sess", bot.active_embeds)

    def test_deletes_multiple_stale_keeps_recent(self):
        stale1 = MagicMock()
        stale1.delete = AsyncMock()
        stale2 = MagicMock()
        stale2.delete = AsyncMock()
        recent = MagicMock()

        now = datetime.datetime.now()
        bot.active_embeds["stale1"] = bot.ActiveEmbed(msg=stale1, last_update=now - datetime.timedelta(hours=5))
        bot.active_embeds["stale2"] = bot.ActiveEmbed(msg=stale2, last_update=now - datetime.timedelta(hours=10))
        bot.active_embeds["recent"] = bot.ActiveEmbed(msg=recent, last_update=now - datetime.timedelta(hours=1))

        asyncio.get_event_loop().run_until_complete(bot.delete_stale_embeds())
        stale1.delete.assert_called_once()
        stale2.delete.assert_called_once()
        self.assertNotIn("stale1", bot.active_embeds)
        self.assertNotIn("stale2", bot.active_embeds)
        self.assertIn("recent", bot.active_embeds)


class TestUpdateActiveEmbeds(unittest.TestCase):
    def setUp(self):
        bot.session_payloads.clear()
        bot.active_embeds.clear()
        bot.steam_profile_cache.clear()

    def test_skips_payload_without_session_id(self):
        bot.session_payloads["x"] = bot.ServerPayload(
            name="S", game="G", difficulty="D", map_file="M",
            map_name="N", final_wave=7, match_state=0,
            wave_state=1, player_count="1|6|0",
            session_id=None,
        )
        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.update_active_embeds(channel))
        channel.send.assert_not_called()

    def test_skips_payload_with_pre_match_state(self):
        bot.session_payloads["x"] = bot.ServerPayload(
            name="S", game="G", difficulty="D", map_file="M",
            map_name="N", final_wave=7, match_state=-1,
            wave_state=-1, player_count="0|6|0",
            session_id="sess1",
        )
        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.update_active_embeds(channel))
        channel.send.assert_not_called()

    def test_creates_embed_for_active_match(self):
        bot.session_payloads["x"] = bot.ServerPayload(
            name="Test Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=1, player_count="1|6|0",
            session_id="sess1",
        )
        mock_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=mock_msg)

        asyncio.get_event_loop().run_until_complete(bot.update_active_embeds(channel))
        channel.send.assert_called_once()
        self.assertIn("sess1", bot.active_embeds)
        self.assertIsInstance(bot.active_embeds["sess1"], bot.ActiveEmbed)
        self.assertEqual(bot.active_embeds["sess1"].msg, mock_msg)

    def test_updates_existing_embed(self):
        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()
        now = datetime.datetime.now()
        bot.active_embeds["sess1"] = bot.ActiveEmbed(msg=mock_msg, last_update=now)
        bot.session_payloads["x"] = bot.ServerPayload(
            name="Server", game="KFTurbo", difficulty="Hard",
            map_file="KF-Farm", map_name="Farm", final_wave=10,
            match_state=0, wave_state=2, player_count="1|6|0",
            session_id="sess1",
        )

        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.update_active_embeds(channel))
        mock_msg.edit.assert_called_once()
        channel.send.assert_not_called()

    def test_deletes_stale_embeds(self):
        mock_msg = MagicMock()
        mock_msg.delete = AsyncMock()
        stale_time = datetime.datetime.now() - datetime.timedelta(hours=5)
        bot.active_embeds["old_sess"] = bot.ActiveEmbed(msg=mock_msg, last_update=stale_time)

        channel = MagicMock()
        asyncio.get_event_loop().run_until_complete(bot.update_active_embeds(channel))
        mock_msg.delete.assert_called_once()
        self.assertNotIn("old_sess", bot.active_embeds)


class TestEmbedUpdateLoop(unittest.TestCase):
    def setUp(self):
        bot.session_payloads.clear()
        bot.active_embeds.clear()
        bot.steam_profile_cache.clear()

    def test_calls_update_active_embeds_after_sleep(self):
        """The loop should sleep then call update_active_embeds."""
        bot.session_payloads["x"] = bot.ServerPayload(
            name="S", game="G", difficulty="D", map_file="M",
            map_name="N", final_wave=7, match_state=0,
            wave_state=1, player_count="1|6|0",
            session_id="sess1",
        )
        mock_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=mock_msg)

        call_count = 0
        original_sleep = asyncio.sleep
        async def fake_sleep(delay):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.CancelledError()

        with patch("KFTurboServerStatusDiscordBot.asyncio.sleep", side_effect=fake_sleep):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.get_event_loop().run_until_complete(bot.embed_update_loop(channel))

        channel.send.assert_called_once()
        self.assertIn("sess1", bot.active_embeds)

    def test_continues_on_error(self):
        """The loop should catch errors and keep running."""
        channel = MagicMock()

        call_count = 0
        async def fake_sleep(delay):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError()

        with patch("KFTurboServerStatusDiscordBot.asyncio.sleep", side_effect=fake_sleep), \
             patch("KFTurboServerStatusDiscordBot.update_active_embeds", side_effect=[Exception("test error"), None]):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.get_event_loop().run_until_complete(bot.embed_update_loop(channel))

        # Should have gone through 2 iterations (error on first, success on second) before cancel on third sleep
        self.assertEqual(call_count, 3)


if __name__ == '__main__':
    unittest.main()
