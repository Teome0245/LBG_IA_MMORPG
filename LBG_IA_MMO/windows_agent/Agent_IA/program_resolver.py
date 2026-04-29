import os
import string
import shutil
import winreg
import subprocess


# ---------------------------------------------------------
#  LISTE DES LECTEURS DISPONIBLES (C:, D:, E:, M:, O:, …)
# ---------------------------------------------------------
def list_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


# ---------------------------------------------------------
#  RECHERCHE DANS LE PATH
# ---------------------------------------------------------
def find_in_path(program_name):
    result = shutil.which(program_name)
    if result:
        print(f"[RESOLVER] ✔ Trouvé via PATH : {result}")
    return result


# ---------------------------------------------------------
#  RECHERCHE DANS LA BASE DE REGISTRE
# ---------------------------------------------------------
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


# ---------------------------------------------------------
#  RECHERCHE SUR TOUS LES LECTEURS (SCAN INTELLIGENT)
# ---------------------------------------------------------
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
                for f in files:
                    if f.lower() == exe_name:
                        full_path = os.path.join(root, f)
                        print(f"[RESOLVER] ✔ Trouvé via scan : {full_path}")
                        return full_path

    return None


# ---------------------------------------------------------
#  RECHERCHE DES APPS UWP (Microsoft Store)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
#  FONCTION PRINCIPALE : TROUVER UN PROGRAMME
# ---------------------------------------------------------
def resolve_program(program_name):
    print(f"[RESOLVER] 🔎 Recherche du programme : {program_name}")

    # 1) PATH
    path = find_in_path(program_name)
    if path:
        return path

    # 2) Registre
    path = find_in_registry(program_name)
    if path:
        return path

    # 3) UWP
    path = find_uwp_app(program_name)
    if path:
        return path

    # 4) Scan intelligent multi-lecteurs
    drives = list_drives()
    path = search_executable(program_name, drives)
    if path:
        return path

    print(f"[RESOLVER] ❌ Programme introuvable : {program_name}")
    return None

