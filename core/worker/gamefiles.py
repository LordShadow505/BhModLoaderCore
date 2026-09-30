import hashlib
import os
from typing import Dict, List

from .dataversion import DataClass, DataVariable
from .variables import (DATA_FORMAT_MODLOADER_FILES,
                        DATA_FORMAT_MODLOADER_VERSION,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_FILES_FILE,
                        MODLOADER_CACHE_FILES_FOLDER)
from .brawlhalla import (
    BRAWLHALLA_FILES,
    BRAWLHALLA_LANG_FILES,
    refresh_brawlhalla_file_index,
)
from .basedispatch import SendNotification

from ..utils.hash import HashFile, HashFromBytes
from ..notifications import NotificationType


class GameFilesData(DataClass):
    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "formatVersion")
    formatVersion: int = DATA_FORMAT_MODLOADER_VERSION

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "formatType")
    formatType: str = DATA_FORMAT_MODLOADER_FILES

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "origFiles")
    origFiles: Dict[str, str]   # {fileName: origFIleHash}

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "modFiles")
    modFiles: Dict[str, str]    # {fileName: fileHash}

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "modifiedFilesMap")
    modifiedFilesMap: Dict[str, str]    # {fileName: modHash}

    # Sound mods may share a BNK/WEM container.  Keep the previous mod layers
    # so removing the top layer restores the next sound mod instead of the
    # original bank prematurely.
    DataVariable(DATA_FORMAT_MODLOADER_FILES, 1, "soundFileStacks")
    soundFileStacks: Dict[str, List[dict]]

    def loadData(self):
        self.loadJsonFile(os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FILE))

    def saveData(self):
        self.saveJsonFile(os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FILE))


class GameFilesClass(GameFilesData):
    def __init__(self):
        self.loadData()
        self.origPreviewsPath = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FOLDER)

        if not os.path.exists(self.origPreviewsPath):
            os.mkdir(self.origPreviewsPath)

    @staticmethod
    def _resolve_target_path(fileName: str):
        """Resolve a game asset by name, refreshing the index if needed."""
        targetPath = BRAWLHALLA_FILES.get(fileName)
        if targetPath and os.path.exists(targetPath):
            return targetPath, fileName

        fn_lower = str(fileName).casefold()
        for key, value in BRAWLHALLA_FILES.items():
            if key.casefold() == fn_lower and os.path.exists(value):
                return value, key

        # Legacy EX mods store complete language.*.bin replacements in the
        # generic binary-file map.  Keep the dedicated language index as a
        # direct fallback as well, so those files work even if the broad game
        # scan was performed before the language directory became available.
        targetPath = BRAWLHALLA_LANG_FILES.get(fileName)
        if targetPath and os.path.exists(targetPath):
            return targetPath, fileName
        for key, value in BRAWLHALLA_LANG_FILES.items():
            if key.casefold() == fn_lower and os.path.exists(value):
                return value, key

        # The game directory may have changed since the worker import (or a
        # bank may have been restored while Loader stayed open).  Re-index and
        # retry before reporting a missing compatible BNK/WEM file.
        refresh_brawlhalla_file_index()
        targetPath = BRAWLHALLA_FILES.get(fileName)
        if targetPath and os.path.exists(targetPath):
            return targetPath, fileName
        for key, value in BRAWLHALLA_FILES.items():
            if key.casefold() == fn_lower and os.path.exists(value):
                return value, key
        targetPath = BRAWLHALLA_LANG_FILES.get(fileName)
        if targetPath and os.path.exists(targetPath):
            return targetPath, fileName
        for key, value in BRAWLHALLA_LANG_FILES.items():
            if key.casefold() == fn_lower and os.path.exists(value):
                return value, key
        return None, fileName

    @staticmethod
    def _is_sound_file(fileName: str) -> bool:
        """Return whether a file is a Wwise container or loose WEM asset."""
        return str(fileName).casefold().endswith((".bnk", ".wem"))

    def _sound_stack_folder(self):
        folder = os.path.join(self.origPreviewsPath, "SoundStacks")
        os.makedirs(folder, exist_ok=True)
        return folder

    def _sound_stack_path(self, fileName: str, modHash: str, content: bytes):
        file_token = hashlib.sha256(str(fileName).casefold().encode("utf-8")).hexdigest()[:16]
        content_token = hashlib.sha256(content).hexdigest()[:16]
        return os.path.join(
            self._sound_stack_folder(),
            f"{file_token}_{str(modHash)[:16]}_{content_token}.bin",
        )

    def _remove_sound_layer_backup(self, layer):
        backup_name = layer.get("backup") if isinstance(layer, dict) else None
        if not backup_name:
            return
        try:
            os.remove(os.path.join(self._sound_stack_folder(), backup_name))
        except OSError:
            pass

    def installFile(self, fileName: str, modFileContent: bytes, modHash: str):
        #print("Install file", fileName)
        SendNotification(NotificationType.InstallingModFile, modHash, fileName)

        targetPath, fileName = self._resolve_target_path(fileName)

        if not targetPath or not os.path.exists(targetPath):
            SendNotification(
                NotificationType.FatalError,
                f"Cannot install file '{fileName}'. The target game file was not found in the Brawlhalla directory. If Brawlhalla updated recently, please verify your game files on Steam."
            )
            return

        try:
            with open(targetPath, "rb") as file:
                origFileContent = file.read()

            origFileHash = HashFromBytes(origFileContent)
            modFileHash = HashFromBytes(modFileContent)

            if self._is_sound_file(fileName):
                # Sound conflicts are intentionally not reported: a BNK/WEM
                # container can carry many independent internal entries.  If
                # the user installs another sound mod, save the current layer
                # before replacing it so uninstall remains reversible.
                current_owner = self.modifiedFilesMap.get(fileName)
                if current_owner and current_owner != modHash:
                    stack = self.soundFileStacks.setdefault(fileName, [])
                    if not any(layer.get("modHash") == current_owner for layer in stack):
                        backup_path = self._sound_stack_path(fileName, current_owner, origFileContent)
                        with open(backup_path, "wb") as backup_file:
                            backup_file.write(origFileContent)
                        stack.append({
                            "modHash": current_owner,
                            "modFileHash": self.modFiles.get(fileName, origFileHash),
                            "backup": os.path.basename(backup_path),
                        })

                if fileName not in self.origFiles:
                    self.origFiles[fileName] = origFileHash
                    with open(os.path.join(self.origPreviewsPath, fileName), "wb") as copyFile:
                        copyFile.write(origFileContent)

                if origFileHash != modFileHash:
                    with open(targetPath, "wb") as modFile:
                        modFile.write(modFileContent)

                self.modFiles[fileName] = modFileHash
                self.modifiedFilesMap[fileName] = modHash
                self.saveData()
                return

            copyOrigFile = True

            if fileName not in self.origFiles:
                #print("Кеширование файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            elif fileName not in self.modFiles and self.origFiles[fileName] != origFileHash:
                #print("Перезапись кэша файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            elif fileName in self.modFiles and origFileHash not in (self.origFiles[fileName], self.modFiles[fileName]):
                #print("Перезапись кэша файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            else:
                copyOrigFile = False

            if copyOrigFile:
                #print("Копирование оригинального файла")
                SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                with open(os.path.join(self.origPreviewsPath, fileName), "wb") as copyFile:
                    copyFile.write(origFileContent)

            if origFileHash != modFileHash:
                #print("Замена оригинального файла")
                with open(targetPath, "wb") as modFile:
                    modFile.write(modFileContent)

            self.modFiles[fileName] = modFileHash
            self.modifiedFilesMap[fileName] = modHash

            self.saveData()
        except Exception as e:
            SendNotification(
                NotificationType.FatalError,
                f"Error processing game file '{fileName}': {str(e)}"
            )

    def repairFile(self, fileName: str):
        if fileName in self.origFiles:
            orig_path = os.path.join(self.origPreviewsPath, fileName)
            if not os.path.exists(orig_path):
                SendNotification(
                    NotificationType.FatalError,
                    f"Cannot restore original file '{fileName}'. Backup copy is missing from the cache folder."
                )
                self.modFiles.pop(fileName, None)
                self.modifiedFilesMap.pop(fileName, None)
                return

            try:
                with open(orig_path, "rb") as copyFile:
                    origFileContent = copyFile.read()

                targetPath, _ = self._resolve_target_path(fileName)

                if not targetPath or not os.path.exists(os.path.dirname(targetPath)):
                    SendNotification(
                        NotificationType.FatalError,
                        f"Cannot restore game file '{fileName}'. The target file was not found in the Brawlhalla folder (it may have been moved or removed in a recent game update)."
                    )
                else:
                    with open(targetPath, "wb") as file:
                        file.write(origFileContent)
            except Exception as e:
                SendNotification(
                    NotificationType.FatalError,
                    f"Error restoring game file '{fileName}': {str(e)}"
                )

            self.modFiles.pop(fileName, None)
            self.modifiedFilesMap.pop(fileName, None)

    def uninstallMod(self, modHash: str):
        for fileName, fileModHash in self.modifiedFilesMap.copy().items():
            if fileModHash == modHash:
                #print("Восстановление файла", fileName)
                SendNotification(NotificationType.UninstallingModFile, modHash, fileName)
                if self._is_sound_file(fileName):
                    stack = self.soundFileStacks.get(fileName, [])
                    if stack:
                        previous = stack.pop()
                        backup_name = previous.get("backup")
                        targetPath, _ = self._resolve_target_path(fileName)
                        backupPath = os.path.join(self._sound_stack_folder(), backup_name or "")
                        if targetPath and os.path.exists(backupPath):
                            try:
                                with open(backupPath, "rb") as backup_file:
                                    previous_content = backup_file.read()
                                with open(targetPath, "wb") as target_file:
                                    target_file.write(previous_content)
                                self.modFiles[fileName] = previous.get("modFileHash", HashFromBytes(previous_content))
                                self.modifiedFilesMap[fileName] = previous.get("modHash", "")
                                self._remove_sound_layer_backup(previous)
                            except OSError as error:
                                SendNotification(
                                    NotificationType.FatalError,
                                    f"Error restoring previous sound layer '{fileName}': {error}"
                                )
                        else:
                            # If a layer backup was removed externally, fall
                            # back to the original cached game file instead of
                            # leaving a partially installed bank in place.
                            self.soundFileStacks.pop(fileName, None)
                            self.repairFile(fileName)
                    else:
                        self.soundFileStacks.pop(fileName, None)
                        self.repairFile(fileName)
                else:
                    self.repairFile(fileName)

        # A sound mod can be below the active top layer.  Removing it only
        # removes its saved layer; the currently active sound file is kept.
        for fileName, stack in list(self.soundFileStacks.items()):
            retained = []
            for layer in stack:
                if layer.get("modHash") == modHash:
                    self._remove_sound_layer_backup(layer)
                else:
                    retained.append(layer)
            if retained:
                self.soundFileStacks[fileName] = retained
            else:
                self.soundFileStacks.pop(fileName, None)

        self.saveData()

    def getModConflict(self, files: List[str], modHash: str):
        conflictMods = set()

        for file in files:
            # BNK/WEM containers can legitimately be edited by several sound
            # mods at different internal event/media entries.  The Loader
            # replaces the complete container on disk, but must not block the
            # user with a file-level conflict dialog for those assets.
            if self._is_sound_file(file):
                continue
            if file in self.modifiedFilesMap:
                conflictMods.add(self.modifiedFilesMap[file])

        return list(conflictMods)


GameFiles = GameFilesClass()
