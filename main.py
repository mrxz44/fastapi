from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from typing import Dict, Optional
import time
import asyncio
import ssl
import json


white_list_ids = [1, 2]
app = FastAPI()
templates = Jinja2Templates(directory="templates")  # Directory containing HTML templates
security = HTTPBasic()

# Create a password context with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Set admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = pwd_context.hash("admin_password")  # Hash your admin password here

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username == ADMIN_USERNAME and pwd_context.verify(credentials.password, ADMIN_PASSWORD_HASH):
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

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

@app.get("/")
async def read_root(request: Request, authenticated: bool = Depends(authenticate)):
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "response_message": json.dumps(manager.response_message),
        "sleep_duration": manager.sleep_duration
    })

@app.post("/update_config")
async def update_config(request: Request, response_message: str = Form(...), sleep_duration: float = Form(...), authenticated: bool = Depends(authenticate)):
    manager.response_message = json.loads(response_message)
    manager.sleep_duration = sleep_duration
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "response_message": json.dumps(manager.response_message),
        "sleep_duration": manager.sleep_duration,
        "message": "Configuration updated successfully"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

""" uvicorn main:app --reload 
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
