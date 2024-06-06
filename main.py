from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict
import time
import asyncio

app = FastAPI()
white_list_ids = [1, 2]
host = "https://fastapi-production-53df.up.railway.app"

class ConnectionManager:
    def __init__(self, id_list):
        self.id_list = id_list
        self.active_connections: Dict[int, WebSocket] = {}
        self.request_times: Dict[int, float] = {}
        self.last_response_time: float = 0
        self.response_sent = {x: False for x in self.id_list}

    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.request_times[client_id] = time.time()

    def disconnect(self, client_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del self.request_times[client_id]

    async def check_and_send_response(self):
        current_time = time.time()
        id_request_check = all(id in self.request_times for id in self.id_list)
        response_check = all(value == False for value in self.response_sent.values())
        if (
                id_request_check and
                (self.last_response_time != current_time) and
                response_check
        ):
            ts_now = str(datetime.utcnow())
            response = {"status": "signal", "ts": ts_now, "order": "market_buy", "symbol": "XAUUSD", "volume": 0.01}
            [await conn.send_json(response) for conn in self.active_connections.values()]

            self.response_sent = {x: True for x in self.id_list}
            self.last_response_time = current_time
            await asyncio.sleep(1)  # Silent for 1000 milliseconds (1 second)
            self.response_sent = {x: False for x in self.id_list}


manager = ConnectionManager(id_list=white_list_ids)


@app.get("/")
async def root():
    return {"greeting": "Hello, World!", "message": "Welcome to Strategy server!"}

@app.websocket("/ws/{client_id}")

async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()
            manager.request_times[client_id] = time.time()
            await manager.check_and_send_response()
    except WebSocketDisconnect:
        manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=host, port=8000)

""" uvicorn main:app --reload 
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
