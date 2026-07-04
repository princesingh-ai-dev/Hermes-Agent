# hermes/api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from hermes.core.idle_loop import IdleManager
from hermes.graph.graph import hermes_graph
from hermes.tools.registry import TOOL_REGISTRY
from hermes.memory.chroma_store import HermesMemory
from hermes.tools.obsidian import obsidian_write, obsidian_search

idle_manager = IdleManager(interval_seconds=15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    idle_manager.start()
    yield
    idle_manager.stop()

app = FastAPI(title="Hermes Agent API", version="0.17.0", lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    task_type: str = "auto"
    stream: bool = True

async def stream_hermes_response(req: ChatRequest):
    """SSE streaming from LangGraph."""
    async for chunk in hermes_graph.astream(
        {"messages": [{"role": "user", "content": req.message}], "task_type": req.task_type},
        config={"configurable": {"thread_id": req.session_id}}
    ):
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/chat")
async def chat(req: ChatRequest):
    """Main chat endpoint with model routing and tool use."""
    if req.stream:
        return StreamingResponse(
            stream_hermes_response(req),
            media_type="text/event-stream"
        )
    result = await hermes_graph.ainvoke(
        {"messages": [{"role": "user", "content": req.message}], "task_type": req.task_type},
        config={"configurable": {"thread_id": req.session_id}}
    )
    return {"response": result}

@app.get("/memory/search")
async def search_memory(q: str):
    """Semantic search over Hermes's long-term memory."""
    memory_store = HermesMemory()
    return memory_store.recall(q)

@app.get("/tools")
async def list_tools():
    """List all available tools."""
    return [t.name for t in TOOL_REGISTRY]

@app.post("/obsidian/write")
async def write_obsidian(note: str, content: str):
    return obsidian_write.invoke({"note_name": note, "content": content})

@app.get("/obsidian/search")
async def search_obsidian(q: str):
    return obsidian_search.invoke({"query": q})
