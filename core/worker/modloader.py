import os
from typing import List, Union

from .variables import (MODS_PATH,
                        MOD_FILE_FORMAT,
                        MODS_SOURCES_PATH,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_MODS_FOLDER,
                        CheckExists)
from .mod import ModClass, ModSource, ModsHashSumCache
from .config import ModloaderCoreConfig


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

    def getModsData(self):
        result = []
        for mod in self.modsClasses:
            d = mod.getDict(ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"])
            swf_names = list(mod.swfs.keys()) if hasattr(mod, 'swfs') and mod.swfs else []
            file_names = list(mod.files.values()) if hasattr(mod, 'files') and mod.files else []
            
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
                "swfs": getattr(mod, 'swfs', {}) or {}
            })
            result.append(d)
        return result

    def getModsSourcesData(self):
        result = []
        for modSources in self.modsSources:
            data = modSources.getDict(
                ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"])
            swfs = getattr(modSources, "swfs", {}) or {}
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
                "swfs": swfs
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
                    except:
                        pass

        for modHash in self.modsHashSumCache.hashes.values():
            if modHash not in modsHashes:
                try:
                    modClass = ModClass(modsCachePath=self.modsCachePath, modHash=modHash, sharedHashCache=self.modsHashSumCache)
                    self.modsClasses.append(modClass)
                except:
                    pass

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
