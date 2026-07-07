"""API synthèse infra — alertes jobs + sonde stockage pour Assistant Pilot."""

from __future__ import annotations

from fastapi import APIRouter, Query

from services.infra_alerts import build_infra_alerts

router = APIRouter(tags=["infra"])


@router.get("/infra/alerts")
def get_infra_alerts(probe: bool = Query(default=True, description="Inclure sonde stockage Proxmox SSH")) -> dict:
    return build_infra_alerts(include_probe=probe)
