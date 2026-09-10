from types import SimpleNamespace

from app.services.ota.adapters.booking import BookingAdapter, BookingAdapterError
from app.services.ota.contracts import OTAAdapterContext


def _context(**overrides):
    values = {
        "hotel_id": 1,
        "provider_code": "booking",
        "external_property_id": "8011855",
        "auth_config": {"access_token": "booking-secret"},
    }
    values.update(overrides)
    return OTAAdapterContext(**values)


def _response(body: bytes, status_code: int = 200, content_type: str = "application/xml"):
    return SimpleNamespace(
        status_code=status_code,
        ok=status_code < 400,
        content=body,
        headers={"Content-Type": content_type},
    )


RESERVATIONS_XML = b"""
<OTA_HotelResNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05">
  <HotelReservations>
    <HotelReservation ResStatus="Commit">
      <RoomStays><RoomStay><RoomTypes><RoomType RoomTypeCode="DLX" /></RoomTypes>
        <TimeSpan Start="2026-10-01" End="2026-10-03" />
      </RoomStay></RoomStays>
      <ResGuests><ResGuest><Profiles><ProfileInfo><Profile><Customer><PersonName>
        <GivenName>Ana</GivenName><Surname>Perez</Surname>
      </PersonName></Customer></Profile></ProfileInfo></Profiles></ResGuest></ResGuests>
      <ResGlobalInfo>
        <HotelReservationIDs><HotelReservationID ResID_Value="bk-1" /></HotelReservationIDs>
        <Total AmountAfterTax="120.00" CurrencyCode="ARS" />
      </ResGlobalInfo>
    </HotelReservation>
  </HotelReservations>
</OTA_HotelResNotifRQ>
"""


def test_booking_adapter_requires_token_and_property_before_transport():
    calls = []
    adapter = BookingAdapter(lambda *args, **kwargs: calls.append((args, kwargs)))

    result = adapter.verify_connection(_context(auth_config={}))

    assert result.success is False
    assert "token" in result.message.lower()
    assert calls == []


def test_booking_adapter_normalizes_xml_reservations_and_deduplicates():
    adapter = BookingAdapter(lambda *args, **kwargs: _response(RESERVATIONS_XML))

    reservations = adapter.pull_new_reservations(_context())

    assert len(reservations) == 1
    assert reservations[0].external_reservation_id == "bk-1"
    assert reservations[0].guest_full_name == "Ana Perez"
    assert reservations[0].sellable_product_code == "DLX"
    assert reservations[0].gross_total == 120.0


def test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence():
    captured = {}

    def requester(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return _response(b"<response><success /></response>")

    adapter = BookingAdapter(requester)
    result = adapter.push_inventory(
        _context(),
        {"currency": "ARS", "updates": [{"room_id": "101", "rate_id": "9", "date": "2026-10-01", "roomstosell": 2}]},
    )

    assert result.success is True
    assert captured["url"].endswith("/hotels/xml/availability")
    assert captured["headers"]["Authorization"] == "Bearer booking-secret"
    assert b"room id=\"101\"" in captured["data"]
    assert b"roomstosell=\"2\"" in captured["data"]
    assert "booking-secret" not in (result.raw_request or "")


def test_booking_adapter_surfaces_retryable_provider_outage():
    adapter = BookingAdapter(lambda *args, **kwargs: _response(b"busy", status_code=503, content_type="text/plain"))

    result = adapter.verify_connection(_context())

    assert result.success is False
    assert result.retryable is True
    assert result.http_status == 503
    assert "reintent" in result.message.lower()


def test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit():
    captured = {}

    def requester(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return _response(b"<response><success /></response>")

    adapter = BookingAdapter(requester)
    result = adapter.acknowledge_reservations(_context(), ["bk-1"])

    assert result.success is True
    assert captured["method"] == "POST"
    assert b'ResID_Value="bk-1"' in captured["data"]
    unsupported = adapter.cancel_reservation(_context(), "bk-1")
    assert unsupported.success is False
    assert unsupported.retryable is False
    assert "salientes" in unsupported.message


def test_booking_adapter_does_not_treat_failed_pull_as_empty_queue():
    adapter = BookingAdapter(lambda *args, **kwargs: _response(b"busy", status_code=500, content_type="text/plain"))

    try:
        adapter.pull_new_reservations(_context())
    except BookingAdapterError as exc:
        assert "disponible" in str(exc).lower()
    else:
        raise AssertionError("A provider failure must not be reported as an empty reservation queue")
