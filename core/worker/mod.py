import os
import json
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
                        MODS_SOURCES_CACHE_PREVIEW,
                        MODS_SOURCES_CACHE_REVISION,
                        MODLOADER_MOD_CACHE_REVISION)
from .dataversion import DataClass, DataVariable
from .gameswf import GetGameFileClass, _OBF_ANCHOR, _OBF_SCRIPT_TEMPLATE
from .gamefiles import GameFiles
from .brawlhalla import BRAWLHALLA_SWFS, BRAWLHALLA_FILES, BRAWLHALLA_VERSION
from .basedispatch import SendNotification
from ..notifications import NotificationType

from ..utils.hash import RandomHash, HashFile

from ..swf.swf import (Swf, GetElementId, SetElementId, GetShapeBitmapId,
                       SetShapeBitmapId, GetNeededCharactersId)
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


# ── Obf-script helpers ───────────────────────────────────────────────────────
# Names of script anchors whose files, when found inside a mod-source `scripts/`
# folder (or any subdirectory), declare Obf-type costume→hand mappings.
# Any script whose FFDec anchor ends with one of these names is treated as an
# Obf script and its getHandForCostume() if-blocks are extracted instead of
# storing the full script body.
_OBF_SCRIPT_NAMES = {"Obf", "Obf_2"}

_RE_IF_BLOCKS = re.compile(
    r"getHandForCostume\s*\([^)]*\)\s*:\s*String\s*\{(.*?)\s*return\s+null\s*;",
    re.DOTALL
)
_RE_TARGET_COSTUME = re.compile(
    r"targetCostume\s*\([^)]*\)\s*:\s*String\s*\{\s*return\s+(Obf\.d\s*\([^)]+\)|[^\;]+)\s*;",
    re.DOTALL
)
_RE_SWAP_SUFFIX = re.compile(
    r"swapSuffix\s*\([^)]*\)\s*:\s*String\s*\{\s*return\s+(Obf\.d\s*\([^)]+\)|[^\;]+)\s*;",
    re.DOTALL
)
_RE_FAMILIES = re.compile(
    r"families\s*\([^)]*\)\s*:\s*Array\s*\{\s*return\s*\[\s*(Obf\.d\s*\([^)]+\)|[^\,\;\]]+)",
    re.DOTALL
)


def _extract_obf_if_blocks(as3_content: str) -> str:
    """Extract all handMap, colorMap, and paletteMap mapping statements from Obf.as."""
    statements = []
    pattern = re.compile(r'((?:handMap|colorMap|paletteMap)\s*\[[^\]]+\]\s*=\s*[^;]+;)', re.DOTALL)
    for m in pattern.finditer(as3_content):
        stmt = m.group(1).strip()
        if stmt:
            statements.append(stmt)
    if statements:
        return "\n\n".join(statements)

    # 2. Legacy fallback for old if-statement blocks in getHandForCostume
    if_matches = re.findall(
        r'if\s*\(\s*costumeName\s*==\s*([^)]+)\)\s*(?:\{\s*return\s+([^;]+);\s*\}|return\s+([^;]+);)',
        as3_content
    )
    if if_matches:
        lines = []
        for m in if_matches:
            c_expr = m[0].strip()
            s_expr = (m[1] or m[2]).strip()
            lines.append(f'handMap[{c_expr}] = {s_expr};')
        if lines:
            return "\n".join(lines)

    # 3. Fallback to targetCostume() and swapSuffix() / families()
    m_costume = _RE_TARGET_COSTUME.search(as3_content)
    m_suffix = _RE_SWAP_SUFFIX.search(as3_content)
    if not m_suffix:
        m_suffix = _RE_FAMILIES.search(as3_content)

    if m_costume and m_suffix:
        c_expr = m_costume.group(1).strip()
        s_expr = m_suffix.group(1).strip()
        if c_expr not in ('""', "''", "null") and s_expr not in ('""', "''", "null"):
            return f'handMap[{c_expr}] = {s_expr};'

    return ""


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

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "bmtCertified")
    bmtCertified: bool = False

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "bmtCert")
    bmtCert: dict = {}

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "creatorCertified")
    creatorCertified: bool = False

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
        cached_data = {}
        if os.path.exists(self.cachePath):
            try:
                with open(self.cachePath, "r", encoding="utf-8") as cache_file:
                    cached_data = json.load(cache_file)
            except (OSError, ValueError, TypeError):
                cached_data = {}

        loaded = self.loadJsonFile(self.cachePath, ignoredVars=["formatVersion", "swfs", "files", "previewsIds"])

        # Check for BMT certificate in mod source
        cert_path = os.path.join(self.modSourcesPath, ".bmt_cert.json")
        if os.path.exists(cert_path):
            try:
                with open(cert_path, "r", encoding="utf-8") as cf:
                    cdata = json.load(cf)
                self.bmtCertified = True
                self.bmtCert = cdata
            except Exception:
                pass

        if not loaded:
            #print(f"New mod source '{self.folderName}' detected")
            if not self.author:
                self.author = self.DEFAULT_AUTHOR
            if not self.gameVersion:
                self.gameVersion = self.DEFAULT_GAME_VERSION
            if not self.version:
                self.version = self.DEFAULT_VERSION
        try:
            cache_revision = int(cached_data.get("sourceCacheRevision", 0))
        except (TypeError, ValueError):
            cache_revision = 0

        source_stamp = self._sourceInventoryStamp()
        cached_swfs = cached_data.get("swfs", {})
        if (loaded and cache_revision >= MODS_SOURCES_CACHE_REVISION and
                isinstance(cached_swfs, dict) and
                cached_data.get("sourceInventoryStamp") == source_stamp):
            # The inventory describes names, not frame contents.  Editing a
            # frames.swf therefore still builds from disk, but merely opening
            # the Creator does not crawl every file in every source anymore.
            self.swfs = cached_swfs
            self._sourceCacheNeedsMigration = False
            return

        scanned_swfs = self.scanSourceInventory()
        cached_inventory = self._inventorySignature(cached_swfs)
        scanned_inventory = self._inventorySignature(scanned_swfs)
        self.swfs = scanned_swfs

        if (not loaded or
                cache_revision < MODS_SOURCES_CACHE_REVISION or
                cached_inventory != scanned_inventory):
            self._sourceCacheNeedsMigration = True
            if not loaded:
                self.saveModData()
        else:
            self._sourceCacheNeedsMigration = False

    def _sourceInventoryStamp(self):
        """Return a cheap stamp for directories that can change inventory."""
        stamp = []
        known_swfs = {name.lower() for name in BRAWLHALLA_SWFS}
        try:
            source_entries = os.scandir(self.modSourcesPath)
        except OSError:
            return stamp

        with source_entries:
            for entry in source_entries:
                if not entry.is_dir() or not entry.name.lower().endswith(".swf"):
                    continue
                if entry.name.lower() not in known_swfs:
                    continue
                for category in ("sprites", "sounds", "scripts"):
                    category_path = os.path.join(entry.path, category)
                    try:
                        stat = os.stat(category_path)
                        stamp.append([entry.name.lower(), category, stat.st_mtime_ns])
                    except OSError:
                        stamp.append([entry.name.lower(), category, None])
        return stamp

    @staticmethod
    def _inventorySignature(swfs):
        signature = {}
        if not isinstance(swfs, dict):
            return signature

        for swf_name, swf_data in swfs.items():
            if not isinstance(swf_data, dict):
                continue
            signature[swf_name] = {
                "sprites": sorted(set(swf_data.get("sprites", []) or [])),
                "sounds": sorted(set(swf_data.get("sounds", []) or []))
            }
        return signature

    def scanSourceInventory(self):
        """Build source metadata from disk without opening or rewriting any SWF."""
        inventory = {}
        known_swfs = {name.lower(): name for name in BRAWLHALLA_SWFS}

        try:
            source_entries = sorted(os.listdir(self.modSourcesPath), key=str.lower)
        except OSError:
            return inventory

        for folder in source_entries:
            folder_path = os.path.join(self.modSourcesPath, folder)
            if not os.path.isdir(folder_path) or not folder.lower().endswith(".swf"):
                continue

            game_swf_name = known_swfs.get(folder.lower())
            if game_swf_name is None:
                continue

            swf_data = {"scripts": {}, "sounds": [], "sprites": [], "obfMappings": {}}

            sprites_path = os.path.join(folder_path, "sprites")
            if os.path.isdir(sprites_path):
                for entry in sorted(os.listdir(sprites_path), key=str.lower):
                    entry_path = os.path.join(sprites_path, entry)
                    match = self.regexSpriteFile.fullmatch(entry)
                    if os.path.isdir(entry_path) and match and match.group(2):
                        swf_data["sprites"].append(match.group(2))

            sounds_path = os.path.join(folder_path, "sounds")
            if os.path.isdir(sounds_path):
                for entry in sorted(os.listdir(sounds_path), key=str.lower):
                    match = self.regexSoundFile.match(entry)
                    if match:
                        swf_data["sounds"].append(match.group(1))

            scripts_path = os.path.join(folder_path, "scripts")
            if os.path.isdir(scripts_path):
                for script_root, _, script_files in os.walk(scripts_path):
                    for entry in sorted(script_files, key=str.lower):
                        if not self.regexAsFile.fullmatch(entry):
                            continue
                        relative = os.path.relpath(os.path.join(script_root, entry), scripts_path)
                        anchor = os.path.splitext(relative)[0].replace(os.sep, "/")
                        swf_data["scripts"][anchor] = ""

            inventory[game_swf_name] = swf_data

        return inventory

    def saveModData(self):
        if not self.hash:
            self.hash = RandomHash()

        data = self.getDict()
        data["sourceCacheRevision"] = MODS_SOURCES_CACHE_REVISION
        data["sourceInventoryStamp"] = self._sourceInventoryStamp()
        temp_path = self.cachePath + f".{threading.get_ident()}.tmp"
        source_stat = os.stat(self.modSourcesPath)
        with open(temp_path, "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file)
        os.replace(temp_path, self.cachePath)
        # _cache.json is derived data; it must not alter the date used to
        # organize the user's source folders.
        os.utime(self.modSourcesPath, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

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

                # Selecting/loading an existing preview must not rewrite it and
                # change the source folder's modification date.
                if os.path.normcase(os.path.abspath(previewPath)) == \
                        os.path.normcase(os.path.abspath(cachePreviewPath)):
                    if cachePreviewPath in removePreviewPath:
                        removePreviewPath.remove(cachePreviewPath)
                    continue

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
            meaningful_dates = []
            for root, _, files in os.walk(self.modSourcesPath):
                for file_name in files:
                    path = os.path.join(root, file_name)
                    if file_name == MODS_SOURCES_CACHE_FILE:
                        continue
                    try:
                        if file_name == "frames.swf" and os.path.getsize(path) <= 31:
                            continue
                        meaningful_dates.append(os.path.getctime(path))
                    except OSError:
                        continue
            if meaningful_dates:
                return max(meaningful_dates)
            return os.path.getctime(self.modSourcesPath)
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
        # This value is only a progress estimate.  Walking every nested source
        # file here caused large legacy mods to spend most of their build time
        # counting files before compiling anything.
        if not isinstance(self.swfs, dict):
            self.swfs = self.scanSourceInventory()

        count = len(self.getPreviewsPaths())
        for swf_data in self.swfs.values():
            if not isinstance(swf_data, dict):
                continue
            count += len(swf_data.get("sprites", []) or [])
            count += len(swf_data.get("sounds", []) or [])
            count += len(swf_data.get("scripts", {}) or {})
        return max(1, count)

    @staticmethod
    def _formatBuildDuration(elapsed):
        if elapsed < 60:
            return f"{elapsed:.2f} seconds"
        minutes, seconds = divmod(elapsed, 60)
        if minutes < 60:
            return f"{int(minutes)}m {seconds:.2f}s"
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)}h {int(minutes)}m {seconds:.2f}s"

    def _finishCompilation(self, tempPath, buildStarted, buildTimings):
        """Atomically publish a successful build and refresh its lightweight cache."""
        phaseStarted = time.perf_counter()
        if os.path.exists(self.modPath):
            for _ in range(5):
                try:
                    os.remove(self.modPath)
                    break
                except OSError:
                    time.sleep(0.5)
        os.rename(tempPath, self.modPath)
        self.saveModData()
        buildTimings["publish"] = time.perf_counter() - phaseStarted

        phaseStarted = time.perf_counter()
        if self._needsRelink():
            try:
                from ..utils.carrier_relinker import relink_mod_file
                from .brawlhalla import BRAWLHALLA_PATH
                relink_mod_file(self.modPath, BRAWLHALLA_PATH)
            except Exception as error:
                print(f"[ModCreator] Auto-relink variables warning: {error}")
        buildTimings["relink"] = time.perf_counter() - phaseStarted

        phaseStarted = time.perf_counter()
        from .modloader import ModLoader
        ModLoader.reloadMod(self.modPath)
        buildTimings["reload_cache"] = time.perf_counter() - phaseStarted

        elapsed = time.perf_counter() - buildStarted
        duration = self._formatBuildDuration(elapsed)
        timingDetails = ", ".join(
            f"{name}={seconds:.2f}s"
            for name, seconds in buildTimings.items()
            if seconds >= 0.01
        )
        message = f"Build completed in {duration}."
        print(f"[ModCompiler] {message}", flush=True)
        if timingDetails:
            print(f"[ModCompiler] Timings: {timingDetails}", flush=True)
        SendNotification(NotificationType.CompileModSourcesFinished,
                         self.hash, elapsed, message)

    def _needsRelink(self):
        """Conservative check: every script-bearing bmod keeps old behavior."""
        if not isinstance(self.swfs, dict):
            return True
        for swf_data in self.swfs.values():
            if not isinstance(swf_data, dict):
                return True
            if swf_data.get("scripts") or swf_data.get("obfMappings"):
                return True
        return False

    def compile(self):
        buildStarted = time.perf_counter()
        buildTimings = {
            "inventory": 0.0,
            "load_sprites": 0.0,
            "prepare_tags": 0.0,
            "clone_tags": 0.0,
            "repair_refs": 0.0,
            "close_sprites": 0.0,
            "ffdec_save": 0.0,
        }
        phaseStarted = time.perf_counter()
        elementsCount = self.getElementsCount()
        buildTimings["inventory"] = time.perf_counter() - phaseStarted
        SendNotification(NotificationType.CompileElementsCount, self.hash, elementsCount)

        tempPath = self.modPath + ".tmp"
        if os.path.exists(tempPath):
            try:
                os.remove(tempPath)
            except:
                pass

        modSwf = Swf(tempPath)
        if modSwf.metaData is None:
            modSwf.addMetadata()
        bulkAddEnabled = modSwf.beginBulkAdd()
        print(
            "[ModCompiler] Fast bulk SWF assembly enabled."
            if bulkAddEnabled else
            "[ModCompiler] Bulk SWF assembly unavailable; using compatibility mode.",
            flush=True,
        )
        self.swfs = {}
        self.previewsIds = {}
        self.files = {}
        self.langFiles = {}
        recoverySwfs = {}
        recoveredSprites = {}

        recovery_paths = []
        if os.path.isfile(self.modPath):
            recovery_paths.append(self.modPath)
        mods_root = os.path.dirname(os.path.dirname(self.modPath))
        backup_mod = os.path.join(mods_root, "Backup", "Mods", os.path.basename(self.modPath))
        if os.path.isfile(backup_mod) and backup_mod not in recovery_paths:
            recovery_paths.append(backup_mod)

        def recoverSprite(sprite_anchor):
            """Load an old source sprite from an existing compiled mod."""
            cached_sprite = recoveredSprites.get(sprite_anchor)
            if cached_sprite is not None:
                return cached_sprite
            for recovery_path in recovery_paths:
                try:
                    recovery_swf = recoverySwfs.get(recovery_path)
                    if recovery_swf is None:
                        recovery_swf = Swf(recovery_path)
                        recoverySwfs[recovery_path] = recovery_swf
                    sprite_id = recovery_swf.symbolClass.getTagByName(sprite_anchor)
                    if sprite_id is None:
                        continue
                    sprites = recovery_swf.getElementById(int(sprite_id), DefineSpriteTag)
                    if not sprites:
                        continue
                    sprite_element = sprites[0]
                    elements = []
                    for element_id in GetNeededCharactersId(sprite_element):
                        for element in recovery_swf.getElementById(element_id):
                            if not isinstance(element, (CSMTextSettingsTag,
                                                        DefineFontAlignZonesTag,
                                                        DefineFontNameTag)):
                                elements.append(element)
                    elements.append(sprite_element)
                    elements = list({
                        GetElementId(element): element for element in elements
                        if GetElementId(element) is not None
                    }.values())
                    recoveredSprites[sprite_anchor] = (recovery_swf, sprite_element, elements)
                    return recoveredSprites[sprite_anchor]
                except Exception:
                    continue
            return None

        try:
            for folder in os.listdir(self.modSourcesPath):
                folderPath = os.path.join(self.modSourcesPath, folder)

                if os.path.isfile(folderPath):
                    continue

                # Import game elements
                swf_target = None
                if folder.endswith(".swf"):
                    if folder in BRAWLHALLA_SWFS:
                        swf_target = folder
                    else:
                        f_lower = folder.lower()
                        for k in BRAWLHALLA_SWFS:
                            if k.lower() == f_lower:
                                swf_target = k
                                break

                if swf_target:
                    gameSwfName: str = swf_target
                    elementsMap = {}
                    self.swfs[gameSwfName] = {}
                    self.swfs[gameSwfName]["scripts"] = {}
                    self.swfs[gameSwfName]["sounds"] = []
                    self.swfs[gameSwfName]["sprites"] = []
                    self.swfs[gameSwfName]["obfMappings"] = {}

                    for category in os.listdir(folderPath):
                        categoryPath = os.path.join(folderPath, category)
                        seen_sprite_ids = {}
                        seen_internal_sprite_ids = {}

                        # Support loose root .as files
                        if os.path.isfile(categoryPath) and category.endswith(".as"):
                            scriptBaseName = os.path.splitext(category)[0]
                            scriptAnchor = scriptBaseName
                            with open(categoryPath, "r", encoding="utf-8", errors="replace") as actionScript:
                                scriptContent = actionScript.read()

                            if_blocks = _extract_obf_if_blocks(scriptContent)
                            if if_blocks:
                                existing = self.swfs[gameSwfName]["obfMappings"].get(scriptAnchor, "")
                                self.swfs[gameSwfName]["obfMappings"][scriptAnchor] = (existing + "\n" + if_blocks) if existing else if_blocks
                                continue

                            SendNotification(NotificationType.CompileModSourcesImportActionScripts, self.hash, scriptAnchor)
                            self.swfs[gameSwfName]["scripts"][scriptAnchor] = scriptContent
                            continue

                        if category == "scripts":
                            # Walk recursively so subdirs like tier_b/ are included.
                            for script_root, _, script_files in os.walk(categoryPath):
                                for elementPath in script_files:
                                    if not self.regexAsFile.findall(elementPath):
                                        continue
                                    scriptBaseName = os.path.splitext(elementPath)[0]

                                    # Build the anchor: relative dir from scripts/ root
                                    rel_dir = os.path.relpath(script_root, categoryPath)
                                    if rel_dir == ".":
                                        scriptAnchor = scriptBaseName
                                    else:
                                        scriptAnchor = rel_dir.replace(os.sep, "/") + "/" + scriptBaseName

                                    fullScriptPath = os.path.join(script_root, elementPath)

                                    with open(fullScriptPath, "r", encoding="utf-8", errors="replace") as actionScript:
                                        scriptContent = actionScript.read()

                                    # 1. If script contains getHandForCostume(), extract the costume mapping
                                    if_blocks = _extract_obf_if_blocks(scriptContent)
                                    if if_blocks:
                                        SendNotification(
                                            NotificationType.CompileModSourcesImportObfMappings,
                                            self.hash, scriptAnchor)
                                        existing = self.swfs[gameSwfName]["obfMappings"].get(scriptAnchor, "")
                                        if existing:
                                            self.swfs[gameSwfName]["obfMappings"][scriptAnchor] = (
                                                existing + "\n" + if_blocks
                                            )
                                        else:
                                            self.swfs[gameSwfName]["obfMappings"][scriptAnchor] = if_blocks
                                        # Do NOT add as loose script — merged into a_ScreenMainMenu2
                                        continue

                                    # 2. For UI_MainMenu.swf, skip carrier-only support scripts
                                    # (they are bundled dynamically inside a_ScreenMainMenu2)
                                    _carrier_names = {
                                        "brawlforgesuite", "brawlforgesuite_2",
                                        "brawlforgesuitebootstrap", "brawlforgesuitebootstrap_2",
                                        "obf", "obf_2",
                                        "a_battlepasssplashartbutton", "a_mainmenu_hotkeybar", "a_mainmenu_hotkeybar_xb1"
                                    }
                                    if gameSwfName.lower() == "ui_mainmenu.swf":
                                        if scriptBaseName.lower() in _carrier_names:
                                            continue
                                        # Skip carrier stub a_ScreenMainMenu2 (handled dynamically)
                                        if scriptBaseName.lower() == "a_screenmainmenu2" and ("BrawlForgeSuite" in scriptContent or "attach(" in scriptContent):
                                            continue

                                    SendNotification(
                                        NotificationType.CompileModSourcesImportActionScripts,
                                        self.hash, scriptAnchor)
                                    self.swfs[gameSwfName]["scripts"][scriptAnchor] = scriptContent
                            continue  # skip the old per-file loop below for "scripts"

                        for elementPath in os.listdir(categoryPath):
                            if category == "sounds":
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

                                    if not spriteAnchor:
                                        SendNotification(NotificationType.CompileModSourcesSpriteHasNoSymbolclass,
                                                         self.hash, elementPath)
                                        continue

                                    SendNotification(NotificationType.CompileModSourcesImportSprite,
                                                     self.hash, spriteAnchor)

                                    frames_path = os.path.join(categoryPath, elementPath, "frames.swf")
                                    spriteSwf = None
                                    spriteElements = None
                                    localSpriteSwf = False
                                    spriteElement = None
                                    spriteId = 0

                                    # Never instantiate Swf for a missing path: Swf would create
                                    # an empty 31-byte file inside the user's old source.
                                    phaseStarted = time.perf_counter()
                                    if os.path.isfile(frames_path) and os.path.getsize(frames_path) > 31:
                                        try:
                                            spriteSwf = Swf(frames_path)
                                            localSpriteSwf = True
                                            for element in spriteSwf.elementsList[::-1]:
                                                if isinstance(element, DefineSpriteTag):
                                                    spriteElement = element
                                                    spriteId = GetElementId(element)
                                                    spriteElements = spriteSwf.elementsList
                                                    break
                                        except Exception:
                                            if spriteSwf is not None and spriteSwf.isOpen():
                                                spriteSwf.close(clearGlobalCaches=False)
                                            spriteSwf = None
                                            localSpriteSwf = False

                                    if spriteElement is None:
                                        recovered = recoverSprite(spriteAnchor)
                                        if recovered is None:
                                            raise RuntimeError(
                                                f"Cannot recover legacy sprite '{spriteAnchor}'. "
                                                "Its source has no valid frames.swf and it was not found "
                                                "in the existing or backup .bmod. Build stopped without "
                                                "overwriting the current mod.")
                                        spriteSwf, spriteElement, spriteElements = recovered
                                        spriteId = GetElementId(spriteElement)
                                    buildTimings["load_sprites"] += time.perf_counter() - phaseStarted

                                    self.swfs[gameSwfName]["sprites"].append(spriteAnchor)

                                    if spriteId in seen_internal_sprite_ids:
                                        SendNotification(NotificationType.CompileModSourcesDuplicateSpriteId,
                                                         self.hash, str(spriteId), elementPath, seen_internal_sprite_ids[spriteId])
                                        raise KeyError(f"Duplicate internal sprite ID {spriteId} detected between '{elementPath}' and '{seen_internal_sprite_ids[spriteId]}'")
                                    
                                    seen_internal_sprite_ids[spriteId] = elementPath

                                    cloneSprites = []
                                    cloneShapes = []

                                    # Read each Java tag ID once.  GetElementId
                                    # crosses JPype for most tag types.
                                    phaseStarted = time.perf_counter()
                                    elementRecords = [
                                        (element_id, element)
                                        for element in spriteElements
                                        if (element_id := GetElementId(element)) is not None
                                    ]
                                    elementRecords.sort(key=lambda item: item[0])
                                    buildTimings["prepare_tags"] += time.perf_counter() - phaseStarted

                                    phaseStarted = time.perf_counter()
                                    for originalElementId, element in elementRecords:
                                        if not isinstance(element,
                                                          (CSMTextSettingsTag, DefineFontNameTag,
                                                           DefineFontAlignZonesTag, PlaceObject2Tag)):

                                            if originalElementId in elementsMap:
                                                if element == spriteElement:
                                                    for mappedElementId, _element in elementRecords:
                                                        if isinstance(_element, (*DefineShapeTags, DefineEditTextTag,
                                                                                  DefineSpriteTag,
                                                                                  *DefineBitsLosslessTags)) or \
                                                                element == spriteElement:

                                                            elementsMap.pop(mappedElementId, None)
                                                else:
                                                    continue

                                            newElId = modSwf.getNextCharacterId()
                                            cloneEl = modSwf.cloneAndAddElement(element, newElId)
                                            elementsMap[originalElementId] = newElId

                                            if isinstance(cloneEl, DefineShapeTags):
                                                if GetShapeBitmapId(cloneEl) is not None:
                                                    cloneShapes.append(cloneEl)

                                            elif isinstance(cloneEl, DefineSpriteTag):
                                                cloneSprites.append(cloneEl)

                                            elif isinstance(element, DefineFontTags):
                                                for dependentElement in spriteSwf.getElementById(originalElementId,
                                                                                                 (DefineFontNameTag,
                                                                                                  DefineFontAlignZonesTag)):
                                                    modSwf.cloneAndAddElement(dependentElement, newElId)

                                            elif isinstance(element, DefineEditTextTag):
                                                if dependentElement := spriteSwf.getElementById(originalElementId,
                                                                                                CSMTextSettingsTag):
                                                    modSwf.cloneAndAddElement(dependentElement[0], newElId)
                                                cloneEl.fontId = elementsMap[element.fontId]

                                            elif isinstance(element, DefineTextTag):
                                                if dependentElement := spriteSwf.getElementById(originalElementId,
                                                                                                CSMTextSettingsTag):
                                                    modSwf.cloneAndAddElement(dependentElement[0], newElId)

                                                for textRecord in cloneEl.textRecords:
                                                    if textRecord.styleFlagsHasFont:
                                                        textRecord.fontId = elementsMap[textRecord.fontId]
                                    buildTimings["clone_tags"] += time.perf_counter() - phaseStarted

                                    phaseStarted = time.perf_counter()
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
                                    buildTimings["repair_refs"] += time.perf_counter() - phaseStarted

                                    if cloneSprites:
                                        modSwf.symbolClass.addTag(elementsMap[spriteId], spriteAnchor)
                                    else:
                                        raise RuntimeError(
                                            f"Sprite '{spriteAnchor}' contains no usable DefineSprite data. "
                                            "Build stopped without overwriting the current mod.")

                                    if localSpriteSwf and spriteSwf.isOpen():
                                        phaseStarted = time.perf_counter()
                                        # clearAllCache() also clears FFDec's
                                        # global/static caches. Doing that for
                                        # every frames.swf dominates builds
                                        # with 1000+ sprites. The output SWF
                                        # performs the global cleanup once at
                                        # the end of the complete build.
                                        spriteSwf.close(clearGlobalCaches=False)
                                        buildTimings["close_sprites"] += time.perf_counter() - phaseStarted

                            else:
                                #print(f"Error: Unsupported category '{category}'")
                                SendNotification(NotificationType.CompileModSourcesUnsupportedCategory, self.hash, category)

                    # Backward compatibility: for older ModLoaders that don't know about
                    # obfMappings, provide the full self-contained carrier script under
                    # scripts['a_ScreenMainMenu2'] so the mod installs fine on older loaders.
                    if self.swfs[gameSwfName].get("obfMappings"):
                        combined = "\n".join(
                            "         " + l.strip()
                            for blocks in self.swfs[gameSwfName]["obfMappings"].values()
                            for l in blocks.splitlines() if l.strip()
                        )
                        m_costume = re.findall(r'handMap\[([^\]]+)\]', combined)
                        m_suffix = re.findall(r'handMap\[[^\]]+\]\s*=\s*([^;]+);', combined)
                        target_costume_expr = m_costume[-1].strip() if m_costume else '"LuchadorFiona"'
                        target_suffix_expr = m_suffix[-1].strip() if m_suffix else '"Bare"'
                        families_expr = "[" + ",".join([target_suffix_expr] * 25) + "]"

                        self.swfs[gameSwfName]["scripts"]["a_ScreenMainMenu2"] = (
                            _OBF_SCRIPT_TEMPLATE
                            .replace("{INIT_MAP_LINES}", combined)
                            .replace("{TARGET_COSTUME}", target_costume_expr)
                            .replace("{SWAP_SUFFIX}", target_suffix_expr)
                            .replace("{FAMILIES}", families_expr)
                        )

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
                            target_file = None
                            if file in BRAWLHALLA_FILES:
                                target_file = file
                            else:
                                file_lower = file.lower()
                                for k in BRAWLHALLA_FILES:
                                    if k.lower() == file_lower:
                                        target_file = k
                                        break

                            if target_file:
                                SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, target_file)

                                binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                self.files[GetElementId(binaryTag)] = target_file
                            else:
                                # Skip language .bin files silently — handled by lang branch
                                if not file.lower().endswith(".bin"):
                                    SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, file)

            try:
                self.creatorCertified = True
                mod_meta = self.getDict()
                mod_meta["creatorCertified"] = True

                # Check for BMT certificate in mod source
                cert_file = os.path.join(self.modSourcesPath, ".bmt_cert.json")
                if os.path.exists(cert_file):
                    try:
                        with open(cert_file, "r", encoding="utf-8") as cf:
                            cdata = json.load(cf)
                        try:
                            from ui.utils.security_scanner import verify_bmt_certificate
                        except Exception:
                            from pathlib import Path
                            import sys
                            p_utils = Path(__file__).parent.parent.parent.parent / "BrawlhallaModLoader" / "ui" / "utils"
                            if str(p_utils) not in sys.path:
                                sys.path.insert(0, str(p_utils))
                            from security_scanner import verify_bmt_certificate

                        from pathlib import Path
                        v_ok, _ = verify_bmt_certificate(cdata, Path(self.modSourcesPath))
                        if v_ok:
                            self.bmtCertified = True
                            self.bmtCert = cdata
                            mod_meta["bmtCertified"] = True
                            mod_meta["bmtCert"] = cdata
                    except Exception as ce:
                        print(f"[ModCompiler] Error reading BMT certificate: {ce}")

                if modSwf.metaData is None:
                    modSwf.addMetadata()
                modSwf.metaData.set(mod_meta)
                phaseStarted = time.perf_counter()
                modSwf.save()
                buildTimings["ffdec_save"] = time.perf_counter() - phaseStarted
                modSwf.close()
                self._finishCompilation(tempPath, buildStarted, buildTimings)
            except:
                SendNotification(NotificationType.CompileModSourcesSaveError, self.hash)
        except Exception as e:
            if not isinstance(e, KeyError):
                SendNotification(NotificationType.CompileModSourcesGeneralError, self.hash, str(e), traceback.format_exc())
        finally:
            for recoverySwf in recoverySwfs.values():
                if recoverySwf.isOpen():
                    recoverySwf.close()
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

    DataVariable(METADATA_FORMAT_CACHE_MOD, 2, "cacheRevision")
    # Zero marks caches written before explicit cache versioning.
    cacheRevision: int = 0

    modCachePath: str

    def isCacheCurrent(self):
        if not self.modCachePath:
            return False
        cache_path = os.path.join(self.modCachePath, METADATA_CACHE_MOD_FILE)
        try:
            with open(cache_path, "r", encoding="utf-8") as cache_file:
                data = json.load(cache_file)
            revision = int(data.get("cacheRevision", 0))
            return (
                revision >= MODLOADER_MOD_CACHE_REVISION and
                isinstance(data.get("hash"), str) and bool(data["hash"]) and
                isinstance(data.get("swfs"), dict) and
                isinstance(data.get("files"), dict) and
                isinstance(data.get("previewsIds"), dict)
            )
        except (OSError, ValueError, TypeError, KeyError):
            return False

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
                    cache_is_current = self.isCacheCurrent()
                    self.loadCache(ignoredVars=["modFileExist"])
                    if not cache_is_current:
                        installed = self.installed
                        SendNotification(NotificationType.LoadingMod, modPath)
                        SendNotification(NotificationType.LoadingModData, modPath)
                        self.loadModData()
                        self.installed = installed
                        self.hashSum = modHashSum
                        self.cacheRevision = MODLOADER_MOD_CACHE_REVISION
                else:
                    _cache = True
            else:
                _cache = True

            if _cache:

                SendNotification(NotificationType.LoadingMod, modPath)
                SendNotification(NotificationType.LoadingModData, modPath)
                self.loadModData()

                self.hashSum = modHashSum
                self.cacheRevision = MODLOADER_MOD_CACHE_REVISION
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

            # Color mod validation check temporarily disabled by user request
            # for swf_name, swf_map in self.swfs.items():
            #     if "ui_mainmenu" in str(swf_name).lower():
            #         ...

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

                # Legacy compatibility: if an older mod has a_ScreenMainMenu2 with getHandForCostume
                # but no obfMappings, extract them on the fly so it merges seamlessly with other mods.
                has_obf = bool(swfMap.get("obfMappings"))
                if not has_obf and swfName.lower() == "ui_mainmenu.swf":
                    legacy_script = swfMap.get("scripts", {}).get("a_ScreenMainMenu2", "")
                    if legacy_script:
                        extracted = _extract_obf_if_blocks(legacy_script)
                        if extracted:
                            swfMap["obfMappings"] = {"a_ScreenMainMenu2": extracted}
                            has_obf = True

                for category, elements in swfMap.items():
                    if category == "scripts":
                        for scriptAnchor, content in elements.items():
                            # When dynamic carrier / obfMappings are active for UI_MainMenu,
                            # Obf and related carrier scripts are handled via importObfMappings,
                            # not verbatim importScript.
                            if has_obf and scriptAnchor.lower() in ("obf", "tier_b/obf", "tier_b.obf", "a_screenmainmenu2"):
                                continue

                            SendNotification(NotificationType.InstallingModSwfScript, self.hash, scriptAnchor)

                            success = gameFile.importScript(content, scriptAnchor, self.hash)

                            if not success:
                                SendNotification(NotificationType.InstallingModSwfScriptError, self.hash, scriptAnchor)

                    elif category == "obfMappings":
                        # Each key is a scriptAnchor (e.g. "tier_b/Obf"), but all Obf
                        # entries for this SWF get merged into _OBF_ANCHOR (a_ScreenMainMenu2).
                        combined_if_blocks = ""
                        for _anchor, if_blocks in elements.items():
                            if if_blocks:
                                if combined_if_blocks:
                                    combined_if_blocks += "\n"
                                combined_if_blocks += if_blocks

                        if combined_if_blocks:
                            SendNotification(NotificationType.InstallingModSwfObfMappings, self.hash, swfName)
                            gameFile.importObfMappings(combined_if_blocks, self.hash)

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
