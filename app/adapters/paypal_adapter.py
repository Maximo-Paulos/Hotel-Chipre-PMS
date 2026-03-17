"""
PayPal Payment Adapter.
Wraps the PayPal REST SDK to create orders and capture payments.
"""
import json
from typing import Optional

from app.schemas.transaction import PaymentGatewayResponse
from app.config import get_settings


class PayPalAdapter:
    """
    Service adapter for PayPal payment integration.
    Creates orders and processes webhooks/IPN notifications.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        settings = get_settings()
        self.client_id = client_id or settings.PAYPAL_CLIENT_ID
        self.client_secret = client_secret or settings.PAYPAL_CLIENT_SECRET
        self.mode = mode or settings.PAYPAL_MODE
        self._api = None

    def _get_api(self):
        """Lazy-initialize the PayPal API."""
        if self._api is None:
            try:
                import paypalrestsdk
                self._api = paypalrestsdk
                paypalrestsdk.configure({
                    "mode": self.mode,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                })
            except ImportError:
                raise RuntimeError(
                    "paypalrestsdk package not installed. Run: pip install paypalrestsdk"
                )
        return self._api

    def create_order(
        self,
        reservation_id: int,
        confirmation_code: str,
        amount: float,
        description: str,
        currency: str = "USD",
        return_url: str = "",
        cancel_url: str = "",
    ) -> PaymentGatewayResponse:
        """
        Create a PayPal payment (order).
        Returns a redirect URL for the customer to approve on PayPal.
        """
        try:
            api = self._get_api()

            payment = api.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
                "transactions": [
                    {
                        "item_list": {
                            "items": [
                                {
                                    "name": f"Reservation {confirmation_code}",
                                    "sku": str(reservation_id),
                                    "price": f"{amount:.2f}",
                                    "currency": currency,
                                    "quantity": 1,
                                }
                            ]
                        },
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency,
                        },
                        "description": description,
                    }
                ],
            })

            if payment.create():
                # Find approval URL
                approval_url = ""
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break

                return PaymentGatewayResponse(
                    success=True,
                    external_payment_id=payment.id,
                    external_status="created",
                    redirect_url=approval_url,
                    gateway_response=json.dumps(payment.to_dict()),
                )
            else:
                return PaymentGatewayResponse(
                    success=False,
                    error_message=f"PayPal error: {payment.error}",
                    gateway_response=json.dumps(payment.error) if payment.error else None,
                )

        except Exception as e:
            return PaymentGatewayResponse(
                success=False,
                error_message=f"PayPal adapter error: {str(e)}",
            )

    def execute_payment(
        self,
        payment_id: str,
        payer_id: str,
    ) -> PaymentGatewayResponse:
        """
        Execute (capture) a PayPal payment after customer approval.
        Called when customer returns from PayPal with paymentId and PayerID.
        """
        try:
            api = self._get_api()
            payment = api.Payment.find(payment_id)

            if payment.execute({"payer_id": payer_id}):
                return PaymentGatewayResponse(
                    success=True,
                    external_payment_id=payment.id,
                    external_status="approved",
                    gateway_response=json.dumps(payment.to_dict()),
                )
            else:
                return PaymentGatewayResponse(
                    success=False,
                    external_payment_id=payment.id,
                    external_status="failed",
                    error_message=f"PayPal execution error: {payment.error}",
                    gateway_response=json.dumps(payment.error) if payment.error else None,
                )

        except Exception as e:
            return PaymentGatewayResponse(
                success=False,
                error_message=f"PayPal execution error: {str(e)}",
            )

    def process_webhook(self, data: dict) -> PaymentGatewayResponse:
        """
        Process a PayPal webhook notification.
        """
        try:
            event_type = data.get("event_type", "")
            resource = data.get("resource", {})
            payment_id = resource.get("id", "")
            status = resource.get("state", resource.get("status", ""))

            is_completed = event_type in (
                "PAYMENT.SALE.COMPLETED",
                "CHECKOUT.ORDER.APPROVED",
            )

            return PaymentGatewayResponse(
                success=is_completed,
                external_payment_id=payment_id,
                external_status=status,
                gateway_response=json.dumps(data),
                error_message=None if is_completed else f"Event: {event_type}, Status: {status}",
            )

        except Exception as e:
            return PaymentGatewayResponse(
                success=False,
                error_message=f"PayPal webhook error: {str(e)}",
            )


# Singleton factory
_adapter_instance: Optional[PayPalAdapter] = None


def get_paypal_adapter() -> PayPalAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = PayPalAdapter()
    return _adapter_instance
