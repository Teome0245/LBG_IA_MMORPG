import os
import subprocess
import logging
import string
import shutil
import winreg
import re
import textwrap
import importlib
import inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor")

# ---------------------------------------------------------
#  CACHE LOCAL DES PROGRAMMES RÉSOLUS
# ---------------------------------------------------------
PROGRAM_CACHE = {}

# ---------------------------------------------------------
#  RESOLVEUR AVANCÉ WINDOWS (multi-lecteurs, registre, PATH)
# ---------------------------------------------------------
def list_drives():
    return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]

def find_in_path(program_name):
    result = shutil.which(program_name)
    if result:
        print(f"[RESOLVER] ✔ Trouvé via PATH : {result}")
    return result

def find_in_registry(program_name):
    registry_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]

    for reg_path in registry_paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    if program_name.lower() in subkey_name.lower():
                        subkey = winreg.OpenKey(key, subkey_name)
                        path, _ = winreg.QueryValueEx(subkey, None)
                        print(f"[RESOLVER] ✔ Trouvé via registre : {path}")
                        return path
                    i += 1
                except OSError:
                    break
        except Exception:
            continue

    return None

def search_executable(program_name, drives):
    exe_name = program_name.lower() + ".exe"

    search_dirs = [
        "Program Files",
        "Program Files (x86)",
        "Users\\%USERNAME%\\AppData\\Local",
        "Users\\%USERNAME%\\AppData\\Roaming",
        "Applications",
        "PortableApps",
        "Games",
        "SteamLibrary"
    ]

    for drive in drives:
        for folder in search_dirs:
            base = os.path.expandvars(os.path.join(drive, folder))
            if not os.path.exists(base):
                continue

            print(f"[RESOLVER] 🔍 Scan : {base}")

            for root, dirs, files in os.walk(base):
                if exe_name in (f.lower() for f in files):
                    full_path = os.path.join(root, exe_name)
                    print(f"[RESOLVER] ✔ Trouvé via scan : {full_path}")
                    return full_path

    return None

def find_uwp_app(program_name):
    try:
        cmd = [
            "powershell",
            "-Command",
            f"Get-AppxPackage *{program_name}* | Select-Object -ExpandProperty InstallLocation"
        ]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()

        if result and os.path.exists(result):
            print(f"[RESOLVER] ✔ Trouvé via UWP : {result}")
            return result

    except Exception:
        pass

    return None

def resolve_program(program_name):
    print(f"[RESOLVER] 🔎 Recherche du programme : {program_name}")

    # 0) Cache local
    if program_name in PROGRAM_CACHE:
        print(f"[RESOLVER] ✔ Trouvé dans le cache : {PROGRAM_CACHE[program_name]}")
        return PROGRAM_CACHE[program_name]

    # 1) PATH
    path = find_in_path(program_name)
    if path:
        PROGRAM_CACHE[program_name] = path
        return path

    # 2) Registre
    path = find_in_registry(program_name)
    if path:
        PROGRAM_CACHE[program_name] = path
        return path

    # 3) UWP
    path = find_uwp_app(program_name)
    if path:
        PROGRAM_CACHE[program_name] = path
        return path

    # 4) Scan intelligent multi-lecteurs
    drives = list_drives()
    path = search_executable(program_name, drives)
    if path:
        PROGRAM_CACHE[program_name] = path
        return path

    print(f"[RESOLVER] ❌ Programme introuvable : {program_name}")
    return None

# ---------------------------------------------------------
#  FONCTION GÉNÉRIQUE : ouvrir un programme automatiquement
# ---------------------------------------------------------
def ouvrir_programme(program_name: str):
    path = resolve_program(program_name)

    if not path:
        return {
            "status": "error",
            "message": f"Programme '{program_name}' introuvable"
        }

    try:
        subprocess.Popen([path])
        return {
            "status": "ok",
            "message": f"Programme '{program_name}' lancé"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# ---------------------------------------------------------
#  CAPABILITY AUTO-CORRECTIVE : ouvrir_notepad
# ---------------------------------------------------------
def ouvrir_notepad(**kwargs):
    """
    Capability auto-corrective :
    - essaie notepad.exe
    - fallback vers le resolver avancé
    """
    print("[AUTO] Correction automatique de 'ouvrir_notepad'")

    # 1) Tentative directe
    try:
        subprocess.Popen(["notepad.exe"])
        return {"status": "ok", "message": "Notepad ouvert."}
    except Exception:
        pass

    # 2) Fallback via resolver
    result = ouvrir_programme("notepad")
    return result

# ---------------------------------------------------------
#  AUTRES CAPABILITÉS EXISTANTES
# ---------------------------------------------------------
def open_notepad():
    try:
        subprocess.Popen(['notepad.exe'])
        return {"status": "ok", "message": "Notepad ouvert."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_directory(path="."):
    try:
        files = os.listdir(path)
        return {"status": "ok", "path": os.path.abspath(path), "files": files}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return {"status": "ok", "content": f.read()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def write_file(path, content):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "ok", "message": f"Fichier écrit : {path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            return {"status": "ok", "message": f"Fichier supprimé : {path}"}
        else:
            return {"status": "error", "message": "Le fichier n'existe pas."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def ouvre_fichier(path):
    try:
        if path.lower() in ["calc", "calc.exe", "calculatrice"]:
            subprocess.Popen(["calc.exe"])
            return {"status": "ok", "message": "Calculatrice lancée."}

        os.startfile(path)
        return {"status": "ok", "message": f"Ouverture de : {path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
#  CAPABILITY AUTO-GÉNÉRÉE : ouvrir_vlc (OK)
# ---------------------------------------------------------
def ouvrir_vlc(**kwargs):
    try:
        subprocess.Popen([r"C:\Program Files\VideoLAN\VLC\vlc.exe"])
        return {
            "status": "ok",
            "message": "ouvrir_vlc exécuté."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }




# --- Capability auto-installée ---
# Description : Auto-installed capability ouvrir_istripper

def ouvrir_istripper(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'ouvrir_istripper' auto-générée mais programme inconnu ou non configuré"
    }




# --- Capability auto-installée ---
# Description : Auto-installed capability reload_capabilities

def reload_capabilities(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'reload_capabilities' auto-générée mais programme inconnu ou non configuré"
    }




# --- Capability auto-installée ---
# Description : Auto-installed capability liste_capabilities

def liste_capabilities(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'liste_capabilities' auto-générée mais programme inconnu ou non configuré"
    }




# --- Capability auto-installée ---
# Description : Auto-installed capability ouvrir_firefox

def ouvrir_firefox(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'ouvrir_firefox' auto-générée mais programme inconnu ou non configuré"
    }




# --- Capability auto-installée ---
# Description : Auto-installed capability list_agent_capabilities

def list_agent_capabilities(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'list_agent_capabilities' auto-générée mais programme inconnu ou non configuré"
    }




# --- Capability auto-installée ---
# Description : Auto-installed capability ouvrir_paint

def ouvrir_paint(**kwargs):
    return {
        "status": "error",
        "message": "Capability 'ouvrir_paint' auto-générée mais programme inconnu ou non configuré"
    }

