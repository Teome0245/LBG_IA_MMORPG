"""Iris/Hermès — forge LLM + validation smoke avant apply."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from team.iris_gdscript_forge import IrisForgeResult, forge_patches_from_gaps, iris_forge_auto_apply
from team.reason_llm import complete_reason, extract_code_block, reason_llm_enabled


def iris_llm_forge_enabled() -> bool:
    return os.environ.get("LBG_IRIS_FORGE_LLM", "1").strip().lower() in ("1", "true", "yes", "on")


def iris_forge_smoke_required() -> bool:
    return os.environ.get("LBG_IRIS_FORGE_SMOKE_REQUIRED", "1").strip().lower() in ("1", "true", "yes", "on")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


_SMOKE_BY_TRACK: dict[str, str] = {
    "m9b": "infra/scripts/smoke_prime_client_minimap.sh",
    "m9c": "infra/scripts/smoke_prime_client_planet_map.sh",
    "m9_full": "infra/scripts/smoke_prime_client_minimap.sh",
    "hermes_net": "infra/scripts/smoke_godot_sidecar_mirror_lan.sh",
    "client_live": "infra/scripts/smoke_godot_sidecar_mirror_lan.sh",
}


def run_forge_smoke(track: str) -> dict[str, Any]:
    rel = _SMOKE_BY_TRACK.get(track)
    if not rel:
        return {"ok": True, "skipped": True, "reason": f"pas de smoke pour track {track}"}
    script = _repo_root() / rel
    if not script.is_file():
        return {"ok": False, "error": f"smoke absent: {script}"}
    timeout = int(os.environ.get("LBG_IRIS_FORGE_SMOKE_TIMEOUT_S", "90"))
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "script": str(script),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "stderr_tail": (proc.stderr or "")[-800:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout}s", "script": str(script)}


def _llm_system_prompt(*, persona: str) -> str:
    label = "Iris (UI Godot 2D M9)" if persona == "iris" else "Hermès (réseau SOE Prime Client)"
    return (
        f"Tu es {label}. Génère du GDScript Godot 4.x minimal, idempotent, sans secrets. "
        "Réponds UNIQUEMENT avec un bloc ```gdscript ... ``` complet et prêt à écrire sur disque. "
        "Pas de prose hors code."
    )


def _guess_target_path(gap: str, *, persona: str) -> str | None:
    low = gap.lower()
    if persona == "hermes" or "network" in low or "bridge" in low or "udp" in low:
        if "goto" in low or "move" in low:
            return "scripts/player_controller.gd"
        return "scripts/network_bridge.gd"
    if "minimap" in low:
        return "scripts/minimap_hud.gd"
    if "planet" in low or "carte" in low or "waypoint" in low:
        if "waypoint_store" in low:
            return "scripts/waypoint_store.gd"
        return "scripts/planet_map_panel.gd"
    return None


def llm_patch_for_gap(gap: str, *, persona: str = "iris", track: str = "m9_full") -> dict[str, Any]:
    if not iris_llm_forge_enabled() or not reason_llm_enabled():
        return {"ok": False, "skipped": True, "gap": gap, "reason": "LLM désactivé"}

    target = _guess_target_path(gap, persona=persona)
    if not target:
        return {"ok": False, "skipped": True, "gap": gap, "reason": "cible inconnue"}

    user = (
        f"Gap détecté : {gap}\n"
        f"Track : {track}\n"
        f"Fichier cible : res://{target}\n"
        "Produis le fichier GDScript complet qui comble ce gap pour Prime Client SWG-like."
    )
    llm = complete_reason(system=_llm_system_prompt(persona=persona), user=user, profile="forge")
    if not llm.get("ok"):
        return {"ok": False, "gap": gap, "target_rel": target, "error": llm.get("error")}

    code = extract_code_block(str(llm.get("text") or ""), lang="gdscript")
    if not code:
        return {"ok": False, "gap": gap, "target_rel": target, "error": "LLM sans bloc gdscript"}

    return {
        "ok": True,
        "gap": gap,
        "target_rel": target,
        "patch_kind": "llm_gdscript",
        "content": code,
        "model": llm.get("model"),
    }


def forge_with_llm_and_smoke(
    gaps: list[str],
    *,
    task_id: str,
    track: str = "m9_full",
    persona: str = "iris",
    auto_apply: bool | None = None,
) -> dict[str, Any]:
    """Pipeline complet : templates → LLM gaps restants → smoke → apply conditionnel."""
    template_result = forge_patches_from_gaps(gaps, task_id=task_id, track=track, auto_apply=False)
    staging_dir = Path(template_result.staging_dir)
    llm_patches: list[dict[str, Any]] = []

    for gap in template_result.gaps_unmatched:
        lp = llm_patch_for_gap(gap, persona=persona, track=track)
        if lp.get("skipped"):
            continue
        llm_patches.append(lp)
        if lp.get("ok") and lp.get("content") and lp.get("target_rel"):
            rel = str(lp["target_rel"])
            dest = staging_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(str(lp["content"]), encoding="utf-8")
            from team.iris_gdscript_forge import IrisForgePatch

            template_result.patches.append(
                IrisForgePatch(
                    gap=str(lp["gap"]),
                    target_rel=rel,
                    patch_kind="llm_gdscript",
                    description=f"LLM patch {rel}",
                    track=track,
                    staging_path=str(dest),
                )
            )

    smoke = run_forge_smoke(track) if iris_forge_smoke_required() else {"ok": True, "skipped": True}
    smoke_ok = bool(smoke.get("ok"))

    should_apply = (iris_forge_auto_apply() if auto_apply is None else auto_apply) and smoke_ok
    applied_count = 0
    if should_apply and template_result.patches:
        import shutil

        from team.m9_map_probe import _prime_client_root

        prime = _prime_client_root()
        for patch in template_result.patches:
            if patch.skipped_reason or not patch.staging_path:
                continue
            src = Path(patch.staging_path)
            if not src.is_file():
                continue
            dest = prime / patch.target_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            patch.applied = True
            applied_count += 1

    return {
        "template_forge": template_result.to_dict(),
        "llm_patches": llm_patches,
        "smoke": smoke,
        "smoke_ok": smoke_ok,
        "applied_count": applied_count,
        "apply_blocked_by_smoke": (iris_forge_auto_apply() if auto_apply is None else auto_apply) and not smoke_ok,
        "persona": persona,
        "track": track,
    }
