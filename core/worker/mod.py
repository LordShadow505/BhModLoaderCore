import os
import re
import shutil
import threading
import time
import traceback
from typing import List, Dict, Tuple, Union

from .vartypes import ModDataSwfsTyped
from .variables import (MODS_PATH,
                        MODS_SOURCES_PATH,
                        MOD_FILE_FORMAT,
                        METADATA_FORMAT_MOD,
                        METADATA_FORMAT_CACHE_MOD,
                        METADATA_FORMAT_VERSION,
                        METADATA_FORMAT_CACHE_MODS_HASH_SUM,
                        METADATA_CACHE_MODS_HASH_SUM_FILE,
                        METADATA_CACHE_MOD_PREVIEWS_FOLDER,
                        METADATA_CACHE_MOD_FILE,
                        MODS_SOURCES_CACHE_FILE,
                        MODS_SOURCES_CACHE_PREVIEW)
from .dataversion import DataClass, DataVariable
from .gameswf import GetGameFileClass
from .gamefiles import GameFiles
from .brawlhalla import BRAWLHALLA_SWFS, BRAWLHALLA_FILES, BRAWLHALLA_VERSION
from .basedispatch import SendNotification
from ..notifications import NotificationType

from ..utils.hash import RandomHash, HashFile

from ..swf.swf import Swf, GetElementId, SetElementId, GetShapeBitmapId, SetShapeBitmapId
from ..ffdec.classes import (CSMTextSettingsTag,
                             DefineFontNameTag,
                             DefineFontAlignZonesTag,
                             DefineBitsLosslessTags,
                             DefineFontTags,
                             DefineEditTextTag,
                             DefineTextTag,
                             DefineSoundTag,
                             DefineShapeTags,
                             DefineSpriteTag,
                             PlaceObject2Tag,
                             PlaceObject3Tag)
from ..notifications import NotificationType
from ..lang.language import LangFile

__all__ = ["BaseModClass", "ModSource", "ModClass"]


LOCK = threading.RLock()


class BaseModClass(DataClass):
    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 0, "formatVersion")
    formatVersion: int = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_MOD, 0, "formatType")
    formatType: str = METADATA_FORMAT_MOD

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "gameVersion")
    gameVersion: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "name")
    name: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "author")
    author: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "version")
    version: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "description")
    description: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "tags")
    tags: List[str] = []

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "previewsIds")
    previewsIds: Dict[int, str] = {}

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "hash")
    hash: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "swfs")
    swfs: Dict[str, ModDataSwfsTyped] = {}

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "files")
    files: Dict[int, str] = {}

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "langFiles")
    langFiles: Dict[str, Dict[str, str]] = {}  # {"language.1.bin": {"key": "new_value"}}

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "authorId")
    authorId: int = 0

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "modId")
    modId: int = 0

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "platform")
    platform: str = ""

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "modUrl")
    modUrl: str = ""

    def loadModData(self):
        pass

    def getGameVersion(self):
        return self.gameVersion

    def getName(self):
        return self.name

    def getAuthor(self):
        return self.author

    def getVersion(self):
        return self.version

    def getDescription(self):
        return self.description

    def getTags(self):
        return self.tags

    def getPreviewsPaths(self) -> List[str]:
        pass

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        pass

    @property
    def date(self) -> float:
        return 0.0


class ModSource(BaseModClass):
    regexSpriteFile = re.compile(r"DefineSprite_(\d+)_?(.+|)?")
    regexSoundFile = re.compile(r"\d+_([^.]+)")
    regexAsFile = re.compile(r"([^.]+)\.as")

    DEFAULT_AUTHOR = ""
    DEFAULT_GAME_VERSION = "All"
    DEFAULT_VERSION = "1.0"

    def __init__(self, modSourcesPath: str):
        SendNotification(NotificationType.LoadingModSource, modSourcesPath)

        self.modSourcesPath = modSourcesPath
        self.folderName = os.path.basename(modSourcesPath)
        self.cachePath = os.path.join(self.modSourcesPath, MODS_SOURCES_CACHE_FILE)
        self.previewsPath = os.path.join(self.modSourcesPath, MODS_SOURCES_CACHE_PREVIEW)
        if MODS_PATH:
            self.modPath = os.path.join(MODS_PATH[0], f"{self.folderName}.{MOD_FILE_FORMAT}")
        else:
            self.modPath = os.path.join(MODS_SOURCES_PATH[0], f"{self.folderName}.{MOD_FILE_FORMAT}")

        self.loadModData()

    def loadModData(self):
        loaded = self.loadJsonFile(self.cachePath, ignoredVars=["formatVersion", "swfs", "files", "previewsIds"])

        if not loaded:
            #print(f"New mod source '{self.folderName}' detected")
            if not self.author:
                self.author = self.DEFAULT_AUTHOR
            if not self.gameVersion:
                self.gameVersion = self.DEFAULT_GAME_VERSION
            if not self.version:
                self.version = self.DEFAULT_VERSION
            self.saveModData()

    def saveModData(self):
        if not self.hash:
            self.hash = RandomHash()

        self.saveJsonFile(self.cachePath)

    def setGameVersion(self, gameVersion: str):
        self.gameVersion = gameVersion

    def setName(self, name: str):
        self.name = name

    def setAuthor(self, author: str):
        self.author = author

    def setVersion(self, version: str):
        self.version = version

    def setDescription(self, description: str):
        self.description = description

    def setTags(self, tags: list):
        self.tags = tags

    def setPreviewsPaths(self, previewsPaths: list):
        if not os.path.exists(self.previewsPath):
            os.mkdir(self.previewsPath)

        removePreviewPath = self.getPreviewsPaths()

        for n, previewPath in enumerate(previewsPaths):
            previewFormat = os.path.splitext(previewPath)[1]
            if previewPath and os.path.exists(previewPath):
                cachePreviewPath = os.path.join(self.previewsPath, f"preview{n}{previewFormat}")

                if cachePreviewPath in removePreviewPath:
                    removePreviewPath.remove(cachePreviewPath)

                with open(previewPath, "rb") as orig:
                    image = orig.read()
                with open(cachePreviewPath, "wb") as new:
                    new.write(image)
                del image

        for previewPath in removePreviewPath:
            os.remove(previewPath)

    def getPreviewsPaths(self) -> List[str]:
        previewsPaths = []
        if os.path.exists(self.previewsPath):
            for previewPath in os.listdir(self.previewsPath):
                previewsPaths.append(os.path.join(self.previewsPath, previewPath))

        return previewsPaths

    @property
    def date(self) -> float:
        if os.path.exists(self.modSourcesPath):
            return os.path.getmtime(self.modSourcesPath)
        return 0.0

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        previews = []

        if os.path.exists(self.previewsPath):
            for previewPath in self.getPreviewsPaths():
                previewFormat = os.path.splitext(previewPath)[1][1:]
                with open(previewPath, "rb") as preview:
                    previews.append((preview.read(), previewFormat))

        return previews

    def getElementsCount(self):
        return len([file for root, dirs, files in os.walk(self.modSourcesPath) for file in files]) - \
               len(self.getPreviewsPaths()) - 1  # 1 - _cache.json

    def compile(self):
        SendNotification(NotificationType.CompileElementsCount, self.hash, self.getElementsCount())

        tempPath = self.modPath + ".tmp"
        if os.path.exists(tempPath):
            try:
                os.remove(tempPath)
            except:
                pass

        modSwf = Swf(tempPath)
        if modSwf.metaData is None:
            modSwf.addMetadata()
        self.swfs = {}
        self.previewsIds = {}
        self.files = {}
        self.langFiles = {}

        try:
            for folder in os.listdir(self.modSourcesPath):
                folderPath = os.path.join(self.modSourcesPath, folder)

                if os.path.isfile(folderPath):
                    continue

                # Import game elements
                if folder.endswith(".swf") and folder in BRAWLHALLA_SWFS:
                    gameSwfName: str = folder
                    elementsMap = {}
                    self.swfs[gameSwfName] = {}
                    self.swfs[gameSwfName]["scripts"] = {}
                    self.swfs[gameSwfName]["sounds"] = []
                    self.swfs[gameSwfName]["sprites"] = []

                    for category in os.listdir(folderPath):
                        categoryPath = os.path.join(folderPath, category)
                        seen_sprite_ids = {}
                        seen_internal_sprite_ids = {}

                        for elementPath in os.listdir(categoryPath):
                            if category == "scripts":
                                if script := self.regexAsFile.findall(elementPath):
                                    scriptAnchor = script[0]
                                    #print("Import ActionScript", scriptAnchor)
                                    SendNotification(NotificationType.CompileModSourcesImportActionScripts,
                                                     self.hash, scriptAnchor)

                                    with open(os.path.join(categoryPath, elementPath), "r") as actionScript:
                                        self.swfs[gameSwfName]["scripts"][scriptAnchor] = actionScript.read()

                            elif category == "sounds":
                                if sound := self.regexSoundFile.findall(elementPath):
                                    soundAnchor = sound[0]
                                    #print("Import Sound", soundAnchor)
                                    SendNotification(NotificationType.CompileModSourcesImportSound, self.hash, soundAnchor)

                                    self.swfs[gameSwfName]["sounds"].append(soundAnchor)

                                    soundTag = modSwf.importSoundFile(os.path.join(categoryPath, elementPath))
                                    modSwf.symbolClass.addTag(GetElementId(soundTag), soundAnchor)

                            elif category == "sprites":
                                if sprite := self.regexSpriteFile.findall(elementPath):
                                    sprite_id_str, spriteAnchor = sprite[0]

                                    if sprite_id_str in seen_sprite_ids:
                                        SendNotification(NotificationType.CompileModSourcesDuplicateSpriteId,
                                                         self.hash, sprite_id_str, elementPath, seen_sprite_ids[sprite_id_str])
                                        raise KeyError(f"Duplicate sprite ID {sprite_id_str} detected between '{elementPath}' and '{seen_sprite_ids[sprite_id_str]}'")
                                    
                                    seen_sprite_ids[sprite_id_str] = elementPath

                                    SendNotification(NotificationType.CompileModSourcesImportSprite,
                                                     self.hash, spriteAnchor)

                                    if not spriteAnchor:
                                        SendNotification(NotificationType.CompileModSourcesSpriteHasNoSymbolclass,
                                                         self.hash, elementPath)
                                        continue

                                    self.swfs[gameSwfName]["sprites"].append(spriteAnchor)

                                    spriteSwf = Swf(os.path.join(categoryPath, elementPath, "frames.swf"))

                                    spriteElement = None
                                    spriteId = 0
                                    for element in spriteSwf.elementsList[::-1]:
                                        if isinstance(element, DefineSpriteTag):
                                            spriteElement = element
                                            spriteId = GetElementId(element)
                                            break
                                    else:
                                        #print("Not found sprite in:", elementPath)
                                        SendNotification(NotificationType.CompileModSourcesSpriteNotFoundInFolder,
                                                         self.hash, elementPath)
                                        continue

                                    if spriteId in seen_internal_sprite_ids:
                                        SendNotification(NotificationType.CompileModSourcesDuplicateSpriteId,
                                                         self.hash, str(spriteId), elementPath, seen_internal_sprite_ids[spriteId])
                                        raise KeyError(f"Duplicate internal sprite ID {spriteId} detected between '{elementPath}' and '{seen_internal_sprite_ids[spriteId]}'")
                                    
                                    seen_internal_sprite_ids[spriteId] = elementPath

                                    cloneSprites = []
                                    cloneShapes = []

                                    for element in sorted(spriteSwf.elementsList, key=lambda x: GetElementId(x)):
                                        if not isinstance(element,
                                                          (CSMTextSettingsTag, DefineFontNameTag,
                                                           DefineFontAlignZonesTag, PlaceObject2Tag)):

                                            if GetElementId(element) in elementsMap:
                                                if element == spriteElement:
                                                    for _element in spriteSwf.elementsList:
                                                        if isinstance(_element, (*DefineShapeTags, DefineEditTextTag,
                                                                                  DefineSpriteTag,
                                                                                  *DefineBitsLosslessTags)) or \
                                                                element == spriteElement:

                                                            elementsMap.pop(GetElementId(_element), None)
                                                else:
                                                    continue

                                            newElId = modSwf.getNextCharacterId()
                                            cloneEl = modSwf.cloneAndAddElement(element, newElId)
                                            elementsMap[GetElementId(element)] = GetElementId(cloneEl)

                                            if isinstance(cloneEl, DefineShapeTags):
                                                if GetShapeBitmapId(cloneEl) is not None:
                                                    cloneShapes.append(cloneEl)

                                            elif isinstance(cloneEl, DefineSpriteTag):
                                                cloneSprites.append(cloneEl)

                                            elif isinstance(element, DefineFontTags):
                                                for dependentElement in spriteSwf.getElementById(GetElementId(element),
                                                                                                 (DefineFontNameTag,
                                                                                                  DefineFontAlignZonesTag)):
                                                    modSwf.cloneAndAddElement(dependentElement, newElId)

                                            elif isinstance(element, DefineEditTextTag):
                                                if dependentElement := spriteSwf.getElementById(GetElementId(element),
                                                                                                CSMTextSettingsTag):
                                                    modSwf.cloneAndAddElement(dependentElement[0], newElId)
                                                cloneEl.fontId = elementsMap[element.fontId]

                                            elif isinstance(element, DefineTextTag):
                                                if dependentElement := spriteSwf.getElementById(GetElementId(element),
                                                                                                CSMTextSettingsTag):
                                                    modSwf.cloneAndAddElement(dependentElement[0], newElId)

                                                for textRecord in cloneEl.textRecords:
                                                    if textRecord.styleFlagsHasFont:
                                                        textRecord.fontId = elementsMap[textRecord.fontId]

                                    for cloneSprite in cloneSprites:
                                        for sEl in cloneSprite.getTags().iterator():
                                            if isinstance(sEl, (PlaceObject2Tag, PlaceObject3Tag)) and sEl.characterId > 0:
                                                if sEl.characterId not in elementsMap:
                                                    SendNotification(NotificationType.CompileModSourcesDefectivePiece,
                                                                     self.hash, elementPath, sEl.characterId)
                                                    raise KeyError(f"Defective piece in '{elementPath}': element {sEl.characterId} not found")
                                                SetElementId(sEl, elementsMap[sEl.characterId])

                                    for cloneShape in cloneShapes:
                                        bitmapId = GetShapeBitmapId(cloneShape)
                                        if bitmapId not in elementsMap:
                                            SendNotification(NotificationType.CompileModSourcesDefectivePiece,
                                                             self.hash, elementPath, bitmapId)
                                            raise KeyError(f"Defective piece in '{elementPath}': bitmap {bitmapId} not found")
                                        SetShapeBitmapId(cloneShape, elementsMap[bitmapId])

                                    if cloneSprites:
                                        modSwf.symbolClass.addTag(elementsMap[spriteId], spriteAnchor)
                                    else:
                                        SendNotification(NotificationType.CompileModSourcesSpriteEmpty,
                                                         self.hash, spriteAnchor)

                            else:
                                #print(f"Error: Unsupported category '{category}'")
                                SendNotification(NotificationType.CompileModSourcesUnsupportedCategory, self.hash, category)

                # Import previews
                elif folder.startswith("_"):
                    if folder == MODS_SOURCES_CACHE_PREVIEW:
                        for n, preview in enumerate(os.listdir(folderPath)):
                            #print("Import Preview", n)
                            SendNotification(NotificationType.CompileModSourcesImportPreview, self.hash, n)

                            binaryTag = modSwf.importBinaryFile(os.path.join(folderPath, preview))
                            previewFormat = os.path.splitext(preview)[1][1:]
                            self.previewsIds[GetElementId(binaryTag)] = previewFormat

                # Import language .bin patches
                elif folder.lower() == "languages" and os.path.isdir(folderPath):
                    for langFile in os.listdir(folderPath):
                        if not langFile.lower().endswith(".bin"):
                            continue
                        langFilePath = os.path.join(folderPath, langFile)
                        SendNotification(NotificationType.CompileModSourcesImportLangFile,
                                         self.hash, langFile)
                        try:
                            lf = LangFile(langFilePath)
                            if langFile not in self.langFiles:
                                self.langFiles[langFile] = {}
                            for entry in lf.entries:
                                self.langFiles[langFile][entry.key.string] = entry.value.string
                        except Exception as _le:
                            SendNotification(NotificationType.CompileModSourcesGeneralError,
                                             self.hash, str(_le), "")

                # Import images, music
                elif os.path.isdir(folderPath):
                    for path, folders, files in os.walk(folderPath):
                        for file in files:
                            if file in BRAWLHALLA_FILES:
                                #print("Import File", file)
                                SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, file)

                                binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                self.files[GetElementId(binaryTag)] = file

                            else:
                                #print("Error: Unknown file:", file)
                                # Skip language .bin files silently — handled by lang branch
                                if not file.lower().endswith(".bin"):
                                    SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, file)

            try:
                if modSwf.metaData is None:
                    modSwf.addMetadata()
                modSwf.metaData.set(self.getDict())
                modSwf.save()
                modSwf.close()
                # Success move
                if os.path.exists(self.modPath):
                    import time
                    for i in range(5):
                        try:
                            os.remove(self.modPath)
                            break
                        except:
                            time.sleep(0.5)
                os.rename(tempPath, self.modPath)
                from .modloader import ModLoader
                ModLoader.reloadMod(self.modPath)
                SendNotification(NotificationType.CompileModSourcesFinished, self.hash)
            except:
                SendNotification(NotificationType.CompileModSourcesSaveError, self.hash)
        except Exception as e:
            if not isinstance(e, KeyError):
                SendNotification(NotificationType.CompileModSourcesGeneralError, self.hash, str(e), traceback.format_exc())
        finally:
            if modSwf.isOpen():
                modSwf.close()
            if os.path.exists(tempPath):
                try:
                    os.remove(tempPath)
                except:
                    pass

    def delete(self):
        shutil.rmtree(self.modSourcesPath)


class ModsHashSumCache(DataClass):
    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 0, "formatVersion")
    formatVersion: str = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 0, "formatType")
    formatType: str = METADATA_FORMAT_CACHE_MODS_HASH_SUM

    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 1, "hashes")
    hashes: Dict[str, str]  # {hashSum: modHash}

    def __init__(self, modsHashSumCachePath: str):
        self.path = os.path.join(modsHashSumCachePath, METADATA_CACHE_MODS_HASH_SUM_FILE)
        self.loadJsonFile(self.path)

    def save(self):
        self.saveJsonFile(self.path)

    def setHash(self, hashSum: str, modHash: str):
        self.hashes[hashSum] = modHash

    def getHash(self, hashSum) -> Union[str, None]:
        return self.hashes.get(hashSum, None)

    def getHashSum(self, modHash: str) -> Union[str, None]:
        for hashSum, _modHash in self.hashes.items():
            if modHash == _modHash:
                return hashSum

        return None

    def removeHash(self, hashSum: str):
        self.hashes.pop(hashSum)


class ModCache(BaseModClass):
    DataVariable(METADATA_FORMAT_CACHE_MOD, 0, "formatType")
    formatType: str = METADATA_FORMAT_CACHE_MOD

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "hashSum")
    hashSum: str

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "installed")
    installed: bool = False

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "currentVersion")
    currentVersion: bool = True

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "modFileExist")
    modFileExist: bool = True

    modCachePath: str

    def loadCache(self, allowedVars=None, ignoredVars=None):
        if self.modCachePath:
            self.loadJsonFile(os.path.join(self.modCachePath, METADATA_CACHE_MOD_FILE),
                              allowedVars=allowedVars,
                              ignoredVars=ignoredVars)

    def saveCache(self):
        if self.modCachePath:
            self.saveJsonFile(os.path.join(self.modCachePath, METADATA_CACHE_MOD_FILE))


class ModClass(ModCache):
    def __init__(self, modsCachePath: str, modPath: str = None, modHash: str = None, sharedHashCache: ModsHashSumCache = None):
        self.modPath = modPath
        if sharedHashCache is not None:
            self.modsHashSumCache = sharedHashCache
        else:
            self.modsHashSumCache = ModsHashSumCache(modsCachePath)

        if self.modPath is not None and os.path.exists(self.modPath):
            self.modFileExist = True

            self.modSwf = Swf(self.modPath, autoload=False)
            fileStat = os.stat(self.modPath)
            modHashSum = f"{fileStat.st_size}_{fileStat.st_mtime}"

            _cache = False

            if modHash := self.modsHashSumCache.getHash(modHashSum):
                self.modCachePath = os.path.join(modsCachePath, modHash)
                if os.path.exists(self.modCachePath):
                    self.loadCache(ignoredVars=["modFileExist"])
                else:
                    _cache = True
            else:
                _cache = True

            if _cache:

                SendNotification(NotificationType.LoadingMod, modPath)
                SendNotification(NotificationType.LoadingModData, modPath)
                self.loadModData()

                self.hashSum = modHashSum
                self.modCachePath = os.path.join(modsCachePath, self.hash)

                if oldHashSum := self.modsHashSumCache.getHashSum(self.hash):
                    self.modsHashSumCache.removeHash(oldHashSum)
                else:
                    if not os.path.exists(self.modCachePath):
                        os.mkdir(self.modCachePath)

                self.cachePreviews()

                self.modsHashSumCache.setHash(modHashSum, self.hash)
                self.modsHashSumCache.save()

                self.loadCache(allowedVars=["installed"])
        elif modHash is not None:
            self.modFileExist = False
            self.modSwf = None
            self.modCachePath = os.path.join(modsCachePath, modHash)
            self.hash = modHash
            # if modHashSum := self.modsHashSumCache.getHashSum(modHash):
            #    self.modsHashSumCache.removeHash(modHashSum)
            #    self.modsHashSumCache.save()
            if os.path.exists(self.modCachePath):
                self.loadCache(ignoredVars=["modFileExist"])
            else:
                self.removeCache()
                raise Exception("Not found mods cache")
        else:
            SendNotification(NotificationType.LoadingModIsEmpty, None, modPath)

        if BRAWLHALLA_VERSION is not None and BRAWLHALLA_VERSION == self.gameVersion:
            self.currentVersion = True
        else:
            self.currentVersion = False

        if self.modPath is not None:
            self.saveCache()

    def open(self):
        if self.modSwf is not None:
            self.modSwf.open()

    def close(self):
        self.modSwf.close()

    def removeCache(self):
        if modHashSum := self.modsHashSumCache.getHashSum(self.hash):
            self.modsHashSumCache.removeHash(modHashSum)
            self.modsHashSumCache.save()

        shutil.rmtree(self.modCachePath)

    def loadModData(self):
        modOpen = self.modSwf.isOpen()

        if not modOpen:
            self.open()

        self.loadFromJson(self.modSwf.metaData.get(), ignoredVars=["formatType", "hashSum", "installed",
                                                                   "currentVersion", "modFileExist"])

        if not modOpen:
            self.close()

    def cachePreviews(self):
        SendNotification(NotificationType.LoadingModCachePreviews, self.hash)

        modOpen = self.modSwf.isOpen()
        modCachePreviewsPath = os.path.join(self.modCachePath, METADATA_CACHE_MOD_PREVIEWS_FOLDER)

        if not os.path.exists(modCachePreviewsPath):
            os.mkdir(modCachePreviewsPath)

        if not modOpen:
            self.open()

        for file in os.listdir(modCachePreviewsPath):
            os.remove(os.path.join(modCachePreviewsPath, file))

        for n, (elId, previewFormat) in enumerate(self.previewsIds.items()):
            self.modSwf.exportBinaryFile(os.path.join(modCachePreviewsPath, f"preview{n}.{previewFormat}"),
                                         elId=elId)

        if not modOpen:
            self.close()

    def getPreviewsPaths(self) -> List[str]:
        previewsPaths = []

        modCachePreviewsPath = os.path.join(self.modCachePath, METADATA_CACHE_MOD_PREVIEWS_FOLDER)
        if os.path.exists(modCachePreviewsPath):
            for file in os.listdir(modCachePreviewsPath):
                previewsPaths.append(os.path.join(modCachePreviewsPath, file))

        return previewsPaths

    @property
    def date(self) -> float:
        if self.modPath and os.path.exists(self.modPath):
            return os.path.getmtime(self.modPath)
        return 0.0

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        previewsContent = []

        for previewPath in self.getPreviewsPaths():
            previewFormat = os.path.splitext(previewPath)[1][1:]

            with open(previewPath, "rb") as file:
                previewsContent.append((file.read(), previewFormat))

        return previewsContent

    def getElementsCount(self):
        return len(self.files) + len([j for i in self.swfs.values() for n in i.values() for j in n])

    def getModConflict(self) -> List[str]:
        LOCK.acquire(True)
        try:
            if not self.modFileExist or self.modSwf is None:
                SendNotification(NotificationType.FatalError, f"Cannot search conflicts for '{self.name}'. The mod file (.bmod) is missing or corrupt. Please try building the mod again.")
                return []

            SendNotification(NotificationType.ModElementsCount, self.hash, len(self.swfs))

            temp_gameFiles = []
            conflictMods = set(GameFiles.getModConflict(list(self.files.values()), self.hash))
            for swfName, swfMap in self.swfs.items():
                gameFile = GetGameFileClass(swfName)
                if gameFile:
                    gameFile.open()

                    SendNotification(NotificationType.ModConflictSearchInSwf, self.hash, swfName)

                    temp_gameFiles.append(gameFile)

                for category, anchors in swfMap.items():
                    if category in ("sounds", "sprites", "scripts"):
                        conflictAnchors = set(list(anchors)) & set(list(gameFile.modifiedAnchorsMap))

                        for anchor in conflictAnchors:
                            if modHash := gameFile.modifiedAnchorsMap.get(anchor, None):
                                conflictMods.add(modHash)

                        del conflictAnchors

                gameFile.close()

            if conflictMods:
                SendNotification(NotificationType.ModConflict, self.hash, list(conflictMods))
            else:
                del temp_gameFiles
                SendNotification(NotificationType.ModConflictNotFound, self.hash)
                #del conflictMods

            return list(conflictMods)
        except Exception as e:
            SendNotification(NotificationType.FatalError, f"Failed to search for conflicts: {str(e)}\n\n{traceback.format_exc()}")
            return []
        finally:
            LOCK.release()

    def install(self, forceInstallation=False):

        LOCK.acquire(True)
        try:
            if not self.modFileExist or self.modSwf is None:
                SendNotification(NotificationType.FatalError, f"Cannot install mod '{self.name}'. The mod file (.bmod) is missing or corrupt. Please try building the mod again.")
                return

            SendNotification(NotificationType.ModElementsCount, self.hash, self.getElementsCount())

            self.open()

            # Check conflict mods
            if not forceInstallation:
                conflictMods = self.getModConflict()
                if conflictMods:
                    SendNotification(NotificationType.ModConflict, self.hash, list(conflictMods))
                    return conflictMods

            else:
                pass
                #SendNotification(NotificationType.ForceInstallation, self.hash)

            for elId, fileName in self.files.items():
                fileElement = self.modSwf.getElementById(elId)
                if fileElement:
                    fileElement = fileElement[0]
                else:
                    #print(f"Error: Not found element '{[elId]}'", fileElement)
                    SendNotification(NotificationType.InstallingModNotFoundFileElement, self.hash, elId)
                    continue

                GameFiles.installFile(fileName, self.modSwf.exportBinaryData(fileElement), self.hash)

            for swfName, swfMap in self.swfs.items():

                gameFile = GetGameFileClass(swfName)
                gameFile.open()

                if gameFile is None:
                    #print(f"Error: Not found swf '{swfName}'!")
                    SendNotification(NotificationType.InstallingModNotFoundGameSwf, self.hash, swfName)
                    continue

                if self.hash in gameFile.installed:
                    #print(f"Mod '{self.name}' in '{swfName}' is already installed")
                    SendNotification(NotificationType.InstallingModInFileAlreadyInstalled, self.hash, swfName)
                    continue
                else:
                    #print(f"Installing '{self.name}' in '{swfName}'")
                    SendNotification(NotificationType.InstallingModSwf, self.hash, swfName)

                for category, elements in swfMap.items():
                    if category == "scripts":
                        for scriptAnchor, content in elements.items():
                            SendNotification(NotificationType.InstallingModSwfScript, self.hash, scriptAnchor)

                            success = gameFile.importScript(content, scriptAnchor, self.hash)

                            if not success:
                                SendNotification(NotificationType.InstallingModSwfScriptError, self.hash, scriptAnchor)

                    elif category == "sounds":
                        for soundAnchor in elements:
                            #print("Install Sound", soundAnchor)
                            SendNotification(NotificationType.InstallingModSwfSound, self.hash, soundAnchor)

                            soundId = self.modSwf.symbolClass.getTagByName(soundAnchor)
                            if soundId is None:
                                #print(f"Error: Sound {soundAnchor} does not exist")
                                SendNotification(NotificationType.InstallingModSwfSoundSymbolclassNotExist,
                                                 self.hash, soundAnchor, swfName)
                                continue

                            sound = self.modSwf.getElementById(soundId, DefineSoundTag)
                            if sound:
                                sound = sound[0]
                            else:
                                #print(f"Error: Sound {soundId} {soundAnchor} does not exist")
                                SendNotification(NotificationType.InstallingModSoundNotExist,
                                                 self.hash, soundAnchor, soundId, swfName)
                                continue

                            gameFile.importSound(sound, soundAnchor, self.hash)
                    elif category == "sprites":
                        elementsMap = {}
                        for spriteAnchor in elements:
                            #print("Install Sprite", spriteAnchor)
                            SendNotification(NotificationType.InstallingModSwfSprite, self.hash, spriteAnchor)

                            spriteId = self.modSwf.symbolClass.getTagByName(spriteAnchor)
                            if spriteId is None:
                                #print(f"Error: Sprite {spriteAnchor} does not exist")
                                SendNotification(NotificationType.InstallingModSwfSpriteSymbolclassNotExist,
                                                 self.hash, spriteAnchor, swfName)
                                continue

                            sprite = self.modSwf.getElementById(spriteId, DefineSpriteTag)
                            if sprite:
                                sprite = sprite[0]
                            else:
                                #print(f"Error: Sprite {spriteId} {spriteAnchor} does not exist")
                                SendNotification(NotificationType.InstallingModSpriteNotExist,
                                                 self.hash, spriteAnchor, spriteId, swfName)
                                continue

                            gameFile.importSprite(sprite, spriteAnchor, self.hash, elementsMap)

                gameFile.addInstalledMod(self.hash)
                #print(gameFile.getJson(formatJson=True))
                gameFile.save()
                gameFile.close()

            SendNotification(NotificationType.InstallingModFinished, self.hash)

            # ── Install language .bin patches ──────────────────────────────────
            if self.langFiles:
                from .langfiles import LangFiles
                from .brawlhalla import BRAWLHALLA_LANG_FILES
                for bin_name, patches in self.langFiles.items():
                    game_path = BRAWLHALLA_LANG_FILES.get(bin_name)
                    if not game_path or not os.path.exists(game_path):
                        SendNotification(NotificationType.InstallingModNotFoundFileElement,
                                         self.hash, bin_name)
                        continue
                    SendNotification(NotificationType.InstallingModLangFile, self.hash, bin_name)
                    try:
                        lf = LangFile(game_path)
                        for key, new_val in patches.items():
                            orig = lf[key]
                            LangFiles.record_install(bin_name, key,
                                                     orig if orig is not None else "",
                                                     self.hash)
                            lf[key] = new_val
                        lf.Save(game_path)
                    except Exception as _le:
                        SendNotification(NotificationType.FatalError,
                                         f"Lang patch failed for {bin_name}: {_le}")

            self.installed = True
            self.saveCache()

        except Exception as e:
            SendNotification(NotificationType.FatalError, f"Failed to install mod: {str(e)}\n\n{traceback.format_exc()}")
        finally:
            LOCK.release()

    def uninstall(self):
        LOCK.acquire(True)
        try:
            SendNotification(NotificationType.ModElementsCount, self.hash, self.getElementsCount())

            GameFiles.uninstallMod(self.hash)

            # ── Restore language .bin patches ──────────────────────────────────
            if self.langFiles:
                from .langfiles import LangFiles
                from .brawlhalla import BRAWLHALLA_LANG_FILES
                to_restore = LangFiles.uninstall_mod(self.hash)
                for bin_name, keys in to_restore.items():
                    game_path = BRAWLHALLA_LANG_FILES.get(bin_name)
                    if not game_path or not os.path.exists(game_path):
                        continue
                    SendNotification(NotificationType.UninstallingModLangFile,
                                     self.hash, bin_name)
                    try:
                        lf = LangFile(game_path)
                        for key, orig_val in keys.items():
                            lf[key] = orig_val
                        lf.Save(game_path)
                    except Exception as _le:
                        SendNotification(NotificationType.FatalError,
                                         f"Lang restore failed for {bin_name}: {_le}")

            for swfName in self.swfs:
                gameFile = GetGameFileClass(swfName)
                if gameFile is None:
                    continue
                gameFile.open()

                gameFile.uninstallMod(self.hash)

                gameFile.save()
                gameFile.close()

            SendNotification(NotificationType.UninstallingModFinished, self.hash)

            self.installed = False
            self.saveCache()
        except Exception as e:
            SendNotification(NotificationType.FatalError, f"Failed to uninstall mod: {str(e)}\n\n{traceback.format_exc()}")
        finally:
            LOCK.release()

    def reinstall(self):
        self.uninstall()
        self.install()

    def delete(self):
        self.removeCache()
        if self.modPath:
            os.remove(self.modPath)
