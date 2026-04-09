from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ZammadConfig:
    base_url: str
    api_token: str
    default_customer: str
    default_group: str


class ZammadClient:
    def __init__(self, config: ZammadConfig):
        self.config = config

    def create_ticket(
        self,
        *,
        title: str,
        body: str,
        customer: str | None = None,
        group: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "title": title,
            "group": group or self.config.default_group,
            "customer": customer or self.config.default_customer,
            "article": {
                "subject": title,
                "body": body,
                "type": "note",
                "internal": False,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/api/v1/tickets",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Token token={self.config.api_token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw or "{}")
                return {
                    "ok": True,
                    "ticket_id": parsed.get("id"),
                    "number": parsed.get("number"),
                    "raw": parsed,
                }
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="ignore")
            return {
                "ok": False,
                "error": f"HTTP {err.code}",
                "detail": detail,
            }
        except Exception as err:  # noqa: BLE001
            return {
                "ok": False,
                "error": "connection_error",
                "detail": str(err),
            }
