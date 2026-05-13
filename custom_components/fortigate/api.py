"""Low-level FortiGate REST API client (FortiOS JSON API)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class FortigateAuthError(Exception):
    """Invalid token or insufficient permissions."""


class FortigateConnectionError(Exception):
    """Unreachable host, TLS failure, or timeout."""


class FortigateApiError(Exception):
    """API returned an error payload."""


class FortigateClient:
    """HTTP client for FortiOS monitor/cmdb paths.

    Authentication uses the official query parameter ``access_token`` (REST API
    admin). Session/cookie login is not implemented here; token auth is the
    best fit for Home Assistant config entries.
    """

    def __init__(
        self,
        hass,
        host: str,
        port: int,
        access_token: str,
        *,
        vdom: str,
        api_prefix: str,
        verify_ssl: bool,
    ) -> None:
        self._hass = hass
        self._host = host.rstrip("/")
        self._port = port
        self._token = access_token
        self._vdom = vdom
        self._api_prefix = api_prefix.strip("/")
        self._verify_ssl = verify_ssl

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def _base_url(self) -> str:
        return f"https://{self._host}:{self._port}"

    def _build_url(self, path: str, extra_params: dict[str, Any] | None = None) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        params: dict[str, Any] = {"access_token": self._token}
        if self._vdom:
            params["vdom"] = self._vdom
        if extra_params:
            for k, v in extra_params.items():
                if v is not None:
                    params[k] = v
        qs = urlencode(params, quote_via=quote, safe="")
        return f"{self._base_url()}{path}?{qs}"

    async def get_json(self, path: str, extra_params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._build_url(path, extra_params)
        session = async_get_clientsession(self._hass)
        ssl_param: bool | aiohttp.Fingerprint = self._verify_ssl
        if not self._verify_ssl:
            ssl_param = False
        try:
            async with session.get(url, ssl=ssl_param, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status in (401, 403):
                    raise FortigateAuthError(f"HTTP {resp.status}")
                if resp.status != 200:
                    err_body = (await resp.text())[:500]
                    raise FortigateApiError(f"HTTP {resp.status}: {err_body}")
                try:
                    data: dict[str, Any] = await resp.json()
                except aiohttp.ContentTypeError as err:
                    raise FortigateApiError("Response is not JSON") from err
        except aiohttp.ClientError as err:
            raise FortigateConnectionError(str(err)) from err

        if data.get("status") == "error":
            raise FortigateApiError(data.get("message") or str(data)[:200])
        return data

    async def validate(self) -> dict[str, Any]:
        """Lightweight call used during config flow (works on 6.x–7.x)."""
        path = f"/api/{self._api_prefix}/monitor/web-ui/state"
        return await self.get_json(path)

    async def get_monitor_interfaces(self) -> dict[str, Any]:
        path = f"/api/{self._api_prefix}/monitor/system/interface"
        return await self.get_json(path)

    async def get_monitor_resource_usage(self) -> dict[str, Any]:
        path = f"/api/{self._api_prefix}/monitor/system/resource/usage"
        return await self.get_json(path)

    async def get_monitor_sdwan_health(self) -> dict[str, Any]:
        path = f"/api/{self._api_prefix}/monitor/virtual-wan/health-check"
        return await self.get_json(path)

    async def put_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """PUT JSON body (e.g. CMDB interface status)."""
        url = self._build_url(path)
        session = async_get_clientsession(self._hass)
        ssl_param: bool | aiohttp.Fingerprint = self._verify_ssl
        if not self._verify_ssl:
            ssl_param = False
        headers = {"Content-Type": "application/json"}
        try:
            async with session.put(
                url,
                json=body,
                headers=headers,
                ssl=ssl_param,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise FortigateAuthError(f"HTTP {resp.status}")
                if resp.status != 200:
                    err_body = (await resp.text())[:500]
                    raise FortigateApiError(f"HTTP {resp.status}: {err_body}")
                try:
                    data: dict[str, Any] = await resp.json()
                except aiohttp.ContentTypeError as err:
                    raise FortigateApiError("Response is not JSON") from err
        except aiohttp.ClientError as err:
            raise FortigateConnectionError(str(err)) from err

        if data.get("status") == "error":
            raise FortigateApiError(data.get("message") or str(data)[:200])
        return data

    async def set_interface_admin_status(self, interface_name: str, up: bool) -> dict[str, Any]:
        """Bring interface administratively up or down (CMDB)."""
        status = "up" if up else "down"
        path = f"/api/{self._api_prefix}/cmdb/system/interface/{quote(str(interface_name), safe='')}"
        return await self.put_json(path, {"status": status})
