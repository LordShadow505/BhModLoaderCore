import os
import sys
import jpype

__all__ = []

def get_resource_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # In PyInstaller bundle, __file__ is relative to _MEIPASS or absolute
        _base = os.path.dirname(__file__)
        if not os.path.isabs(_base):
            return os.path.join(sys._MEIPASS, _base, filename)
        return os.path.join(_base, filename)
    # In development
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

        # 2. Try jpype's default JVM path finder (verify 64-bit vs 32-bit)
        try:
            default_path = jpype._jvmfinder.getDefaultJVMPath()
            if default_path and os.path.exists(default_path):
                is_64bit_python = sys.maxsize > 2**31
                is_32bit_path = "x86" in default_path.lower()
                if not (is_64bit_python and is_32bit_path):
                    return default_path
        except Exception:
            pass

        # 3. Search common 64-bit Java installation directories
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

        if hasattr(os, "add_dll_directory"):
            for pe in [java_bin, jvm_dir]:
                if os.path.exists(pe):
                    try:
                        os.add_dll_directory(pe)
                    except Exception:
                        pass

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

if jvmpath is None:
    raise ImportError("Java not found!")

jpype.startJVM(jvmpath, "-Xmx2048m", "-Xms32m", "-XX:+UseSerialGC", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])




from .classes import *
