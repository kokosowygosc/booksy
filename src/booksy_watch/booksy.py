"""Booksy HTTP client. Reverse-engineered consumer API.

Endpoints discovered:
  GET  {API}/2/customer_api/businesses/{business_id}
  POST {API}/2/customer_api/me/businesses/{business_id}/time_slots/

Where API = https://{country}.booksy.com/api/{country}

No auth required for reads. Only the public web app's x-api-key is needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

API_KEY = "web-e3d812bf-d7a2-445d-ab38-55589ae6a121"
API_VERSION = "X"
DEFAULT_COUNTRY = "pl"

URL_BUSINESS_ID_RE = re.compile(r"booksy\.com/[^/]+/(\d+)_")


def parse_business_id(url: str) -> int:
    """Extract numeric business id from a Booksy salon URL."""
    m = URL_BUSINESS_ID_RE.search(url)
    if not m:
        raise ValueError(f"Cannot parse business id from URL: {url}")
    return int(m.group(1))


def parse_country(url: str) -> str:
    """Extract country code from URL path, e.g. /pl-pl/ -> pl."""
    m = re.search(r"booksy\.com/([a-z]{2})-[a-z]{2}/", url)
    return m.group(1) if m else DEFAULT_COUNTRY


@dataclass(slots=True)
class ServiceVariant:
    variant_id: int
    duration: int
    price: float
    staffer_ids: list[int]


@dataclass(slots=True)
class Service:
    service_id: int
    name: str
    variants: list[ServiceVariant]

    @property
    def display(self) -> str:
        price = self.variants[0].price if self.variants else 0
        return f"{self.name}  ({price:.0f} zł, {self.variants[0].duration}min)"


@dataclass(slots=True)
class Staffer:
    staffer_id: int
    name: str


@dataclass(slots=True)
class Business:
    business_id: int
    name: str
    services: list[Service]
    staff: list[Staffer]

    def staffer_name(self, staffer_id: int | None) -> str:
        if staffer_id is None:
            return "any staffer"
        for s in self.staff:
            if s.staffer_id == staffer_id:
                return s.name
        return f"staffer {staffer_id}"

    def service_by_variant(self, variant_id: int) -> Service | None:
        for svc in self.services:
            for v in svc.variants:
                if v.variant_id == variant_id:
                    return svc
        return None


@dataclass(slots=True, frozen=True, order=True)
class Slot:
    when: datetime  # local time at salon (no tz info)


class BooksyClient:
    def __init__(self, country: str = DEFAULT_COUNTRY, timeout: float = 15.0) -> None:
        self.country = country
        base = f"https://{country}.booksy.com/api/{country}"
        self._client = httpx.Client(
            base_url=base,
            timeout=timeout,
            headers={
                "x-api-key": API_KEY,
                "x-version": API_VERSION,
                "accept-language": f"{country}-{country.upper()}",
                "user-agent": "Mozilla/5.0 booksy-watch/0.1",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BooksyClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get_business(self, business_id: int) -> Business:
        r = self._client.get(f"/2/customer_api/businesses/{business_id}")
        r.raise_for_status()
        data = r.json()["business"]
        services: list[Service] = []
        for cat in data.get("service_categories", []):
            for svc in cat.get("services", []):
                if not svc.get("is_available_for_customer_booking", True):
                    continue
                variants = [
                    ServiceVariant(
                        variant_id=v["id"],
                        duration=v.get("duration", 0),
                        price=float(v.get("price", 0) or 0),
                        staffer_ids=list(v.get("staffer_id", []) or []),
                    )
                    for v in svc.get("variants", [])
                ]
                if not variants:
                    continue
                services.append(
                    Service(
                        service_id=svc["id"],
                        name=svc.get("name", "?"),
                        variants=variants,
                    )
                )
        staff = [
            Staffer(staffer_id=s["id"], name=s.get("name", "?"))
            for s in data.get("staff", [])
        ]
        return Business(
            business_id=data["id"],
            name=data.get("name", "?"),
            services=services,
            staff=staff,
        )

    def get_time_slots(
        self,
        business_id: int,
        service_variant_id: int,
        start: date,
        end: date,
        staffer_id: int | None = None,
    ) -> list[Slot]:
        """Return all slots sorted ascending. Filters by staffer if given.

        Note: the API ignores per-staffer filtering in the request body; it
        returns the union of available slots across all staffers for the variant.
        Variants are normally tied to a single staffer (see ``variant.staffer_ids``),
        so picking the right variant is how you scope per-person.
        """
        body = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "service_variant_ids": [service_variant_id],
        }
        r = self._client.post(
            f"/2/customer_api/me/businesses/{business_id}/time_slots/",
            json=body,
        )
        r.raise_for_status()
        raw = r.json().get("timeslots", {}).get(str(service_variant_id), {})
        slots: list[Slot] = []
        for day_str, entries in raw.items():
            try:
                d = date.fromisoformat(day_str)
            except ValueError:
                continue
            for entry in entries:
                minutes = int(entry["t"])
                slots.append(Slot(when=datetime.combine(d, datetime.min.time()) + timedelta(minutes=minutes)))
        slots.sort()
        return slots
