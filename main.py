from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import json
import os
import queue
import signal
import sys
import time
import threading
import webbrowser
from analyzer import detect_package_manager, launch_cleanup_terminal, launch_commands_terminal, perform_scan, get_live_stats, get_cleanup_commands
from terminal_session import start_session, get_active_session, stop_active_session

app = FastAPI(title="PC Analyzer Linux")

# Heartbeat tracking for auto-shutdown when browser closes
last_heartbeat = time.time()
shutdown_timer_started = False

def check_heartbeat():
    global last_heartbeat
    # Grace period at startup
    time.sleep(10)
    while True:
        time.sleep(2)
        if time.time() - last_heartbeat > 8:
            print("No active browser window detected (heartbeat timeout). Shutting down...")
            os.kill(os.getpid(), signal.SIGINT)
            break

@app.get("/api/scan")
def api_scan():
    try:
        return perform_scan()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def api_stats():
    try:
        return get_live_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cleanup")
def api_cleanup():
    try:
        if not launch_cleanup_terminal(detect_package_manager()):
            raise HTTPException(status_code=503, detail="No se encontró una terminal compatible.")
        return {"status": "terminal_opened"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_install_commands():
    """Install commands currently recommended (deduplicated, in order)."""
    recommendations = perform_scan().get("recommendations", [])
    return list(dict.fromkeys(
        recommendation["install_cmd"]
        for recommendation in recommendations
        if recommendation.get("install_cmd")
    ))


@app.get("/api/commands")
def api_commands(action: str = ""):
    """Deprecated: kept for reference. Use /api/terminal/start instead."""
    raise HTTPException(status_code=410, detail="Este endpoint ya no se usa. Usa /api/terminal/start.")


@app.post("/api/install-recommendations")
def api_install_recommendations():
    try:
        commands = get_install_commands()
        if not commands:
            raise HTTPException(status_code=404, detail="No hay paquetes disponibles para instalar.")
        if not launch_commands_terminal(commands, "instalación de paquetes recomendados"):
            raise HTTPException(status_code=503, detail="No se encontró una terminal compatible.")
        return {"status": "terminal_opened", "count": len(commands)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- In-app terminal (PTY) ----------

@app.post("/api/terminal/start")
def api_terminal_start(payload: dict):
    action = (payload.get("action") or "").strip().lower()
    if action == "cleanup":
        commands = get_cleanup_commands(detect_package_manager())
        title = "Limpieza y mantenimiento del sistema"
        if not commands:
            raise HTTPException(status_code=404, detail="No hay comandos disponibles para esta acción.")
    elif action == "install":
        commands = get_install_commands()
        title = "Instalación de paquetes recomendados"
        if not commands:
            raise HTTPException(status_code=404, detail="No hay paquetes disponibles para instalar.")
    else:
        raise HTTPException(status_code=400, detail="Acción no válida. Usa 'cleanup' o 'install'.")
    session = start_session(commands, title)
    return {"id": session.id, "title": session.title, "count": len(commands)}


@app.get("/api/terminal/events")
def api_terminal_events():
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="No hay sesión de terminal activa.")

    def _encode(kind, payload):
        if kind == "exit":
            return f"data: {json.dumps({'type': 'exit', 'code': payload})}\n\n"
        return f"data: {json.dumps({'type': 'output', 'data': payload})}\n\n"

    def event_stream():
        try:
            while True:
                if session.done:
                    # Drain any remaining output, then finish.
                    try:
                        kind, payload = session.output_q.get_nowait()
                        yield _encode(kind, payload)
                        continue
                    except queue.Empty:
                        break
                try:
                    kind, payload = session.output_q.get(timeout=15)
                except queue.Empty:
                    yield ": ping\n\n"
                    continue
                yield _encode(kind, payload)
                if kind == "exit":
                    break
        except GeneratorExit:
            # Client disconnected (e.g. page reload); the session keeps running.
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/terminal/input")
def api_terminal_input(payload: dict):
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="No hay sesión de terminal activa.")
    data = payload.get("data", "")
    accepted = session.write_input(data)
    return {"status": "ok" if accepted else "closed", "accepted": accepted}


@app.post("/api/terminal/stop")
def api_terminal_stop():
    stop_active_session()
    return {"status": "stopped"}

@app.post("/api/heartbeat")
def api_heartbeat():
    global last_heartbeat, shutdown_timer_started
    last_heartbeat = time.time()
    if not shutdown_timer_started:
        shutdown_timer_started = True
        threading.Thread(target=check_heartbeat, daemon=True).start()
    return {"status": "ok"}

@app.post("/api/shutdown")
def api_shutdown():
    print("Manual shutdown requested. Shutting down...")
    def target():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGINT)
    threading.Thread(target=target, daemon=True).start()
    return {"status": "shutting down"}

# Mount static folder for frontend assets
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)

@app.get("/", response_class=HTMLResponse)
def get_index():
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>PC Analyzer Linux</h1><p>Frontend assets are building...</p>")

app.mount("/static", StaticFiles(directory=static_path), name="static")

if __name__ == "__main__":
    import uvicorn
    
    # Open the default web browser automatically
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
