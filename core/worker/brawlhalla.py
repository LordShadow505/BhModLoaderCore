import os
import re
import sys

from .config import ModloaderCoreConfig

from ..utils.hash import HashFile
from ..ffdec.classes import ArrayList, Configuration, HighlightedTextWriter, ScriptExportMode
from ..swf import Swf

__all__ = ["BRAWLHALLA_PATH", "BRAWLHALLA_SWFS", "BRAWLHALLA_FILES", "BRAWLHALLA_LANG_FILES", "BRAWLHALLA_VERSION"]


BRAWLHALLA_PATH = None
BRAWLHALLA_SWFS = {}
BRAWLHALLA_FILES = {}
BRAWLHALLA_LANG_FILES = {}   # {"language.1.bin": "/abs/path/language.1.bin"}
BRAWLHALLA_VERSION = None


if sys.platform in ["win32", "win64"]:
    import winreg

    brawlhallaFolders = []
    steamHomePath = ""

    # Try custom path first
    if ModloaderCoreConfig.customBrawlhallaPath:
        if os.path.exists(ModloaderCoreConfig.customBrawlhallaPath):
            BRAWLHALLA_PATH = ModloaderCoreConfig.customBrawlhallaPath

    if BRAWLHALLA_PATH is None:
        for reg in ["SOFTWARE\\WOW6432Node\\Valve\\Steam", "SOFTWARE\\Valve\\Steam"]:
            try:
                steamHomePath = winreg.QueryValueEx(
                    winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        reg
                    ),
                    "InstallPath"
                )[0]
                break
            except FileNotFoundError:
                pass

    if steamHomePath:
        with open(os.path.join(os.path.join(steamHomePath, "steamapps"), "libraryfolders.vdf")) as vdf:
            for path in [*re.findall(r'(?:"\d{1,3}"|"path")\t{2}"(.+)"\n', vdf.read()), steamHomePath]:
                try:
                    folder = os.path.join(path.replace("\\\\", "\\"), "steamapps")
                    if not os.path.exists(folder):
                        continue
                    if "common" in os.listdir(folder) and "Brawlhalla" in os.listdir(os.path.join(folder, "common")):
                        brawlhallaFolders.append(os.path.join(folder, "common", "Brawlhalla"))
                except:
                    pass

        brawlhallaFolders = list({*brawlhallaFolders, *ModloaderCoreConfig.brawlhallaAllowedPaths})

        for folder in brawlhallaFolders:
            if os.path.exists(folder) and "Brawlhalla.exe" in os.listdir(folder) and "BrawlhallaAir.swf" in os.listdir(
                    folder):
                if folder in ModloaderCoreConfig.brawlhallaIgnoredPaths:
                    continue

                BRAWLHALLA_PATH = folder

    del brawlhallaFolders
    del steamHomePath

    if BRAWLHALLA_PATH is None:
        import time
        import psutil

        os.system("start steam://rungameid/291550")

        found = False
        path = None

        i = 0
        while not found and i < 5:
            time.sleep(1)

            for proc in psutil.process_iter():
                try:
                    proc_name = proc.name()
                except psutil.NoSuchProcess:
                    pass
                else:
                    if proc_name == "Brawlhalla.exe":
                        found = True
                        os.system(f'taskkill /pid {proc.pid}')
                        path = proc.cwd()
                        break

            i += 1

        BRAWLHALLA_PATH = path

    if BRAWLHALLA_PATH is None:
        print("Brawlhalla not found! Please set the path manually in settings.")

elif sys.platform == "darwin":
    pass

else:
    pass

if BRAWLHALLA_PATH is not None and os.path.exists(BRAWLHALLA_PATH):
    try:
        # Fast shallow scan of Brawlhalla folder (depth <= 1)
        root_files = os.listdir(BRAWLHALLA_PATH)
        for f in root_files:
            full_p = os.path.join(BRAWLHALLA_PATH, f)
            if os.path.isfile(full_p):
                f_lower = f.lower()
                if f_lower.endswith(".swf"):
                    BRAWLHALLA_SWFS[f] = full_p
                elif f_lower.endswith((".mp3", ".png", ".jpg")):
                    BRAWLHALLA_FILES[f] = full_p
            elif os.path.isdir(full_p):
                try:
                    for sf in os.listdir(full_p):
                        sub_p = os.path.join(full_p, sf)
                        if os.path.isfile(sub_p):
                            sf_lower = sf.lower()
                            if sf_lower.endswith(".swf"):
                                BRAWLHALLA_SWFS[sf] = sub_p
                            elif sf_lower.endswith((".mp3", ".png", ".jpg")):
                                BRAWLHALLA_FILES[sf] = sub_p
                except Exception:
                    pass
    except Exception as e:
        print(f"[Brawlhalla] Error scanning directory: {e}")

    # Search brawlhalla language files
    _lang_folder = os.path.join(BRAWLHALLA_PATH, "languages")
    if os.path.isdir(_lang_folder):
        for _lf in os.listdir(_lang_folder):
            if _lf.lower().endswith(".bin Bin"):
                BRAWLHALLA_LANG_FILES[_lf] = os.path.join(_lang_folder, _lf)
            elif _lf.lower().endswith(".bin"):
                BRAWLHALLA_LANG_FILES[_lf] = os.path.join(_lang_folder, _lf)
    del _lang_folder



    # Get brawlhalla version
    _bhAir = BRAWLHALLA_SWFS.get("BrawlhallaAir.swf", None)

    if _bhAir is not None:
        brawlhallaAirHash = HashFile(_bhAir)

        if brawlhallaAirHash == ModloaderCoreConfig.brawlhallaAirHash:
            BRAWLHALLA_VERSION = ModloaderCoreConfig.brawlhallaVersion

        else:

            try:
                with open(_bhAir, "rb") as _raw:
                    _raw_bytes = _raw.read()
                _version_matches = re.findall(rb'(\d\.\d\d(?:\.\d)?)', _raw_bytes)

                from collections import Counter
                _counts = Counter(
                    m.decode("utf-8") for m in _version_matches
                    if len(m) in (4, 6)  # "X.XX" or "X.XX.X"
                )
                if _counts:
                    BRAWLHALLA_VERSION = _counts.most_common(1)[0][0]
                del _raw_bytes, _version_matches, _counts
            except Exception:
                pass

            # ── Slow path: full FFDec decompile (fallback) ───────────────────
            if BRAWLHALLA_VERSION is None:
                brawlhallaAir = Swf(_bhAir)

                for AS3Pack in brawlhallaAir.AS3Packs:
                    methodInfos = ArrayList()
                    AS3Pack.getMethodInfos(methodInfos)

                    abc = AS3Pack.abc
                    for methodInfo in methodInfos:
                        bodyIndex = abc.findBodyIndex(methodInfo.getMethodIndex())

                        if bodyIndex != -1:
                            body = abc.bodies.get(bodyIndex)
                            writer = HighlightedTextWriter(Configuration.getCodeFormatting(), True)
                            abc.bodies.get(bodyIndex).getCode().toASMSource(abc, abc.constants,
                                                                            abc.method_info.get(body.method_info),
                                                                            body,
                                                                            ScriptExportMode.PCODE,
                                                                            writer)
                            search = re.findall(r'pushstring "(\d\.\d\d|\d\.\d\d.\d)"', str(writer.toString()))

                            if search:
                                BRAWLHALLA_VERSION = search[0]
                                break

                    if BRAWLHALLA_VERSION is not None:
                        ModloaderCoreConfig.brawlhallaVersion = BRAWLHALLA_VERSION
                        ModloaderCoreConfig.brawlhallaAirHash = brawlhallaAirHash
                        ModloaderCoreConfig.save()
                        break

                brawlhallaAir.close()
                del brawlhallaAir

            if BRAWLHALLA_VERSION is not None:
                ModloaderCoreConfig.brawlhallaVersion = BRAWLHALLA_VERSION
                ModloaderCoreConfig.brawlhallaAirHash = brawlhallaAirHash
                ModloaderCoreConfig.save()

    del _bhAir
