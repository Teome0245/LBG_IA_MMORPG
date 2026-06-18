from __future__ import annotations

import asyncio
import contextlib

from lbg_companion_bot.services import chat_service
from lbg_companion_bot.services import db as svc_db
from lbg_companion_bot.settings import Settings


class AutonomyLoop:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="companion_autonomy_loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is None:
            return
        t = self._task
        self._task = None
        t.cancel()
        # CancelledError est normal lors d'un arrêt propre.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t

    async def _run(self) -> None:
        # Boucle simple : tick des sessions récentes ; quotas côté chat_service évitent le spam.
        interval = max(1.0, float(self._settings.autonomous_loop_interval_s))
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self._tick_once)
            except Exception:
                # On ne crash pas le service sur une erreur de boucle ; prochaine itération retentera.
                pass
            await asyncio.sleep(interval)

    def _tick_once(self) -> None:
        con = svc_db.connect(self._settings.db_path)
        try:
            sids = svc_db.list_recent_sessions(con, limit=int(self._settings.autonomous_loop_max_sessions))
            for sid in sids:
                # Debug=false : ne pas exposer la mécanique ; le nudge est persisté en message si émis.
                chat_service.autonomous_tick(con=con, settings=self._settings, session_id=sid, debug=False)
        finally:
            con.close()

