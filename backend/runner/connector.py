import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

try:
    import websockets
except ImportError:
    # Optional dependency for the runner
    websockets = None

logger = logging.getLogger(__name__)

RunnerActionHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


def _get_account_name(payload: Dict[str, Any]) -> str | None:
    account = payload.get("account")
    if not isinstance(account, str):
        return None
    account = account.strip()
    return account or None


def _get_request_id(payload: Dict[str, Any]) -> str | None:
    request_id = payload.get("request_id")
    if not isinstance(request_id, str):
        return None
    request_id = request_id.strip()
    if not request_id or len(request_id) > 128:
        return None
    return request_id


def _log_safe_ws_url(target_ws_url: str) -> str:
    parts = urlsplit(target_ws_url)
    path_parts = [part for part in parts.path.split("/") if part]
    if path_parts:
        path_parts[-1] = "[redacted]"
    safe_path = "/" + "/".join(path_parts) if path_parts else parts.path
    return urlunsplit((parts.scheme, parts.netloc, safe_path, "", ""))


class SelfHostedConnector:
    def __init__(
        self,
        target_ws_url: str,
        token: str,
        *,
        imap_fetch_handler: RunnerActionHandler | None = None,
        smtp_send_handler: RunnerActionHandler | None = None,
        webdav_write_handler: RunnerActionHandler | None = None,
        caldav_write_handler: RunnerActionHandler | None = None,
    ):
        self.target_ws_url = target_ws_url
        self.token = token
        self.imap_fetch_handler = imap_fetch_handler
        self.smtp_send_handler = smtp_send_handler
        self.webdav_write_handler = webdav_write_handler
        self.caldav_write_handler = caldav_write_handler
        self.connection = None
        self.is_connected = False
        
    async def connect(self):
        if websockets is None:
            logger.error("websockets library is not installed. Runner cannot start.")
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            self.connection = await websockets.connect(self.target_ws_url, additional_headers=headers)
            self.is_connected = True
            logger.info(
                "Connected to Naruon Gateway at %s",
                _log_safe_ws_url(self.target_ws_url),
            )
            await self._listen_loop()
        except asyncio.CancelledError:
            raise
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            self.is_connected = False
            logger.exception(f"Failed to connect to Naruon Gateway: {e}")
        except Exception as e:
            # We catch Exception here but limit logger.exception to websocket errors
            # to avoid referencing websockets.exceptions directly in the tuple
            # in case websockets is None (though we return early if it is)
            if websockets and isinstance(e, websockets.exceptions.WebSocketException):
                self.is_connected = False
                logger.exception(f"Failed to connect to Naruon Gateway: {e}")
            else:
                self.is_connected = False
                logger.exception(f"Failed to connect to Naruon Gateway with unexpected error: {e}")

    async def _listen_loop(self):
        if not self.connection:
            return
        try:
            while self.is_connected:
                message = await self.connection.recv()
                await self.handle_message(message)
        except Exception as e:
            if websockets and isinstance(e, websockets.exceptions.ConnectionClosed):
                logger.warning("Connection closed by remote gateway.")
            else:
                logger.warning(f"Connection loop ended: {e}")
            self.is_connected = False
            
    async def handle_message(self, message: str | bytes):
        # Dispatch message to internal SMTP/IMAP proxy handlers
        logger.debug("Received instruction from gateway.")
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.error("Failed to decode message from gateway.")
            await self.send_response({
                "status": "error",
                "action": None,
                "error": "invalid json",
            })
            return

        if not isinstance(payload, dict):
            logger.error("Gateway instruction payload must be an object.")
            await self.send_response({
                "status": "error",
                "action": None,
                "error": "invalid payload",
            })
            return

        action = payload.get("action")
        if action == "fetch_imap":
            await self._handle_fetch_imap(payload)
        elif action == "send_smtp":
            await self._handle_send_smtp(payload)
        elif action == "write_webdav":
            await self._handle_write_webdav(payload)
        elif action == "write_caldav":
            await self._handle_write_caldav(payload)
        else:
            logger.info("Unknown action received.")
            await self.send_response({
                "status": "error",
                "action": action if isinstance(action, str) else None,
                "error": "unknown action",
            })
            
    async def _handle_fetch_imap(self, payload: Dict[str, Any]):
        if _get_account_name(payload) is None:
            logger.error("IMAP fetch instruction is missing account.")
            await self.send_response({
                "status": "error",
                "action": "fetch_imap",
                "error": "missing account",
            })
            return
        logger.info("Dispatching local IMAP fetch adapter for configured account.")
        await self._execute_local_adapter(
            action="fetch_imap",
            protocol="IMAP",
            payload=payload,
            handler=self.imap_fetch_handler,
        )
        
    async def _handle_send_smtp(self, payload: Dict[str, Any]):
        if _get_account_name(payload) is None:
            logger.error("SMTP send instruction is missing account.")
            await self.send_response({
                "status": "error",
                "action": "send_smtp",
                "error": "missing account",
            })
            return
        logger.info("Dispatching local SMTP send adapter for configured account.")
        await self._execute_local_adapter(
            action="send_smtp",
            protocol="SMTP",
            payload=payload,
            handler=self.smtp_send_handler,
        )

    async def _handle_write_webdav(self, payload: Dict[str, Any]):
        if _get_account_name(payload) is None:
            logger.error("WebDAV write instruction is missing account.")
            await self.send_response({
                "status": "error",
                "action": "write_webdav",
                "error": "missing account",
            })
            return
        logger.info("Dispatching local WebDAV write adapter for configured account.")
        await self._execute_local_adapter(
            action="write_webdav",
            protocol="WebDAV",
            payload=payload,
            handler=self.webdav_write_handler,
        )

    async def _handle_write_caldav(self, payload: Dict[str, Any]):
        if _get_account_name(payload) is None:
            logger.error("CalDAV write instruction is missing account.")
            await self.send_response({
                "status": "error",
                "action": "write_caldav",
                "error": "missing account",
            })
            return
        logger.info("Dispatching local CalDAV write adapter for configured account.")
        await self._execute_local_adapter(
            action="write_caldav",
            protocol="CalDAV",
            payload=payload,
            handler=self.caldav_write_handler,
        )

    async def _execute_local_adapter(
        self,
        *,
        action: str,
        protocol: str,
        payload: Dict[str, Any],
        handler: RunnerActionHandler | None,
    ):
        account = _get_account_name(payload)
        response: Dict[str, Any] = {
            "status": "error",
            "action": action,
            "protocol": protocol,
            "account": account,
            "request_id": _get_request_id(payload),
            "provider_write_executed": False,
        }
        if account is None:
            response["error"] = "missing account"
            await self.send_response(response)
            return
        if handler is None:
            response["error"] = "adapter_not_configured"
            await self.send_response(response)
            return

        try:
            adapter_result = await handler(dict(payload))
        except Exception:
            logger.exception("%s local adapter failed.", protocol)
            response["error"] = "adapter_failed"
            await self.send_response(response)
            return

        if not isinstance(adapter_result, dict):
            response["error"] = "invalid_adapter_response"
            await self.send_response(response)
            return

        status_value = adapter_result.get("status", "success")
        response["status"] = status_value if isinstance(status_value, str) else "success"
        response["provider_write_executed"] = bool(
            adapter_result.get("provider_write_executed", False)
        )
        reserved_keys = {
            "action",
            "account",
            "protocol",
            "request_id",
            "provider_write_executed",
        }
        for key, value in adapter_result.items():
            if key in reserved_keys:
                continue
            response[key] = value
        await self.send_response(response)

    async def send_response(self, response: Dict[str, Any]):
        if self.is_connected and self.connection:
            await self.connection.send(json.dumps(response))

if __name__ == "__main__":
    # Example usage for local bootstrap
    connector = SelfHostedConnector("ws://localhost:8080/api/runner/ws", "sample-token")
    asyncio.run(connector.connect())
