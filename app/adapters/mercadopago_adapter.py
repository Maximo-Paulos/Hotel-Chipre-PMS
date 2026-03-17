"""
MercadoPago Payment Adapter.
Wraps the MercadoPago SDK to create payment preferences and process IPN/webhooks.
"""
import json
from typing import Optional

from app.schemas.transaction import PaymentGatewayResponse
from app.config import get_settings


class MercadoPagoAdapter:
    """
    Service adapter for MercadoPago payment integration.
    Creates checkout preferences and processes webhook notifications.
    """

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or get_settings().MP_ACCESS_TOKEN
        self._sdk = None

    def _get_sdk(self):
        """Lazy-initialize the MercadoPago SDK."""
        if self._sdk is None:
            try:
                import mercadopago
                self._sdk = mercadopago.SDK(self.access_token)
            except ImportError:
                raise RuntimeError(
                    "mercadopago package not installed. Run: pip install mercadopago"
                )
        return self._sdk

    def create_preference(
        self,
        reservation_id: int,
        confirmation_code: str,
        amount: float,
        description: str,
        payer_email: str = "",
        currency: str = "ARS",
        back_urls: Optional[dict] = None,
        notification_url: Optional[str] = None,
    ) -> PaymentGatewayResponse:
        """
        Create a MercadoPago checkout preference.
        Returns a redirect URL for the customer to complete payment.
        """
        try:
            sdk = self._get_sdk()

            preference_data = {
                "items": [
                    {
                        "title": f"Reserva {confirmation_code} - {description}",
                        "quantity": 1,
                        "unit_price": float(amount),
                        "currency_id": currency,
                    }
                ],
                "external_reference": str(reservation_id),
                "payer": {"email": payer_email} if payer_email else {},
            }

            if back_urls:
                preference_data["back_urls"] = back_urls
                preference_data["auto_return"] = "approved"

            if notification_url:
                preference_data["notification_url"] = notification_url

            result = sdk.preference().create(preference_data)
            response = result.get("response", {})

            if result.get("status") in (200, 201):
                return PaymentGatewayResponse(
                    success=True,
                    external_payment_id=str(response.get("id", "")),
                    external_status="created",
                    redirect_url=response.get("init_point", ""),
                    gateway_response=json.dumps(response),
                )
            else:
                return PaymentGatewayResponse(
                    success=False,
                    error_message=f"MercadoPago error: {result}",
                    gateway_response=json.dumps(result),
                )

        except Exception as e:
            return PaymentGatewayResponse(
                success=False,
                error_message=f"MercadoPago adapter error: {str(e)}",
            )

    def process_webhook(self, data: dict) -> PaymentGatewayResponse:
        """
        Process an IPN (Instant Payment Notification) from MercadoPago.
        Queries the payment status from the API.
        """
        try:
            sdk = self._get_sdk()
            payment_id = data.get("data", {}).get("id")

            if not payment_id:
                return PaymentGatewayResponse(
                    success=False,
                    error_message="No payment ID in webhook data",
                )

            result = sdk.payment().get(payment_id)
            response = result.get("response", {})

            status = response.get("status", "")
            is_approved = status == "approved"

            return PaymentGatewayResponse(
                success=is_approved,
                external_payment_id=str(payment_id),
                external_status=status,
                gateway_response=json.dumps(response),
                error_message=None if is_approved else f"Payment status: {status}",
            )

        except Exception as e:
            return PaymentGatewayResponse(
                success=False,
                error_message=f"MercadoPago webhook error: {str(e)}",
            )


# Singleton-style factory
_adapter_instance: Optional[MercadoPagoAdapter] = None


def get_mercadopago_adapter() -> MercadoPagoAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MercadoPagoAdapter()
    return _adapter_instance
