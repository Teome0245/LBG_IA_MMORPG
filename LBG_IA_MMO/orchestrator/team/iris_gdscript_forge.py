"""Iris — forge GDScript M9 : gaps détectés → patches proposés (L1 staging / L2 apply)."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from team.m9_map_probe import _prime_client_root


@dataclass
class IrisPatchRecipe:
    gap_patterns: tuple[str, ...]
    template_rel: str | None = None
    target_rel: str | None = None
    patch_kind: str = "copy_template"
    track: str = "m9"
    description: str = ""


@dataclass
class IrisForgePatch:
    gap: str
    target_rel: str
    patch_kind: str
    description: str
    track: str
    staging_path: str
    applied: bool = False
    skipped_reason: str | None = None


@dataclass
class IrisForgeResult:
    ok: bool
    patches: list[IrisForgePatch] = field(default_factory=list)
    staging_dir: str = ""
    manifest_path: str = ""
    applied_count: int = 0
    gaps_unmatched: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "staging_dir": self.staging_dir,
            "manifest_path": self.manifest_path,
            "applied_count": self.applied_count,
            "gaps_unmatched": self.gaps_unmatched,
            "patches": [
                {
                    "gap": p.gap,
                    "target_rel": p.target_rel,
                    "patch_kind": p.patch_kind,
                    "description": p.description,
                    "track": p.track,
                    "staging_path": p.staging_path,
                    "applied": p.applied,
                    "skipped_reason": p.skipped_reason,
                }
                for p in self.patches
            ],
            "timestamp": self.timestamp,
        }


RECIPES: tuple[IrisPatchRecipe, ...] = (
    IrisPatchRecipe(
        ("minimap_script", "minimap_hud.gd"),
        template_rel="scripts/minimap_hud.gd",
        target_rel="scripts/minimap_hud.gd",
        track="m9b",
        description="Script minimap HUD M9b",
    ),
    IrisPatchRecipe(
        ("minimap_scene", "minimap_hud.tscn"),
        template_rel="scenes/ui/minimap_hud.tscn",
        target_rel="scenes/ui/minimap_hud.tscn",
        track="m9b",
        description="Scène minimap HUD M9b",
    ),
    IrisPatchRecipe(
        ("minimap_config", "minimap_config.json"),
        template_rel="config/minimap_config.json",
        target_rel="config/minimap_config.json",
        track="m9b",
        description="Config minimap M9b",
    ),
    IrisPatchRecipe(
        ("MinimapHud non branchée", "minimap_hud"),
        patch_kind="patch_main_minimap",
        target_rel="scenes/main.tscn",
        track="m9b",
        description="Brancher MinimapHud dans main.tscn",
    ),
    IrisPatchRecipe(
        ("planet_map_script", "planet_map_panel.gd"),
        template_rel="scripts/planet_map_panel.gd",
        target_rel="scripts/planet_map_panel.gd",
        track="m9c",
        description="Script carte planétaire M9c",
    ),
    IrisPatchRecipe(
        ("planet_map_scene", "planet_map_panel.tscn"),
        template_rel="scenes/ui/planet_map_panel.tscn",
        target_rel="scenes/ui/planet_map_panel.tscn",
        track="m9c",
        description="Scène carte planétaire M9c",
    ),
    IrisPatchRecipe(
        ("waypoint_store", "waypoint_store.gd"),
        template_rel="scripts/waypoint_store.gd",
        target_rel="scripts/waypoint_store.gd",
        track="m9c",
        description="Store waypoints M9c",
    ),
    IrisPatchRecipe(
        ("locations_tree", "locations_tree.json"),
        template_rel="assets/maps/locations_tree.json",
        target_rel="assets/maps/locations_tree.json",
        track="m9c",
        description="Arbre locations Scrapaltai M9c",
    ),
    IrisPatchRecipe(
        ("waypoints.json", "waypoints_config"),
        template_rel="config/waypoints.json",
        target_rel="config/waypoints.json",
        track="m9c",
        description="Config waypoints par défaut M9c",
    ),
    IrisPatchRecipe(
        ("PlanetMapPanel non branchée", "planet_map_panel"),
        patch_kind="patch_main_planet_map",
        target_rel="scenes/main.tscn",
        track="m9c",
        description="Brancher PlanetMapPanel dans main.tscn",
    ),
)

HERMES_RECIPES: tuple[IrisPatchRecipe, ...] = (
    IrisPatchRecipe(
        ("network_bridge", "network bridge"),
        template_rel="scripts/network_bridge.gd",
        target_rel="scripts/network_bridge.gd",
        track="hermes_net",
        description="Pont UDP NetworkBridge Hermès",
    ),
    IrisPatchRecipe(
        ("goto", "request_move_to", "udp goto"),
        patch_kind="llm_only",
        target_rel="scripts/player_controller.gd",
        track="hermes_net",
        description="Navigation goto UDP (LLM)",
    ),
)

ALL_RECIPES_BY_PERSONA: dict[str, tuple[IrisPatchRecipe, ...]] = {
    "iris": RECIPES,
    "hermes": HERMES_RECIPES,
}

_MAIN_MINIMAP_EXT = '[ext_resource type="PackedScene" path="res://scenes/ui/minimap_hud.tscn" id="11_mm"]'
_MAIN_MINIMAP_NODE = '[node name="MinimapHud" parent="UI" instance=ExtResource("11_mm")]'
_MAIN_PLANET_EXT = '[ext_resource type="PackedScene" path="res://scenes/ui/planet_map_panel.tscn" id="12_pmap"]'
_MAIN_PLANET_NODE = '[node name="PlanetMapPanel" parent="UI" instance=ExtResource("12_pmap")]'


def iris_forge_enabled() -> bool:
    return os.environ.get("LBG_IRIS_FORGE_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def iris_forge_auto_apply() -> bool:
    return os.environ.get("LBG_IRIS_FORGE_AUTO_APPLY", "0").strip().lower() in ("1", "true", "yes", "on")


def _template_root(persona: str = "iris") -> Path:
    sub = "hermes_net" if persona == "hermes" else "iris_m9"
    return Path(__file__).resolve().parent / "forge_templates" / sub


def _staging_base() -> Path:
    raw = os.environ.get("LBG_IRIS_FORGE_STAGING_DIR", "").strip()
    if raw:
        return Path(raw)
    return _prime_client_root() / ".iris_forge" / "staging"


def _match_recipe(gap: str, *, persona: str = "iris") -> IrisPatchRecipe | None:
    low = gap.lower()
    recipes = ALL_RECIPES_BY_PERSONA.get(persona, RECIPES)
    for recipe in recipes:
        if any(p.lower() in low for p in recipe.gap_patterns):
            return recipe
    # fallback croisé iris pour gaps M9 même si persona hermes mal routé
    if persona == "hermes":
        for recipe in RECIPES:
            if any(p.lower() in low for p in recipe.gap_patterns):
                return recipe
    return None


def _patch_main_tscn(content: str, *, mode: str) -> tuple[str, bool]:
    """Injecte ext_resource + node UI pour minimap ou planet map."""
    changed = False
    if mode == "patch_main_minimap":
        if "minimap_hud.tscn" not in content:
            insert_at = content.find("\n\n[sub_resource")
            if insert_at == -1:
                insert_at = content.find("\n[node name=")
            if insert_at != -1:
                content = content[:insert_at] + "\n" + _MAIN_MINIMAP_EXT + content[insert_at:]
                changed = True
        if "MinimapHud" not in content:
            ui_anchor = content.rfind('[node name="UI"')
            if ui_anchor != -1:
                next_node = content.find("\n[node name=", ui_anchor + 1)
                insert_at = len(content) if next_node == -1 else next_node
                content = content[:insert_at] + "\n\n" + _MAIN_MINIMAP_NODE + content[insert_at:]
                changed = True
    elif mode == "patch_main_planet_map":
        if "planet_map_panel.tscn" not in content:
            insert_at = content.find("\n\n[sub_resource")
            if insert_at == -1:
                insert_at = content.find("\n[node name=")
            if insert_at != -1:
                content = content[:insert_at] + "\n" + _MAIN_PLANET_EXT + content[insert_at:]
                changed = True
        if "PlanetMapPanel" not in content:
            insert_at = len(content)
            content = content.rstrip() + "\n\n" + _MAIN_PLANET_NODE + "\n"
            changed = True
    return content, changed


def _collect_gaps_from_probes(probes: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for probe in probes:
        if probe.get("ok"):
            continue
        gaps.extend(str(g) for g in (probe.get("gaps") or []))
        nested = probe.get("probes")
        if isinstance(nested, list):
            for sub in nested:
                if isinstance(sub, dict) and not sub.get("ok"):
                    gaps.extend(str(g) for g in (sub.get("gaps") or []))
                    if sub.get("hint"):
                        gaps.append(str(sub["hint"]))
        if probe.get("hint") and not probe.get("gaps"):
            gaps.append(str(probe["hint"]))
    seen: set[str] = set()
    out: list[str] = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _write_staging_file(staging_dir: Path, rel: str, content: str | bytes, *, binary: bool = False) -> Path:
    dest = staging_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        dest.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    else:
        dest.write_text(content if isinstance(content, str) else content.decode("utf-8"), encoding="utf-8")
    return dest


def _apply_patch(prime: Path, patch: IrisForgePatch, staging_dir: Path) -> bool:
    src = staging_dir / patch.target_rel
    if not src.is_file():
        patch.skipped_reason = "staging_missing"
        return False
    dest = prime / patch.target_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    patch.applied = True
    return True


def forge_patches_from_gaps(
    gaps: list[str],
    *,
    task_id: str = "manual",
    track: str = "m9_full",
    persona: str = "iris",
    auto_apply: bool | None = None,
) -> IrisForgeResult:
    """Génère des patches à partir des gaps M9 ; staging par défaut, apply si auto_apply."""
    if not iris_forge_enabled():
        return IrisForgeResult(ok=True, gaps_unmatched=gaps)

    staging_dir = _staging_base() / task_id.replace(":", "_")
    staging_dir.mkdir(parents=True, exist_ok=True)
    prime = _prime_client_root()
    template_root = _template_root(persona)
    should_apply = iris_forge_auto_apply() if auto_apply is None else auto_apply

    patches: list[IrisForgePatch] = []
    matched_gaps: set[str] = set()
    used_targets: set[str] = set()

    for gap in gaps:
        recipe = _match_recipe(gap, persona=persona)
        if recipe is None:
            continue
        if recipe.patch_kind == "llm_only":
            matched_gaps.add(gap)
            continue
        target_rel = recipe.target_rel or ""
        dedupe_key = f"{recipe.patch_kind}:{target_rel}"
        if dedupe_key in used_targets:
            matched_gaps.add(gap)
            continue
        used_targets.add(dedupe_key)

        patch = IrisForgePatch(
            gap=gap,
            target_rel=target_rel,
            patch_kind=recipe.patch_kind,
            description=recipe.description,
            track=recipe.track or track,
            staging_path=str(staging_dir / target_rel) if target_rel else "",
        )

        if recipe.patch_kind == "copy_template" and recipe.template_rel:
            tpl = template_root / recipe.template_rel
            if not tpl.is_file():
                patch.skipped_reason = "template_missing"
                patches.append(patch)
                matched_gaps.add(gap)
                continue
            dest = _write_staging_file(staging_dir, recipe.target_rel or recipe.template_rel, tpl.read_bytes(), binary=True)
            patch.staging_path = str(dest)
        elif recipe.patch_kind in ("patch_main_minimap", "patch_main_planet_map"):
            main_src = prime / "scenes/main.tscn"
            base_text = main_src.read_text(encoding="utf-8", errors="ignore") if main_src.is_file() else ""
            patched, changed = _patch_main_tscn(base_text, mode=recipe.patch_kind)
            if not changed and main_src.is_file():
                patch.skipped_reason = "already_present"
            else:
                dest = _write_staging_file(staging_dir, "scenes/main.tscn", patched)
                patch.staging_path = str(dest)
        else:
            patch.skipped_reason = "unknown_kind"

        patches.append(patch)
        matched_gaps.add(gap)

    applied_count = 0
    if should_apply:
        for patch in patches:
            if patch.skipped_reason or not patch.staging_path:
                continue
            if _apply_patch(prime, patch, staging_dir):
                applied_count += 1

    manifest_path = staging_dir / "iris_forge_manifest.json"
    result = IrisForgeResult(
        ok=len(patches) > 0 and all(p.skipped_reason in (None, "already_present") for p in patches),
        patches=patches,
        staging_dir=str(staging_dir),
        manifest_path=str(manifest_path),
        applied_count=applied_count,
        gaps_unmatched=[g for g in gaps if g not in matched_gaps],
    )
    manifest_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def forge_from_m9_probes(
    probes: list[dict[str, Any]],
    *,
    task_id: str,
    track: str = "m9_full",
    persona: str = "iris",
    auto_apply: bool | None = None,
) -> IrisForgeResult | None:
    gaps = _collect_gaps_from_probes(probes)
    if not gaps:
        return None
    return forge_patches_from_gaps(gaps, task_id=task_id, track=track, persona=persona, auto_apply=auto_apply)


def resolve_iris_forge(task_context: dict[str, Any]) -> bool:
    if not iris_forge_enabled():
        return False
    if task_context.get("iris_forge") or task_context.get("forge_gdscript"):
        return True
    return False
