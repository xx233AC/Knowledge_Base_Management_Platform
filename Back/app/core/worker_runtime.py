"""Own a spawned worker for exactly one ASGI lifespan, including development reloads."""
import asyncio
from contextlib import suppress
import logging
import multiprocessing

from app.core.database import build_database
from app.integrations.infrastructure import Infrastructure

log = logging.getLogger(__name__)


def run_worker(settings, stop):
    from app.worker import Worker
    logging.basicConfig(level=logging.INFO)
    engine, factory = build_database(settings.database_url)
    try:
        Worker(settings, factory, Infrastructure.from_settings(settings)).run(stop)
    finally:
        engine.dispose()


class WorkerRuntime:
    def __init__(self, settings, *, check_interval=1.0, shutdown_timeout=5.0):
        self.settings = settings
        self.check_interval, self.shutdown_timeout = check_interval, shutdown_timeout
        self.context = multiprocessing.get_context('spawn')
        self.stop = self.context.Event()
        self.process = self.monitor = None

    def _start(self):
        self.process = self.context.Process(target=run_worker, args=(self.settings, self.stop),
                                            name='knowledge-worker', daemon=True)
        self.process.start()
        log.info('Background worker started (pid=%s)', self.process.pid)

    async def _watch(self):
        while True:
            await asyncio.sleep(self.check_interval)
            if not self.process.is_alive():
                self.process.join()
                log.error('Background worker exited (code=%s); restarting', self.process.exitcode)
                self.process.close()
                self._start()

    async def __aenter__(self):
        self._start()
        self.monitor = asyncio.create_task(self._watch())
        return self

    async def __aexit__(self, *_):
        self.monitor.cancel()
        with suppress(asyncio.CancelledError):
            await self.monitor
        self.stop.set()
        process = self.process
        try:
            await asyncio.to_thread(process.join, self.shutdown_timeout)
            if process.is_alive():
                log.warning('Stopping busy background worker (pid=%s)', process.pid)
                process.terminate()
                await asyncio.to_thread(process.join, self.shutdown_timeout)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join)
        finally:
            process.close()
            self.process = None
        log.info('Background worker stopped')
