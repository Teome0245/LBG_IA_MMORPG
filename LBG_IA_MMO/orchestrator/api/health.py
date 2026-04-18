from fastapi import APIRouter, Header, HTTPException, Response

from services import metrics as svc_metrics

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
def metrics(
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Response:
    if not svc_metrics.enabled():
        raise HTTPException(status_code=404, detail={"error": "not_found", "hint": "metrics disabled"})
    expected = svc_metrics.auth_token()
    if expected:
        got = (authorization or "").strip()
        prefix = "Bearer "
        if not (got.startswith(prefix) and got[len(prefix) :].strip() == expected):
            raise HTTPException(status_code=401, detail={"error": "unauthorized", "hint": "invalid metrics token"})

    body = svc_metrics.render_prometheus_text()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

