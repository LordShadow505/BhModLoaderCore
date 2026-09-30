import os
import traceback
from typing import List, Union

from .variables import (MODS_PATH,
                        MOD_FILE_FORMAT,
                        MODS_SOURCES_PATH,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_MODS_FOLDER,
                        CheckExists)
from .mod import ModClass, ModSource, ModsHashSumCache
from .config import ModloaderCoreConfig
from .basedispatch import SendNotification
from ..notifications import NotificationType


class ModLoaderClass:
    modsSources: List[ModSource] = []
    modsClasses: List[ModClass] = []
    modsGhosts: list = []

    def __init__(self):
        self.config = ModloaderCoreConfig
        self.modsCachePath = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_MODS_FOLDER)
        if not os.path.exists(self.modsCachePath):
            os.mkdir(self.modsCachePath)

        self.modsHashSumCache = ModsHashSumCache(self.modsCachePath)

        # Auto-update obfuscation symbols on ModLoader startup
        try:
            from ..utils.symbols_manager import resolve_and_update_symbols
            import threading
            threading.Thread(target=resolve_and_update_symbols, kwargs={"force": False, "trigger": "Startup"}, daemon=True).start()
        except Exception:
            pass

    def reload(self):
        self.reloadMods()
        self.reloadModsSources()

    def clear(self):
        self.modsSources = []
        self.modsClasses = []
        self.modsGhosts = []

    @staticmethod
    def _getListingSwfs(swfs):
        """Return the small SWF inventory the UI needs to render a mod card.

        Passing compiled ActionScript source through the controller queue makes
        Loader startup depend on the largest installed mod.  The UI only uses
        the SWF and anchor names, so deliberately omit script bodies here.
        """
        listing_swfs = {}
        if not isinstance(swfs, dict):
            return listing_swfs

        for swf_name, swf_data in swfs.items():
            if not isinstance(swf_data, dict):
                continue
            scripts = swf_data.get("scripts", {})
            listing_swfs[swf_name] = {
                "scripts": {
                    anchor: "" for anchor in scripts
                } if isinstance(scripts, dict) else {},
                "sounds": list(swf_data.get("sounds", []) or []),
                "sprites": list(swf_data.get("sprites", []) or []),
            }
        return listing_swfs

    def getModsData(self):
        result = []
        for mod in self.modsClasses:
            try:
                d = mod.getDict(ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"])
                swf_names = list(mod.swfs.keys()) if hasattr(mod, 'swfs') and mod.swfs else []
                file_names = list(mod.files.values()) if hasattr(mod, 'files') and mod.files else []
                listing_swfs = self._getListingSwfs(getattr(mod, 'swfs', {}) or {})

                sprite_names = []
                if hasattr(mod, 'swfs') and mod.swfs:
                    for swf_data in mod.swfs.values():
                        if isinstance(swf_data, dict) and "sprites" in swf_data:
                            sprite_names.extend(swf_data["sprites"])

                d.update({
                    "modPath": getattr(mod, 'modPath', ""),
                    "previewsPaths": mod.getPreviewsPaths(),
                    "currentGameVersion": self.config.brawlhallaVersion,
                    "date": mod.date,
                    "swfNames": swf_names,
                    "fileNames": file_names,
                    "spriteNames": sprite_names,
                    "swfs": listing_swfs
                })
                result.append(d)
            except Exception as error:
                mod_path = getattr(mod, "modPath", "")
                SendNotification(
                    NotificationType.LoadingModError,
                    mod_path,
                    f"{type(error).__name__}: {error}",
                    traceback.format_exc(),
                )
        return result

    def getModsSourcesData(self):
        result = []
        for modSources in self.modsSources:
            data = modSources.getDict(
                ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"])
            swfs = getattr(modSources, "swfs", {}) or {}
            listing_swfs = self._getListingSwfs(swfs)
            sprite_names = [
                sprite
                for swf_data in swfs.values() if isinstance(swf_data, dict)
                for sprite in (swf_data.get("sprites", []) or [])
            ]
            data.update({
                "previewsPaths": modSources.getPreviewsPaths(),
                "currentGameVersion": self.config.brawlhallaVersion,
                "modSourcesPath": modSources.modSourcesPath,
                "date": modSources.date,
                "swfNames": list(swfs.keys()),
                "spriteNames": sprite_names,
                "swfs": listing_swfs
            })
            result.append(data)
        return result

    def loadMods(self):
        modsHashes = []

        if MODS_PATH:
            modsPath = MODS_PATH[0]
            CheckExists(modsPath, True)

            for modFile in os.listdir(modsPath):
                modPath = os.path.join(modsPath, modFile)
                if modFile.endswith(f".{MOD_FILE_FORMAT}") and os.path.isfile(modPath):
                    try:
                        modClass = ModClass(modPath=modPath, modsCachePath=self.modsCachePath, sharedHashCache=self.modsHashSumCache)
                        if modClass.hash not in modsHashes:
                            modsHashes.append(modClass.hash)
                            self.modsClasses.append(modClass)
                    except Exception as error:
                        SendNotification(
                            NotificationType.LoadingModError,
                            modPath,
                            f"{type(error).__name__}: {error}",
                            traceback.format_exc(),
                        )

        for modHash in self.modsHashSumCache.hashes.values():
            if modHash not in modsHashes:
                try:
                    modClass = ModClass(modsCachePath=self.modsCachePath, modHash=modHash, sharedHashCache=self.modsHashSumCache)
                    self.modsClasses.append(modClass)
                except Exception as error:
                    SendNotification(
                        NotificationType.LoadingModError,
                        "",
                        f"Cached mod '{modHash}' could not be loaded: {type(error).__name__}: {error}",
                        traceback.format_exc(),
                    )

    def reloadMods(self):
        self.modsClasses = []
        self.loadMods()

    def reloadMod(self, modPath: str):
        # 1. Remove if already exists in self.modsClasses
        for m in self.modsClasses:
            if m.modPath == modPath:
                self.modsClasses.remove(m)
                break

        # 2. Load it
        if os.path.exists(modPath):
            from .mod import ModClass
            modClass = ModClass(modPath=modPath, modsCachePath=self.modsCachePath, sharedHashCache=self.modsHashSumCache)
            if modClass.modFileExist:
                self.modsClasses.append(modClass)
                return modClass
        return None

    def loadModsSources(self):
        modsSourcesHashes = []
        if MODS_SOURCES_PATH:
            basePath = MODS_SOURCES_PATH[0]
            CheckExists(basePath, True)

            for modSourcesFolder in os.listdir(basePath):
                folderPath = os.path.join(basePath, modSourcesFolder)
                if os.path.isdir(folderPath) and not modSourcesFolder.startswith("__"):
                    modSource = ModSource(folderPath)
                    # Not load duplicate
                    if modSource.hash not in modsSourcesHashes:
                        modsSourcesHashes.append(modSource.hash)
                        self.modsSources.append(modSource)


    def reloadModsSources(self):
        self.modsSources: List[ModSource] = []
        self.loadModsSources()

    def getModByHash(self, hash: str) -> Union[ModClass, None]:
        for mod in self.modsClasses:
            if mod.hash == hash:
                return mod

        return None

    def getModSourcesByHash(self, hash: str) -> Union[ModSource, None]:
        for modSources in self.modsSources:
            if modSources.hash == hash:
                return modSources

        return None

    def createModSource(self, folderName: str) -> Union[ModSource, None]:
        path = os.path.join(MODS_SOURCES_PATH[0], folderName)
        if os.path.exists(path):
            return None
        else:
            os.mkdir(path)
            modSource = ModSource(path)
            self.modsSources.append(modSource)
            return modSource

    def load(self):
        self.loadMods()
        self.loadModsSources()


ModLoader = ModLoaderClass()
