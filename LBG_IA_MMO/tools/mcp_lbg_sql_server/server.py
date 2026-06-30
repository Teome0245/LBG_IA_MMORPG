"""Serveur MCP read-only SQL (MariaDB) pour PreCU (VM 245) et Prime (VM 246)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_SRC = _ROOT / "agents" / "src"
if str(_AGENTS_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENTS_SRC))

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None
    DictCursor = None

from mcp.server.fastmcp import FastMCP
from lbg_agents.remote_targets import resolve_host

mcp = FastMCP("lbg-sql")


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _db_config(server_id: str) -> dict[str, Any]:
    sid = (server_id or "precu").strip().lower()
    
    # Résolution des hôtes via registry
    if sid in ("prime", "mmo", "246"):
        host = resolve_host("mmo") or "192.168.0.246"
        env_prefix = "CORE3_PRIME_DB_"
    else:
        host = resolve_host("precu") or "192.168.0.245"
        env_prefix = "CORE3_PRECU_DB_"

    user = os.environ.get(f"{env_prefix}USER") or os.environ.get("CORE3_DB_USER") or "swgemu"
    pwd = os.environ.get(f"{env_prefix}PASS") or os.environ.get("CORE3_DB_PASS") or ""
    db = os.environ.get(f"{env_prefix}NAME") or os.environ.get("CORE3_DB_NAME") or "swgemu"
    port_str = os.environ.get(f"{env_prefix}PORT") or os.environ.get("CORE3_DB_PORT") or "3306"
    
    try:
        port = int(port_str)
    except ValueError:
        port = 3306

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": pwd,
        "database": db,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
        "connect_timeout": 5,
    }


def _validate_readonly(sql: str) -> tuple[bool, str | None]:
    sql_clean = sql.strip().upper()
    if not sql_clean:
        return False, "La requête SQL est vide."
        
    # Doit débuter par SELECT / SHOW / DESCRIBE / EXPLAIN
    if not (sql_clean.startswith("SELECT") or sql_clean.startswith("SHOW") or sql_clean.startswith("DESC") or sql_clean.startswith("EXPLAIN")):
        return False, "Requête non autorisée. Seules les requêtes de lecture (SELECT, SHOW, DESCRIBE, EXPLAIN) sont permises."

    # Mots clés interdits
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "REPLACE", "CREATE", "TRUNCATE", "GRANT", "REVOKE", "LOAD", "RENAME"}
    tokens = set(re.findall(r"\b\w+\b", sql_clean))
    intersect = tokens.intersection(forbidden)
    if intersect:
        return False, f"La requête contient des jetons interdits (écriture/DDL suspecté) : {', '.join(intersect)}"

    return True, None


@mcp.tool()
def sql_list_tables(server_id: str = "precu") -> str:
    """Liste toutes les tables de la base de données.
    
    Args:
        server_id: Identifiant de la VM cible (ex: 'precu' ou 'prime'). Default: 'precu'.
    """
    if pymysql is None:
        return _dump({"ok": False, "error": "pymysql non disponible"})
        
    cfg = _db_config(server_id)
    try:
        with pymysql.connect(**cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                rows = cur.fetchall()
                tables = []
                for r in rows:
                    tables.extend(r.values())
                return _dump({"ok": True, "server": cfg["host"], "database": cfg["database"], "tables": tables})
    except Exception as e:
        return _dump({"ok": False, "server": cfg["host"], "error": str(e)})


@mcp.tool()
def sql_describe_table(table_name: str, server_id: str = "precu") -> str:
    """Renvoie la structure détaillée des colonnes d'une table.
    
    Args:
        table_name: Nom de la table à décrire.
        server_id: Identifiant de la VM cible (ex: 'precu' ou 'prime'). Default: 'precu'.
    """
    if pymysql is None:
        return _dump({"ok": False, "error": "pymysql non disponible"})
        
    if not re.match(r"^[A-Za-z0-9_]+$", table_name):
        return _dump({"ok": False, "error": f"Nom de table invalide : {table_name}"})

    cfg = _db_config(server_id)
    try:
        with pymysql.connect(**cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DESCRIBE `{table_name}`")
                columns = cur.fetchall()
                return _dump({"ok": True, "server": cfg["host"], "table": table_name, "columns": columns})
    except Exception as e:
        return _dump({"ok": False, "server": cfg["host"], "error": str(e)})


@mcp.tool()
def sql_query(query: str, server_id: str = "precu", limit: int = 100) -> str:
    """Exécute une requête SQL SELECT read-only et renvoie les résultats sous forme JSON.
    
    Args:
        query: Requête SQL (ex: 'SELECT * FROM accounts LIMIT 5').
        server_id: Identifiant de la VM cible (ex: 'precu' ou 'prime'). Default: 'precu'.
        limit: Nombre maximum de lignes à renvoyer (max 100). Default: 100.
    """
    if pymysql is None:
        return _dump({"ok": False, "error": "pymysql non disponible"})
        
    ok, err = _validate_readonly(query)
    if not ok:
        return _dump({"ok": False, "error": err})

    max_rows = min(max(1, limit), 100)
    cfg = _db_config(server_id)
    try:
        with pymysql.connect(**cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchmany(max_rows + 1)
                
                truncated = False
                if len(rows) > max_rows:
                    rows = rows[:max_rows]
                    truncated = True
                    
                return _dump({
                    "ok": True,
                    "server": cfg["host"],
                    "database": cfg["database"],
                    "rows": rows,
                    "count": len(rows),
                    "truncated": truncated
                })
    except Exception as e:
        return _dump({"ok": False, "server": cfg["host"], "error": str(e)})


if __name__ == "__main__":
    mcp.run()
