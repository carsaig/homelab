"""codemunch gateway — ONE MCP endpoint that merges codemunch's code tools with
our repo-lifecycle tools, without touching codemunch's source.

Why a gateway (not two Bifrost endpoints, not a fork):
  * mcp-proxy keeps `codemunch-core` (jcodemunch-mcp serve) warm as a stdio
    server — so codemunch's index stays hot between calls.
  * This gateway is the ONLY server Caddy exposes. It advertises codemunch-core's
    full tool surface PLUS fetch_repo/clear_repo/repo_status, and forwards any
    non-local call to codemunch-core over loopback. codemunch stays an unmodified
    pinned dependency (zero drift); the LLM sees one merged toolset at one URL
    (mcp.<your-domain>/codemunch).

Lifecycle contract (unchanged): single slot at /data/workspace/current, async
clone→index_folder→embed_repo, persisted status.json state machine, reject a
second fetch while loaded, fail closed on restart mid-index.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Long index/embed calls on a big repo can run for HOURS (a 100k-symbol repo
# embeds for ~3h on a 2-thread onnxruntime), and the SSE stream from
# codemunch-core is silent throughout (mcp-proxy does not forward codemunch's
# progress notifications, and requesting them causes stdio backpressure that
# stalls embedding — so we do NOT request them). A very generous sse_read_timeout
# is therefore the keep-alive: the client simply waits out the whole call.
# Tune via CODEMUNCH_LONG_CALL_TIMEOUT_HOURS if a repo ever needs even longer.
_LONG_CALL_HOURS = float(os.environ.get("CODEMUNCH_LONG_CALL_TIMEOUT_HOURS", "12"))
_SSE_READ_TIMEOUT = timedelta(hours=_LONG_CALL_HOURS)
_HTTP_TIMEOUT = timedelta(seconds=30)
_LONG_REQUEST_TIMEOUT = timedelta(hours=_LONG_CALL_HOURS + 1)


# ── Paths & config (overridable via env; defaults match the Dockerfile) ──────

DATA_ROOT = Path(os.environ.get("CODEMUNCH_DATA_ROOT", "/data"))
WORKSPACE = Path(os.environ.get("CODEMUNCH_WORKSPACE", str(DATA_ROOT / "workspace" / "current")))
INDEX_DIR = Path(os.environ.get("CODE_INDEX_PATH", str(DATA_ROOT / "code-index")))
STATUS_FILE = Path(os.environ.get("CODEMUNCH_STATUS_FILE", str(DATA_ROOT / "status.json")))

# codemunch-core's warm endpoint behind the same mcp-proxy, over loopback. A
# fresh session per call is cheap here — mcp-proxy keeps the stdio subprocess
# hot, so this never respawns codemunch, and each call gets clean isolation.
CORE_URL = os.environ.get(
    "CODEMUNCH_CORE_URL", "http://127.0.0.1:9090/servers/codemunch-core/mcp"
)

_FETCHABLE = {"empty", "failed"}
_IN_FLIGHT = {"cloning", "indexing", "embedding"}
_URL_RE = re.compile(r"^https://[A-Za-z0-9.\-]+/[A-Za-z0-9._\-/]+?(?:\.git)?/?$")

_task: Optional[asyncio.Task] = None

# Our locally-handled tools (everything else is forwarded to codemunch-core).
_OUR_TOOLS: list[types.Tool] = [
    types.Tool(
        name="fetch_repo",
        description=(
            "Clone a PUBLIC git repo into the single slot and index it in the "
            "background for codemunch to read. Returns immediately — poll "
            "repo_status until state == 'ready'. Refuses if a repo is already "
            "loaded or indexing; call clear_repo first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string",
                        "description": "https git URL of a public repo, e.g. https://github.com/owner/repo"},
                "ref": {"type": "string",
                        "description": "optional branch or tag (default: the repo's default branch)"},
            },
            "required": ["url"],
        },
    ),
    types.Tool(
        name="clear_repo",
        description=("Wipe the current repo and codemunch's index from the volume, "
                     "freeing the slot. Refuses while a fetch/index is in flight."),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="repo_status",
        description=("Report the repo lifecycle state (empty/cloning/indexing/"
                     "embedding/ready/failed) with repo URL, repo_id, commit, "
                     "symbol/file counts, live progress (progress_done/"
                     "progress_total) and eta_seconds during indexing/embedding, "
                     "and any error. Poll this to track a fetch."),
        inputSchema={"type": "object", "properties": {}},
    ),
]
_OUR_NAMES = {t.name for t in _OUR_TOOLS}


# ── status.json helpers ─────────────────────────────────────────────────────

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_status() -> dict[str, Any]:
    try:
        return json.loads(STATUS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"state": "empty", "repo": None, "ref": None, "path": None,
                "commit": None, "repo_id": None, "symbol_count": None,
                "file_count": None, "languages": None, "progress_done": None,
                "progress_total": None, "eta_seconds": None, "updated_at": None,
                "error": None}


def _write_status(**fields: Any) -> dict[str, Any]:
    cur = _read_status()
    cur.update(fields)
    cur["updated_at"] = _now()
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cur, indent=2))
    tmp.replace(STATUS_FILE)  # atomic — a torn write can never be read as valid
    return cur


def _reconcile_on_boot() -> None:
    """Fail closed: a non-terminal state with no live task means we crashed."""
    st = _read_status()
    if st.get("state") in _IN_FLIGHT:
        _write_status(state="failed",
                      error="process restarted mid-index; call clear_repo then re-fetch")


# tool_surface=full pins the whole tool set visible (see entrypoint). _wipe_slot
# rewrites it after nuking the index dir.
_CONFIG_JSONC = '{\n  "tool_surface": "full",\n  "tool_profile": "full"\n}\n'


def _wipe_slot() -> None:
    """Nuke the clone AND codemunch's ENTIRE index dir, recreate both, and
    rewrite config.jsonc. A full rm -rf (not a piecemeal per-entry wipe) is
    deliberate: leftover 0-byte DBs / file-cache dirs from an interrupted run
    made codemunch's next index fail with 'no such table: symbols'. The baked
    ONNX model lives in /opt, never under /data, so it is untouched."""
    for d in (WORKSPACE, INDEX_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "config.jsonc").write_text(_CONFIG_JSONC)


# ── codemunch-core client (stable public MCP tools only) ─────────────────────

async def _core_call(
    tool: str,
    args: dict[str, Any],
    long: bool = False,
) -> tuple[bool, list[types.ContentBlock], str]:
    """Call one codemunch-core tool. Returns (is_error, content_blocks, text).

    We deliberately do NOT request progress notifications (mcp-proxy drops them
    and they cause stdio backpressure). `long` widens the request timeout for
    big-repo index/embed; the generous sse_read_timeout keeps the silent stream
    alive for the whole call.
    """
    async with streamablehttp_client(
        CORE_URL, timeout=_HTTP_TIMEOUT, sse_read_timeout=_SSE_READ_TIMEOUT,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                tool, args,
                read_timeout_seconds=_LONG_REQUEST_TIMEOUT if long else None,
            )
            text = "\n".join(getattr(c, "text", "") for c in res.content)
            return bool(res.isError), list(res.content), text


def _embedded_count() -> Optional[int]:
    """Live count of embedded symbols, read straight from codemunch's index DB
    (single slot → one *.db under CODE_INDEX_PATH). Best-effort and read-only:
    if the schema ever changes, this returns None and progress simply goes quiet
    rather than breaking anything."""
    try:
        dbs = sorted(INDEX_DIR.glob("*.db"), key=lambda p: p.stat().st_size, reverse=True)
        if not dbs:
            return None
        con = sqlite3.connect(f"file:{dbs[0]}?mode=ro", uri=True, timeout=2)
        try:
            return con.execute("SELECT COUNT(*) FROM symbol_embeddings").fetchone()[0]
        finally:
            con.close()
    except Exception:  # noqa: BLE001 — progress is best-effort, never fatal
        return None


async def _estimate_embed_progress(total: Optional[int]) -> None:
    """Background ticker: while embed_repo runs, publish REAL progress by reading
    the growing symbol_embeddings count, with an ETA from the measured rate.
    Cancelled by the pipeline the moment embed_repo returns."""
    t0 = time.time()
    while True:
        await asyncio.sleep(5)
        done = _embedded_count()
        if done is None:
            continue  # DB not readable yet / schema drift → stay quiet
        elapsed = time.time() - t0
        rate = done / elapsed if elapsed > 0 else 0
        eta = int((total - done) / rate) if (rate > 0 and total and done < total) else None
        _write_status(state="embedding", progress_done=done,
                      progress_total=total, eta_seconds=eta)


async def _core_list_tools() -> list[types.Tool]:
    async with streamablehttp_client(CORE_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return list((await session.list_tools()).tools)


# ── background pipeline ──────────────────────────────────────────────────────

async def _pipeline(url: str, ref: Optional[str]) -> None:
    """clone -> index_folder -> embed_repo, advancing status.json as we go.
    index_folder(path) returns a repo id (owner/repo); downstream tools take
    that id, so we capture and surface it."""
    try:
        _wipe_slot()

        _write_status(state="cloning", repo=url, ref=ref, path=str(WORKSPACE),
                      commit=None, repo_id=None, symbol_count=None,
                      file_count=None, languages=None, error=None)
        clone_cmd = ["git", "clone", "--depth", "1"]
        if ref:
            clone_cmd += ["--branch", ref]
        clone_cmd += [url, str(WORKSPACE)]
        proc = await asyncio.create_subprocess_exec(
            *clone_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {out.decode(errors='replace')[-800:]}")

        commit = subprocess.run(
            ["git", "-C", str(WORKSPACE), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip() or None

        _write_status(state="indexing", commit=commit,
                      progress_done=None, progress_total=None, eta_seconds=None)
        err, _c, text = await _core_call("index_folder", {"path": str(WORKSPACE)}, long=True)
        if err:
            raise RuntimeError(f"index_folder failed: {text[:800]}")
        info = json.loads(text)
        repo_id = info.get("repo")
        if not repo_id:
            raise RuntimeError(f"index_folder returned no repo id: {text[:400]}")

        symbols = info.get("symbol_count")
        _write_status(state="embedding", repo_id=repo_id, symbol_count=symbols,
                      file_count=info.get("file_count"),
                      languages=info.get("languages"),
                      progress_done=0, progress_total=symbols, eta_seconds=None)
        # Approximate progress/ETA from a side ticker (mcp-proxy drops codemunch's
        # own progress notifications). The embed itself is a plain awaited call.
        estimator = asyncio.create_task(_estimate_embed_progress(symbols))
        try:
            err, _c, text = await _core_call("embed_repo", {"repo": repo_id}, long=True)
        finally:
            estimator.cancel()
        if err:
            raise RuntimeError(f"embed_repo failed: {text[:800]}")

        # embed_repo returns success even when every symbol's embedding call
        # errored (it just skips them). Fail loudly on a 0-embedding result —
        # otherwise we'd declare 'ready' over an empty semantic index (e.g. a
        # bad embedding VK/credential silently 401ing every request).
        try:
            emb = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            emb = {}
        if symbols and emb.get("symbols_embedded") == 0:
            raise RuntimeError(
                "embed produced 0 embeddings (provider=%s, skipped_error=%s) — "
                "check the embedding provider/credentials. %s"
                % (emb.get("provider"), emb.get("symbols_skipped_error"), text[:300]))

        _write_status(state="ready", error=None, progress_done=symbols,
                      progress_total=symbols, eta_seconds=0)
    except Exception as exc:  # noqa: BLE001 — any failure is a fail-closed status
        _write_status(state="failed", error=str(exc)[:1000])


# ── our tool handlers ────────────────────────────────────────────────────────

async def _do_fetch(url: str, ref: Optional[str]) -> str:
    global _task
    st = _read_status()
    state = st.get("state", "empty")
    if state not in _FETCHABLE:
        if state in _IN_FLIGHT:
            return f"Refused: a repo is currently {state} ({st.get('repo')}). Wait for it to finish or fail."
        return f"Refused: repo already loaded ({st.get('repo')}). Call clear_repo first, then fetch again."
    if not _URL_RE.match(url):
        return ("Refused: url must be a public https git URL, e.g. "
                "https://github.com/owner/repo (private repos are not supported).")
    _write_status(state="cloning", repo=url, ref=ref, path=str(WORKSPACE),
                  commit=None, repo_id=None, symbol_count=None,
                  file_count=None, languages=None, progress_done=None,
                  progress_total=None, eta_seconds=None, error=None)
    _task = asyncio.create_task(_pipeline(url, ref))
    return (f"Started fetching {url}" + (f" (ref {ref})" if ref else "")
            + ". Poll repo_status until state == 'ready'.")


async def _do_clear() -> str:
    st = _read_status()
    if st.get("state") in _IN_FLIGHT:
        return (f"Refused: {st.get('state')} in progress ({st.get('repo')}). "
                "Wait for repo_status to report 'ready' or 'failed', then clear.")
    # Drop codemunch-core's cached DB handle for the loaded repo BEFORE wiping
    # files — the warm process otherwise keeps a stale connection to the deleted
    # DB and the next index fails 'no such table'. invalidate_cache needs the
    # repo id (the old no-arg call was a silent no-op).
    repo_id = st.get("repo_id")
    if repo_id:
        try:
            await _core_call("invalidate_cache", {"repo": repo_id})
        except Exception:  # noqa: BLE001 — best-effort; the wipe below is authoritative
            pass
    _wipe_slot()
    _write_status(state="empty", repo=None, ref=None, path=None, commit=None,
                  repo_id=None, symbol_count=None, file_count=None,
                  languages=None, progress_done=None, progress_total=None,
                  eta_seconds=None, error=None)
    return "Cleared. Slot is empty; ready for the next fetch_repo."


# ── MCP server: merge + forward ──────────────────────────────────────────────

server = Server("codemunch")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Advertise codemunch-core's full surface plus our lifecycle tools."""
    try:
        core = await _core_list_tools()
    except Exception:  # noqa: BLE001 — if core is briefly unready, still expose ours
        core = []
    return core + _OUR_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
    if name == "fetch_repo":
        return [types.TextContent(type="text", text=await _do_fetch(
            arguments.get("url", ""), arguments.get("ref")))]
    if name == "clear_repo":
        return [types.TextContent(type="text", text=await _do_clear())]
    if name == "repo_status":
        return [types.TextContent(type="text", text=json.dumps(_read_status(), indent=2))]

    # Everything else is a codemunch-core tool — forward it verbatim.
    err, content, text = await _core_call(name, arguments)
    if err:
        # Re-raise so the framework returns a proper error result to the caller.
        raise RuntimeError(text or f"{name} failed")
    return content


async def _main() -> None:
    _reconcile_on_boot()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
