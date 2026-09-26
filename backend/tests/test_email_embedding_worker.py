"""Background loop checks for the committed-email embedding worker."""

import asyncio

import pytest

from services.email_embedding_worker import EmailEmbeddingWorker


@pytest.mark.asyncio
async def test_loop_reports_sweep_error_and_stops(monkeypatch, caplog):
    worker = EmailEmbeddingWorker(interval_seconds=3600)
    started = asyncio.Event()

    async def fail_sweep():
        started.set()
        raise RuntimeError("temporary")

    monkeypatch.setattr(worker, "_sweep", fail_sweep)
    await worker.start()
    task = worker._task
    await worker.start()
    assert worker._task is task
    await asyncio.wait_for(started.wait(), 1)
    for _ in range(100):
        if "Email embedding sweep failed: RuntimeError" in caplog.text:
            break
        await asyncio.sleep(0)
    await worker.stop()
    assert "Email embedding sweep failed: RuntimeError" in caplog.text
    assert worker._running is False


@pytest.mark.asyncio
async def test_stop_cancels_active_sweep(monkeypatch):
    worker = EmailEmbeddingWorker()
    started = asyncio.Event()

    async def wait_in_sweep():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(worker, "_sweep", wait_in_sweep)
    await worker.start()
    await asyncio.wait_for(started.wait(), 1)
    await worker.stop()
    assert worker._task.done()


@pytest.mark.asyncio
async def test_stop_accepts_task_cancelled_before_loop_starts():
    worker = EmailEmbeddingWorker()
    await worker.start()
    worker._task.cancel()
    await worker.stop()
    assert worker._running is False
