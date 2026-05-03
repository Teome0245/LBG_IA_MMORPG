from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from mail_imap_preview import run_mail_imap_preview
from pydantic import BaseModel, Field

import core

app = FastAPI(title="lbg-linux-agent-ia", version="0.1.0")


class InvokeRequest(BaseModel):
    actor_id: str
    text: str = Field(default="")
    context: dict[str, Any] = Field(default_factory=dict)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    allow_urls = core.url_allowlist()
    allow_hosts = core.url_host_allowlist()
    allow_dirs = core.file_allowlist_dirs()
    return {
        "status": "ok",
        "service": "agent_ia_linux",
        "version": "0.1.0",
        "linux": {
            "env_file": str(core.env_path()),
            "dry_run_env": core.get_cfg("LBG_LINUX_DRY_RUN").strip() or None,
            "url_allowlist_count": len(allow_urls),
            "url_allowlist_preview": allow_urls[:5],
            "url_host_allowlist_count": len(allow_hosts),
            "url_host_allowlist_preview": allow_hosts[:5],
            "file_allowlist_dirs_count": len(allow_dirs),
            "file_allowlist_dirs_preview": [str(p) for p in allow_dirs[:5]],
            "approval_gate_active": bool(core.get_cfg("LBG_LINUX_APPROVAL_TOKEN").strip()),
            "audit_log_path_set": bool(core.get_cfg("LBG_LINUX_AUDIT_LOG_PATH").strip()),
            "learn_enabled": core.learn_enabled(),
            "web_search_enabled": core.web_search_enabled(),
            "search_engine": core.linux_search_engine(),
            "mail_imap_enabled": core.mail_imap_enabled(),
        },
    }


@app.post("/invoke")
def invoke(payload: InvokeRequest) -> dict[str, object]:
    ctx = payload.context if isinstance(payload.context, dict) else {}
    action = ctx.get("desktop_action")
    trace_id = ctx.get("_trace_id") if isinstance(ctx.get("_trace_id"), str) else None
    dry_run = core.linux_dry_run(ctx)

    base: dict[str, object] = {
        "agent": "agent_ia_linux",
        "handler": "desktop",
        "actor_id": payload.actor_id,
        "request_text": payload.text,
        "meta": {"dry_run": dry_run, "execution_gated": core.linux_requires_approval()},
    }

    if not isinstance(action, dict):
        out = {**base, "ok": False, "outcome": "bad_request", "error": "Aucune desktop_action dans context."}
        core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
        return out

    kind = str(action.get("kind") or "").strip()

    if kind == "open_url":
        url = action.get("url")
        if not isinstance(url, str) or not url.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `url` requis"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        url = url.strip()
        if not core.url_is_allowed(url):
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "URL non autorisée",
                "url": url,
                "url_host_allowlist_preview": core.url_host_allowlist()[:5],
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not dry_run and core.linux_requires_approval() and not core.linux_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "url": url}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "url": url}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        try:
            # best-effort: xdg-open
            core.popen_quiet(["xdg-open", url])
            out = {**base, "ok": True, "outcome": "ok", "url": url}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "url": url}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

    if kind == "search_web_open":
        if not core.web_search_enabled():
            out = {
                **base,
                "ok": False,
                "outcome": "feature_disabled",
                "error": "Recherche web désactivée (LBG_LINUX_WEB_SEARCH=1 pour activer)",
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        query = action.get("query")
        if not isinstance(query, str) or not query.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `query` requis"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        url3, qerr = core.build_web_search_url(query)
        if not url3 or qerr:
            out = {**base, "ok": False, "outcome": "bad_request", "error": qerr or "requête invalide"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not core.web_search_url_trusted(url3):
            out = {**base, "ok": False, "outcome": "error", "error": "URL de recherche interne invalide", "url": url3}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not dry_run and core.linux_requires_approval() and not core.linux_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "url": url3}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "url": url3, "engine": core.linux_search_engine()}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        try:
            core.popen_quiet(["xdg-open", url3])
            out = {**base, "ok": True, "outcome": "ok", "url": url3, "engine": core.linux_search_engine()}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "url": url3}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

    if kind == "mail_imap_preview":
        if not core.mail_imap_enabled():
            out = {
                **base,
                "ok": False,
                "outcome": "feature_disabled",
                "error": "Messagerie IMAP désactivée (LBG_LINUX_MAIL_ENABLED=1 pour activer)",
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        fc_ok, sc_ok, max_m, max_b, max_sc, perr = core.mail_imap_parse_action(action)
        if perr:
            out = {**base, "ok": False, "outcome": "bad_request", "error": perr}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        host, port, user, password, use_ssl = core.mail_imap_credentials()
        if not dry_run and core.linux_requires_approval() and not core.linux_approval_ok(ctx):
            out = {
                **base,
                "ok": False,
                "outcome": "approval_denied",
                "error": "Approval token requis",
                "from_contains": fc_ok,
                "subject_contains": sc_ok,
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            hint_q = fc_ok or sc_ok
            messages = [
                {
                    "uid": "(dry-run)",
                    "from": "expéditeur@exemple.invalid",
                    "subject": f"… filtre « {hint_q} » (simulation)",
                    "date": "",
                    "body_preview": "[dry-run] Aucune connexion IMAP ; définir LBG_LINUX_MAIL_IMAP_* pour une exécution réelle.",
                }
            ]
            out = {
                **base,
                "ok": True,
                "outcome": "dry_run",
                "messages": messages,
                "matched_count": len(messages),
                "from_contains": fc_ok,
                "subject_contains": sc_ok,
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not host or not user or not password:
            out = {
                **base,
                "ok": False,
                "outcome": "configuration_error",
                "error": "IMAP incomplet : LBG_LINUX_MAIL_IMAP_HOST, USER et PASSWORD requis",
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        msgs, ierr = run_mail_imap_preview(
            host=host,
            port=port,
            user=user,
            password=password,
            use_ssl=use_ssl,
            from_contains=fc_ok,
            subject_contains=sc_ok,
            max_messages=max_m,
            max_body_chars=max_b,
            max_scan=max_sc,
        )
        if ierr:
            out = {
                **base,
                "ok": False,
                "outcome": "error",
                "error": ierr,
                "from_contains": fc_ok,
                "subject_contains": sc_ok,
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        out = {
            **base,
            "ok": True,
            "outcome": "ok",
            "messages": msgs,
            "matched_count": len(msgs),
            "from_contains": fc_ok,
            "subject_contains": sc_ok,
        }
        core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
        return out

    if kind == "file_append":
        path = action.get("path")
        content = action.get("text")
        if not isinstance(path, str) or not path.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `path` requis"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not isinstance(content, str):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `text` requis"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        path = path.strip()
        if not core.path_is_allowed(path):
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "Chemin non autorisé",
                "path": path,
                "file_allowlist_dirs_preview": [str(p) for p in core.file_allowlist_dirs()[:5]],
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if not dry_run and core.linux_requires_approval() and not core.linux_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "path": path}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "path": path, "bytes": len(content.encode("utf-8"))}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.open("a", encoding="utf-8").write(content)
            out = {**base, "ok": True, "outcome": "ok", "path": str(p), "bytes": len(content.encode("utf-8"))}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "path": path}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

    if kind == "open_app":
        app_id = action.get("app")
        args = action.get("args")
        want_learn = action.get("learn") is True
        if not isinstance(app_id, str) or not app_id.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `app` requis"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        app_id = app_id.strip()
        allow = core.split_csv((core.get_cfg("LBG_LINUX_APP_ALLOWLIST") or "").strip())
        if app_id not in allow:
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "Application non autorisée",
                "app": app_id,
                "app_allowlist_preview": allow[:10],
            }
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if args is None:
            args_list: list[str] = []
        elif isinstance(args, list) and all(isinstance(x, str) for x in args):
            args_list = [x for x in args if x.strip()]
        else:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `args` doit être list[string]"}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

        if not dry_run and core.linux_requires_approval() and not core.linux_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "app": app_id}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "app": app_id, "args": args_list}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

        map_raw = (core.get_cfg("LBG_LINUX_APP_MAP_JSON") or "").strip()
        try:
            mapping = json.loads(map_raw) if map_raw else {}
            if not isinstance(mapping, dict):
                mapping = {}
        except Exception:
            mapping = {}
        cmd = mapping.get(app_id) if isinstance(mapping, dict) else None

        cmd_list: list[str]
        if isinstance(cmd, str) and cmd.strip():
            cmd_list = [cmd.strip()]
        elif isinstance(cmd, list) and all(isinstance(x, str) for x in cmd) and cmd:
            cmd_list = [x.strip() for x in cmd if x.strip()]
        else:
            cmd_list = [app_id]

        try:
            core.popen_quiet([*cmd_list, *args_list])
            out = {**base, "ok": True, "outcome": "ok", "app": app_id, "args": args_list}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            if (
                want_learn
                and not dry_run
                and core.learn_enabled()
                and (not core.learn_allowlist() or app_id in core.learn_allowlist())
                and (not core.linux_requires_approval() or core.linux_approval_ok(ctx))
            ):
                resolved = core.which(app_id)
                if resolved:
                    okp, errp = core.persist_learned_app(app_id, resolved)
                    if okp:
                        try:
                            core.popen_quiet([resolved, *args_list])
                            out = {
                                **base,
                                "ok": True,
                                "outcome": "ok",
                                "app": app_id,
                                "args": args_list,
                                "learned": True,
                                "learned_path": resolved,
                            }
                            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
                            return out
                        except Exception as e2:
                            out = {
                                **base,
                                "ok": False,
                                "outcome": "error",
                                "error": str(e2),
                                "app": app_id,
                                "args": args_list,
                                "learned": True,
                                "learned_path": resolved,
                            }
                            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
                            return out
                    out = {
                        **base,
                        "ok": False,
                        "outcome": "error",
                        "error": f"{e} | learn_persist_failed: {errp}",
                        "app": app_id,
                        "args": args_list,
                        "learned": False,
                    }
                    core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
                    return out

            out = {**base, "ok": False, "outcome": "error", "error": str(e), "app": app_id, "args": args_list}
            core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
            return out

    out = {**base, "ok": False, "outcome": "unknown_kind", "error": "Action inconnue", "kind": kind}
    core.audit_write({"event": "agents.linux.audit", "trace_id": trace_id, **out})
    return out

