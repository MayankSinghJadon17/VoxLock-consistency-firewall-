from __future__ import annotations
import asyncio
import os, time
from pathlib import Path
from typing import Any
from aiohttp import web
from .types import RequestState
from .voiceguard import VoiceGuard

_UI_RUNNER: web.AppRunner | None = None

def _relative(ts: float) -> str:
    age = max(0, time.monotonic() - ts)
    if age < 1: return "just now"
    if age < 60: return f"{int(age)}s ago"
    return f"{int(age // 60)}m ago"

def _ui_event(event: Any) -> dict[str, Any]:
    p = dict(event.payload); kind = event.kind
    mapping = {
        "generated_text": "audio_generated",
        "audio_chunk_generated": "audio_generated",
        "audio_chunk_played": "audio_played",
        "audio_chunk_rejected": "audio_blocked",
        "interrupt": "interrupt",
        "constraint_diff": "constraint_diff",
        "interrupt_latency": "interrupt_latency",
        "request_started": "request_started",
        "request_completed": "request_completed",
        "ghost_task": "ghost_task",
        "state_changed": "state_changed",
        "tool_started": "tool_started",
        "tool_completed": "tool_completed",
        "tool_cancelled": "tool_cancelled",
    }
    ui_type = mapping.get(kind, kind)
    out = {
        "id": f"{kind}-{event.request_id}-{event.at:.6f}",
        "type": ui_type,
        "requestId": event.request_id,
        "timestamp": event.at,
    }
    if "user_text" in p: out["text"] = p["user_text"]
    if kind == "generated_text":
        out["detail"] = "LLM output generated"; out["metric"] = len(str(p.get("text", "")))
    elif kind in {"audio_chunk_generated", "audio_chunk_played", "audio_chunk_rejected"}:
        out["metric"] = 1
        if kind == "audio_chunk_rejected": out["detail"] = p.get("reason", "Audio was rejected")
    elif kind == "interrupt":
        out["detail"] = p.get("reason", "User interrupted")

    elif kind == "constraint_diff":
        out["previousRequestId"] = p.get("previous_request_id")
        out["oldText"] = p.get("old_text", "")
        out["newText"] = p.get("new_text", "")
        out["changes"] = p.get("changes", [])
        out["detail"] = "Request constraints changed"

    elif kind == "interrupt_latency":
        out["latencyMs"] = round(float(p.get("latency_ms", 0.0)), 2)
        out["detail"] = "Interrupt handling latency"

    elif kind == "ghost_task":
        stage = str(p.get("stage", "background task"))
        out["stage"] = stage
        out["detail"] = f"{stage.replace('_', ' ').title()} finished after supersession"
    elif kind == "tool_started":
        out["detail"] = "Tool execution started"
    elif kind == "tool_completed":
        out["detail"] = "Tool execution completed"
    elif kind == "tool_cancelled":
        out["detail"] = "Tool execution cancelled"
    elif "state" in p:
        out["detail"] = p["state"]
    elif "reason" in p:
        out["detail"] = p["reason"]
    return out

def build_snapshot(guard: VoiceGuard) -> dict[str, Any]:
    ledger_events = guard.ledger.timeline()
    events = []
    for e in ledger_events:
        events.append(_ui_event(e))
        if e.kind == "interrupt":
            events.append({
                "id": f"superseded-{e.request_id}-{e.at:.6f}",
                "type": "superseded",
                "requestId": e.request_id,
                "timestamp": e.at,
                "detail": "Request invalidated by a newer request",
            })
    interrupted = {e.request_id for e in ledger_events if e.kind == "interrupt"}
    request_ids = sorted({e.request_id for e in ledger_events if e.kind == "request_started"})
    requests = []
    for rid in request_ids:
        started = next(e for e in ledger_events if e.request_id == rid and e.kind == "request_started")
        if rid == guard.active_id:
            state = {RequestState.TOOL_RUNNING:"TOOL", RequestState.RESPONDING:"RESPONDING",
                     RequestState.THINKING:"THINKING", RequestState.LISTENING:"LISTENING",
                     RequestState.IDLE:"IDLE"}[guard.state]
        elif rid in interrupted:
            state = "SUPERSEDED"
        else:
            state = "THINKING"
        requests.append({"id":rid,"text":started.payload.get("user_text",""),"state":state,
                         "startedAt":started.at,"relative":_relative(started.at),"isCurrent":rid==guard.active_id})
    current = next((r for r in requests if r["isCurrent"]), None)
    metrics = {
        "requests": len(request_ids),
        "superseded": len(interrupted),
        "blocked": sum(e.get("metric",0) for e in events if e["type"]=="audio_blocked"),
        "heard": sum(e.get("metric",0) for e in events if e["type"]=="audio_played"),
        "ghostTasks": sum(1 for e in events if e["type"]=="ghost_task"),
        "generated": sum(e.get("metric",0) for e in events if e["type"]=="audio_generated"),
    }
    return {"currentRequest":current,"requests":requests,"events":events,"metrics":metrics,
            "demoStep":len(events),"isRunning":guard.active_id != 0,"serverTime":time.monotonic()}

async def _state(request: web.Request) -> web.Response:
    return web.json_response(build_snapshot(request.app["guard"]), headers={"Cache-Control":"no-store"})

async def _health(request: web.Request) -> web.Response:
    return web.json_response({"ok":True})

async def _start_demo(request: web.Request) -> web.Response:
    request.app["demo_start_event"].set()
    return web.json_response({"ok": True, "started": True})

async def _stop_demo(request: web.Request) -> web.Response:
    await request.app["stop_demo_callback"]()
    return web.json_response({"ok": True, "stopped": True})

async def _index(request: web.Request) -> web.StreamResponse:
    index = request.app["dist"] / "index.html"
    if index.exists(): return web.FileResponse(index)
    return web.json_response({"ok":True,"message":"VoiceGuard UI API is running. Build ui/ first."})

async def start_ui_server(
    guard: VoiceGuard,
    demo_start_event: asyncio.Event,
    stop_demo_callback,
) -> None:
    global _UI_RUNNER
    if _UI_RUNNER is not None: return
    dist = Path(__file__).resolve().parent.parent / "ui" / "dist"
    app = web.Application()
    app["guard"] = guard; app["dist"] = dist; app["demo_start_event"] = demo_start_event
    app["stop_demo_callback"] = stop_demo_callback
    async def cors(app, handler):
        async def middleware(request):
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        return middleware
    app.middlewares.append(cors)
    app.router.add_get("/api/state", _state)
    app.router.add_get("/api/health", _health)
    app.router.add_post("/api/start_demo", _start_demo)
    app.router.add_post("/api/stop_demo", _stop_demo)
    if dist.exists(): app.router.add_static("/assets", dist / "assets")
    app.router.add_get("/", _index)
    app.router.add_get("/{path:.*}", _index)
    _UI_RUNNER = web.AppRunner(app)
    await _UI_RUNNER.setup()
    await web.TCPSite(_UI_RUNNER, "127.0.0.1", int(os.getenv("VOICEGUARD_UI_PORT","8765"))).start()
