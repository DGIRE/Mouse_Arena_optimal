"""Mouse Arena Data Console -- interactive viewer for the Mouse Arena aggregate."""
__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Qt DLL isolation (Windows) -- ONLY for a self-contained pip PySide6 wheel.
#
# A pip PySide6 (Qt6*.dll bundled next to the bindings) living in a venv on top
# of Anaconda's Python can collide with Anaconda's own Qt6/ICU in ...\Library\bin.
# For that case we push PySide6's own folder to the front of the DLL search.
#
# A conda / conda-forge PySide6 instead keeps its Qt6 libraries in the
# environment's ``Library\bin`` and manages a self-consistent Qt/ICU/runtime set;
# touching the DLL search there would BREAK it. We detect the pip case by the
# presence of ``Qt6Core.dll`` inside the PySide6 package dir and only isolate
# then; for a conda build this is a complete no-op.
#
# Runs on package import, BEFORE app.py's `from PySide6 import QtWidgets`.
# ---------------------------------------------------------------------------
def _isolate_pyside6_dlls():
    import os
    try:
        import importlib.util
        spec = importlib.util.find_spec("PySide6")   # locate, don't import
        locs = list(getattr(spec, "submodule_search_locations", None) or [])
        if not locs:
            return
        pyside_dir = locs[0]

        # Only act for a self-contained pip wheel (Qt6 DLLs bundled here).
        if not os.path.isfile(os.path.join(pyside_dir, "Qt6Core.dll")):
            return                                    # conda build -> leave it alone

        os.environ.setdefault("CONDA_DLL_SEARCH_MODIFICATION_ENABLE", "0")

        # drop conda's Library\...\bin (foreign Qt6/ICU) from PATH
        kept = []
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if not p:
                continue
            norm = p.replace("/", "\\").lower()
            if "\\library\\" in norm and norm.rstrip("\\").endswith("bin"):
                continue
            kept.append(p)
        os.environ["PATH"] = pyside_dir + os.pathsep + os.pathsep.join(kept)

        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(pyside_dir)
            except Exception:
                pass
        plugins = os.path.join(pyside_dir, "plugins")
        if os.path.isdir(plugins):
            os.environ["QT_PLUGIN_PATH"] = plugins
            platforms = os.path.join(plugins, "platforms")
            if os.path.isdir(platforms):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms

        if os.name == "nt":
            try:
                import ctypes
                for dll in ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"):
                    p = os.path.join(pyside_dir, dll)
                    if os.path.isfile(p):
                        try:
                            ctypes.WinDLL(p)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass


_isolate_pyside6_dlls()
