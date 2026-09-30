import os
import sys
import shutil
import jpype

__all__ = []

_DLL_DIRECTORY_HANDLES = []


def _retain_dll_directory(path):
    """Keep a Windows DLL search directory active for the process lifetime."""
    if not path or not hasattr(os, "add_dll_directory") or not os.path.isdir(path):
        return
    try:
        _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(path))
    except Exception:
        pass


def _resolve_jpype_native_path(module):
    """Resolve Nuitka's real extracted _jpype binary, not its synthetic origin."""
    declared = getattr(module, "__file__", None)
    candidates = []

    if declared:
        declared = os.path.abspath(declared)
        candidates.append(declared)

        # Nuitka 4.x can report ``<onefile>\_jpype\_jpype.pyd`` as the
        # import origin while extracting the binary as ``<onefile>\_jpype.pyd``.
        declared_dir = os.path.dirname(declared)
        candidates.extend([
            os.path.join(os.path.dirname(declared_dir), os.path.basename(declared)),
            os.path.join(os.path.dirname(declared_dir), "_jpype.pyd"),
        ])

    compiled = globals().get("__compiled__")
    runtime_roots = [
        getattr(sys, "_MEIPASS", None),
        getattr(compiled, "containing_dir", None),
    ]

    module_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        runtime_roots.append(module_dir)
        parent = os.path.dirname(module_dir)
        if parent == module_dir:
            break
        module_dir = parent

    for root in runtime_roots:
        if root:
            candidates.append(os.path.join(root, "_jpype.pyd"))

    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized not in seen and os.path.isfile(candidate):
            return os.path.abspath(candidate)
        seen.add(normalized)
    return None

def get_resource_path(filename):
    # 1. Check direct relative to __file__
    try:
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), filename))
        if os.path.exists(p):
            return p
    except Exception:
        pass

    # 2. Check standard frozen and standalone runtime bases
    bases = [
        getattr(sys, '_MEIPASS', None),
        os.path.dirname(sys.executable),
        os.path.abspath("."),
    ]
    for base in bases:
        if base:
            for sub in ["", "core/ffdec", "core\\ffdec", "core", "assets"]:
                p = os.path.abspath(os.path.join(base, sub, filename))
                if os.path.exists(p):
                    return p

    # Fallback
    return os.path.abspath(os.path.join(os.path.dirname(__file__), filename))

PLAYERGLOBAL = get_resource_path("playerglobal32_0.swc")
FFDEC_LIB = get_resource_path("ffdec_lib.jar")
CMYKJPEG_LIB = get_resource_path("cmykjpeg.jar")
JL_LIB = get_resource_path("jl1.0.1.jar")

assert os.path.exists(FFDEC_LIB), f"ffdec_lib.jar doesn't exist at {FFDEC_LIB}"
assert os.path.exists(CMYKJPEG_LIB), f"cmykjpeg.jar doesn't exist at {CMYKJPEG_LIB}"
assert os.path.exists(JL_LIB), f"jl1.0.1.jar doesn't exist at {JL_LIB}"

jvmpath = None

if sys.platform.startswith("win"):
    # During JVM startup JPype asks Java to load its native module again. Fix
    # Nuitka's synthetic module origin before JPype passes it to System.load().
    try:
        import _jpype

        _jpype_native_path = _resolve_jpype_native_path(_jpype)
        if _jpype_native_path:
            _jpype.__file__ = _jpype_native_path
            _jpype_spec = getattr(_jpype, "__spec__", None)
            if _jpype_spec is not None:
                _jpype_spec.origin = _jpype_native_path
            _retain_dll_directory(os.path.dirname(_jpype_native_path))
    except Exception:
        pass

    def find_jvm_dll():
        # 1. Check JAVA_HOME environment variable first
        java_home = os.getenv("JAVA_HOME")
        if java_home and os.path.exists(java_home):
            for sub in [
                os.path.join("bin", "server", "jvm.dll"),
                os.path.join("bin", "client", "jvm.dll"),
                os.path.join("jre", "bin", "server", "jvm.dll"),
                os.path.join("bin", "default", "jvm.dll"),
                os.path.join("lib", "server", "jvm.dll"),
            ]:
                p = os.path.join(java_home, sub)
                if os.path.exists(p):
                    return p

        # 2. Ask JPype through its public API. This is the most reliable path
        # for vendor-specific registry keys used by Temurin, Oracle and JDKs.
        try:
            default_path = jpype.getDefaultJVMPath()
            if default_path and os.path.exists(default_path):
                is_64bit_python = sys.maxsize > 2**31
                is_32bit_path = "x86" in default_path.lower()
                if not (is_64bit_python and is_32bit_path):
                    return default_path
        except Exception:
            pass

        # 2b. java.exe may be available even when JAVA_HOME is not set.
        java_exe = shutil.which("java")
        if java_exe:
            java_home = os.path.dirname(os.path.dirname(os.path.abspath(java_exe)))
            for sub in [os.path.join("bin", "server", "jvm.dll"),
                        os.path.join("jre", "bin", "server", "jvm.dll")]:
                candidate = os.path.join(java_home, sub)
                if os.path.exists(candidate):
                    return candidate

        # 3. Check Windows Registry for JavaHome
        try:
            import winreg
            for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for reg_path in [
                    r"SOFTWARE\JavaSoft\Java Runtime Environment",
                    r"SOFTWARE\JavaSoft\JRE",
                    r"SOFTWARE\JavaSoft\Java Development Kit",
                    r"SOFTWARE\JavaSoft\JDK",
                ]:
                    try:
                        with winreg.OpenKey(root_key, reg_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                            cur_ver, _ = winreg.QueryValueEx(k, "CurrentVersion")
                            with winreg.OpenKey(k, cur_ver) as vk:
                                reg_java_home, _ = winreg.QueryValueEx(vk, "JavaHome")
                                if reg_java_home and os.path.exists(reg_java_home):
                                    for sub in [
                                        os.path.join("bin", "server", "jvm.dll"),
                                        os.path.join("bin", "client", "jvm.dll"),
                                        os.path.join("jre", "bin", "server", "jvm.dll"),
                                        os.path.join("bin", "default", "jvm.dll"),
                                    ]:
                                        p = os.path.join(reg_java_home, sub)
                                        if os.path.exists(p):
                                            return p
                    except Exception:
                        pass
        except Exception:
            pass

        # 4. Search common 64-bit Java installation directories
        candidates = []
        pf = os.getenv("ProgramFiles", "C:\\Program Files")
        java_dir = os.path.join(pf, "Java")
        if os.path.exists(java_dir):
            for entry in os.listdir(java_dir):
                candidates.append(os.path.join(java_dir, entry))

        for vendor in ["Eclipse Adoptium", "BellSoft", "Amazon Corretto", "Zulu", "Semeru"]:
            v_dir = os.path.join(pf, vendor)
            if os.path.exists(v_dir):
                for entry in os.listdir(v_dir):
                    candidates.append(os.path.join(v_dir, entry))

        for base in candidates:
            for sub in [
                os.path.join("bin", "server", "jvm.dll"),
                os.path.join("bin", "client", "jvm.dll"),
                os.path.join("jre", "bin", "server", "jvm.dll"),
                os.path.join("bin", "default", "jvm.dll"),
                os.path.join("lib", "server", "jvm.dll"),
            ]:
                p = os.path.join(base, sub)
                if os.path.exists(p):
                    return p
        return None


    jvmpath = find_jvm_dll()

    if jvmpath:
        jvm_dir = os.path.dirname(jvmpath)
        java_bin = os.path.dirname(jvm_dir)
        java_root = os.path.dirname(java_bin)

        if not os.getenv("JAVA_HOME"):
            os.environ["JAVA_HOME"] = java_root

        for pe in [java_bin, jvm_dir]:
            if os.path.exists(pe) and pe not in os.environ.get("PATH", ""):
                os.environ["PATH"] = pe + os.path.pathsep + os.environ.get("PATH", "")

        for pe in [java_bin, jvm_dir]:
            _retain_dll_directory(pe)

    flashlibFolder = os.path.join(os.getenv("APPDATA"), "JPEXS", "FFDec", "flashlib")
    flashlibFile = os.path.join(flashlibFolder, "playerglobal32_0.swc")

    if not os.path.exists(flashlibFile):
        if not os.path.exists(flashlibFolder):
            os.makedirs(flashlibFolder, exist_ok=True)

        with open(PLAYERGLOBAL, "rb") as orig:
            with open(flashlibFile, "wb") as new:
                new.write(orig.read())

elif sys.platform == "darwin":
    jvmpath = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/lib/jli/libjli.dylib"

else:
    pass

if not jpype.isJVMStarted():
    if jvmpath is None:
        raise ImportError("Java not found!")
    jpype.startJVM(jvmpath, "-Xmx2048m", "-Xms32m", "-XX:+UseSerialGC", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])




from .classes import *
