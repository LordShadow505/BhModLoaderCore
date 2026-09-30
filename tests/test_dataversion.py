import unittest
from typing import Dict, List
from unittest.mock import patch

from core.worker.dataversion import DataClass
from core.worker.gameswf import GameSwf
from core.worker.modloader import ModLoaderClass


class _State(DataClass):
    values: Dict[str, str] = {}
    entries: List[str] = []
    enabled: bool = True

    def __init__(self):
        pass


class _BrokenListedMod:
    modPath = "C:/Mods/broken.bmod"

    def getDict(self, ignoredVars=None):
        raise ValueError("legacy metadata is incomplete")


class DataMetaclassTests(unittest.TestCase):
    def test_mutable_class_defaults_are_isolated_per_instance(self):
        first = _State()
        second = _State()

        first.values["Gfx_Ahsoka.swf"] = "a_Mouth_Ahsoka"
        first.entries.append("a_Mouth_Ahsoka")

        self.assertEqual(second.values, {})
        self.assertEqual(second.entries, [])
        self.assertTrue(second.enabled)

    def test_game_swfs_do_not_share_tracking_state(self):
        with patch("core.worker.gameswf.Swf"):
            body_swf = GameSwf("Gfx_Ahsoka.swf")
            weapon_swf = GameSwf("Gfx_Ahsoka_Katar.swf")

        body_swf.modifiedAnchorsMap["a_Mouth_Ahsoka"] = "mod-hash"
        body_swf.anchors["a_Mouth_Ahsoka"] = 100

        self.assertEqual(weapon_swf.modifiedAnchorsMap, {})
        self.assertEqual(weapon_swf.anchors, {})

    def test_listing_inventory_omits_actionscript_bodies(self):
        listing = ModLoaderClass._getListingSwfs({
            "Gfx_Ahsoka.swf": {
                "scripts": {"a_Arm1_Ahsoka": "very large script body"},
                "sounds": ["s_Ahsoka"],
                "sprites": ["a_Arm1_Ahsoka"],
            }
        })

        self.assertEqual(listing["Gfx_Ahsoka.swf"]["scripts"], {"a_Arm1_Ahsoka": ""})
        self.assertEqual(listing["Gfx_Ahsoka.swf"]["sounds"], ["s_Ahsoka"])
        self.assertEqual(listing["Gfx_Ahsoka.swf"]["sprites"], ["a_Arm1_Ahsoka"])

    def test_cross_swf_tracking_is_discarded_before_uninstall(self):
        game_swf = object.__new__(GameSwf)
        game_swf.modifiedAnchorsMap = {
            "a_Mouth_Ahsoka": "mod-hash",
            "a_WeaponKatarBlade_Ahsoka": "mod-hash",
            "a_SomeoneElse": "another-mod",
        }
        game_swf.anchors = {
            "a_Mouth_Ahsoka": 100,
            "a_WeaponKatarBlade_Ahsoka": 101,
        }
        game_swf.scripts = {"a_Mouth_Ahsoka": "old body"}

        game_swf.discardStaleModAnchors(
            "mod-hash", {"a_WeaponKatarBlade_Ahsoka"})

        self.assertNotIn("a_Mouth_Ahsoka", game_swf.modifiedAnchorsMap)
        self.assertNotIn("a_Mouth_Ahsoka", game_swf.anchors)
        self.assertNotIn("a_Mouth_Ahsoka", game_swf.scripts)
        self.assertEqual(
            game_swf.modifiedAnchorsMap["a_WeaponKatarBlade_Ahsoka"], "mod-hash")
        self.assertEqual(game_swf.modifiedAnchorsMap["a_SomeoneElse"], "another-mod")

    def test_bad_listing_entry_does_not_abort_the_rest_of_the_mod_list(self):
        loader = object.__new__(ModLoaderClass)
        loader.modsClasses = [_BrokenListedMod()]
        loader.config = type("Config", (), {"brawlhallaVersion": "All"})()

        with patch("core.worker.modloader.SendNotification") as notify:
            self.assertEqual(loader.getModsData(), [])

        notification_type, path, summary, details = notify.call_args.args
        self.assertEqual(notification_type.name, "LoadingModError")
        self.assertEqual(path, "C:/Mods/broken.bmod")
        self.assertIn("legacy metadata is incomplete", summary)
        self.assertIn("ValueError", details)


if __name__ == "__main__":
    unittest.main()
