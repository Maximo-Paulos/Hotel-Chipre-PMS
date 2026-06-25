"""v72 §16.2: reportable_origin derivation from channel_code + company_id + source."""
from types import SimpleNamespace

import pytest

from app.models.reservation import (
    ReportableOriginEnum,
    ReservationChannelCodeEnum,
    ReservationSourceEnum,
    reportable_origin,
)


def _res(channel=None, company_id=None, source=ReservationSourceEnum.DIRECT):
    return SimpleNamespace(channel_code=channel, company_id=company_id, source=source)


@pytest.mark.parametrize(
    "channel,expected",
    [
        (ReservationChannelCodeEnum.WALK_IN, ReportableOriginEnum.MANUAL_RECEPCION),
        (ReservationChannelCodeEnum.PHONE, ReportableOriginEnum.TELEFONO),
        (ReservationChannelCodeEnum.WHATSAPP, ReportableOriginEnum.WHATSAPP_BOT),
        (ReservationChannelCodeEnum.WEBSITE_DIRECT, ReportableOriginEnum.WEB_PROPIA),
        (ReservationChannelCodeEnum.BOOKING, ReportableOriginEnum.BOOKING_MANUAL),
        (ReservationChannelCodeEnum.EXPEDIA, ReportableOriginEnum.EXPEDIA_MANUAL),
        (ReservationChannelCodeEnum.COMPANY, ReportableOriginEnum.EMPRESA),
    ],
)
def test_origin_from_channel(channel, expected):
    assert reportable_origin(_res(channel=channel)) is expected


def test_company_id_overrides_channel():
    # Even a website_direct channel reports as empresa when company_id is set.
    res = _res(channel=ReservationChannelCodeEnum.WEBSITE_DIRECT, company_id=42)
    assert reportable_origin(res) is ReportableOriginEnum.EMPRESA


def test_company_channel_is_empresa():
    res = _res(channel=ReservationChannelCodeEnum.COMPANY, company_id=None)
    assert reportable_origin(res) is ReportableOriginEnum.EMPRESA


def test_ota_source_fallback_when_channel_generic():
    booking = _res(channel=ReservationChannelCodeEnum.OTHER_OTA, source=ReservationSourceEnum.BOOKING)
    assert reportable_origin(booking) is ReportableOriginEnum.BOOKING_MANUAL

    expedia = _res(channel=ReservationChannelCodeEnum.OTHER_OTA, source=ReservationSourceEnum.EXPEDIA)
    assert reportable_origin(expedia) is ReportableOriginEnum.EXPEDIA_MANUAL


def test_unknown_channel_defaults_to_manual_reception():
    res = _res(channel=ReservationChannelCodeEnum.OTHER_DIRECT, source=ReservationSourceEnum.DIRECT)
    assert reportable_origin(res) is ReportableOriginEnum.MANUAL_RECEPCION
