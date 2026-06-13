from app.models.room import Room, RoomCategory
from app.models.guest import Guest, GuestCompanion, GuestTag, GuestRatingEnum, GuestTagTypeEnum
from app.models.reservation import (
    Reservation,
    ReservationStatusEnum,
    ReservationOutcomeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationChannelCodeEnum,
    ReservationCancellationReasonCodeEnum,
    ReservationNoShowPolicyAppliedEnum,
)
from app.models.transaction import Transaction, PaymentMethodEnum, TransactionStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.company import Company
from app.models.ota import OTAReservationMapping, OTAWebhookCredential
from app.models.ota_core import (
    OTAProvider,
    OTAConnection,
    OTAPropertyMapping,
    OTARoomMapping,
    OTARatePlanMapping,
    OTAInventoryRule,
    OTAPriceRule,
    OTACancellationRule,
    OTACommissionRule,
    OTACurrencyRate,
    OTAReservationLink,
    OTASyncJob,
    OTASyncEvent,
)
from app.models.pricing import CategoryPricing
from app.models.commercial import (
    SellableProduct,
    ProductRoomCompatibility,
    RatePlan,
    RatePlanPrice,
    TaxPolicy,
    TaxRule,
    FxPolicy,
)
from app.models.operations import (
    ReservationStatusHistory,
    ReservationAdjustment,
    RoomMovementGroup,
    RoomMoveEvent,
    BillingAdjustment,
)
from app.models.allocation import (
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
    AllocationAssignment,
    ReservationAllocationLock,
    AllocationExplanation,
    SolverMetric,
    ManualOverrideReason,
    LLMPolicySuggestion,
    LLMFeedbackEvent,
)
from app.models.connection import Connection
from app.models.onboarding import OnboardingState
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.models.subscription import SubscriptionPlan, HotelSubscription, SubscriptionEntitlement, HotelEntitlementOverride
from app.models.subscription_v2 import Subscription, SubscriptionEvent
from app.models.integration import IntegrationCatalog, IntegrationConnection, IntegrationEvent
from app.models.payment_link_test import PaymentLinkTest
from app.models.payment import (
    Payment,
    PaymentLink,
    PaymentWebhookEvent,
    PaymentProviderEnum,
    PaymentStatusEnum,
    PaymentLinkStatusEnum,
)
from app.models.security_token import SecurityToken
from app.models.rate_limit_event import RateLimitEvent
from app.models.ai_assistant import AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight
from app.models.audit_log import AuditLog, AuditActionEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.permission import Permission, RolePermissionDefault, HotelPermissionOverride
from app.models.laundry import LaundryBatch, LaundryItem
from app.models.stock import StockItem, StockLocation, StockMovement
from app.models.voucher import HotelVoucher, VoucherRedemption, VoucherStatusEnum
from app.models.refund import RefundRequest, RefundPathEnum, RefundStatusEnum
from app.models.pending_action import (
    PendingOperationalAction,
    PendingActionTypeEnum,
    PendingActionStatusEnum,
    PendingActionPriorityEnum,
)
from app.models.cash_register import (
    CashSession,
    CashMovement,
    CashCloseReport,
    CashSessionStatusEnum,
    CashMovementTypeEnum,
)
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.models.payment_config import PaymentSurchargeConfig
from app.models.hotel_api_key import HotelAPIKey, APIKeyPurposeEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.company_document import CompanyDocument, CompanyDocumentTypeEnum, CompanyDocumentStatusEnum
# master_admin models live outside app/models but share Base — import them so
# Base.metadata is complete (create_all/drop_all in tests must see every table)
import app.master_admin.models  # noqa: F401
from app.models.analytics import (
    AnalyticsExportFormatEnum,
    AnalyticsCurrencyDisplayEnum,
    AnalyticsExportStatusEnum,
    AnalyticsAlertSetting,
    AnalyticsAlertSnooze,
    AnalyticsExportJob,
    AnalyticsAIUsageMonthly,
    HotelAuditEvent,
    RoomStateEventTypeEnum,
    RoomStateEventReasonCodeEnum,
    RoomStateEvent,
    FactReservationRowKindEnum,
    FactRoomOccupancyStatusAtNightEnum,
    FactReservationDaily,
    FactRoomOccupancyDaily,
)

__all__ = [
    "Room", "RoomCategory",
    "Guest", "GuestCompanion", "GuestTag", "GuestRatingEnum", "GuestTagTypeEnum",
    "Reservation", "ReservationStatusEnum", "ReservationOutcomeEnum",
    "ReservationGuestSegmentEnum", "ReservationGuestSegmentSourceEnum",
    "ReservationChannelCodeEnum", "ReservationCancellationReasonCodeEnum",
    "ReservationNoShowPolicyAppliedEnum",
    "Transaction", "PaymentMethodEnum", "TransactionStatusEnum",
    "HotelConfiguration",
    "Company",
    "OTAReservationMapping",
    "OTAWebhookCredential",
    "OTAProvider",
    "OTAConnection",
    "OTAPropertyMapping",
    "OTARoomMapping",
    "OTARatePlanMapping",
    "OTAInventoryRule",
    "OTAPriceRule",
    "OTACancellationRule",
    "OTACommissionRule",
    "OTACurrencyRate",
    "OTAReservationLink",
    "OTASyncJob",
    "OTASyncEvent",
    "CategoryPricing",
    "SellableProduct",
    "ProductRoomCompatibility",
    "RatePlan",
    "RatePlanPrice",
    "TaxPolicy",
    "TaxRule",
    "FxPolicy",
    "ReservationStatusHistory",
    "ReservationAdjustment",
    "RoomMovementGroup",
    "RoomMoveEvent",
    "BillingAdjustment",
    "AllocationPolicyProfile",
    "AllocationPolicyVersion",
    "AllocationRun",
    "AllocationAssignment",
    "ReservationAllocationLock",
    "AllocationExplanation",
    "SolverMetric",
    "ManualOverrideReason",
    "LLMPolicySuggestion",
    "LLMFeedbackEvent",
    "Connection",
    "OnboardingState",
    "User",
    "HotelMembership",
    "SubscriptionPlan",
    "HotelSubscription",
    "SubscriptionEntitlement",
    "HotelEntitlementOverride",
    "Subscription",
    "SubscriptionEvent",
    "IntegrationCatalog",
    "IntegrationConnection",
    "IntegrationEvent",
    "PaymentLinkTest",
    "Payment",
    "PaymentLink",
    "PaymentWebhookEvent",
    "PaymentProviderEnum",
    "PaymentStatusEnum",
    "PaymentLinkStatusEnum",
    "SecurityToken",
    "RateLimitEvent",
    "AIAssistantSession",
    "AIAssistantMessage",
    "AIAssistantActionRun",
    "AIAssistantInsight",
    "AnalyticsExportFormatEnum",
    "AnalyticsCurrencyDisplayEnum",
    "AnalyticsExportStatusEnum",
    "AnalyticsAlertSetting",
    "AnalyticsAlertSnooze",
    "AnalyticsExportJob",
    "AnalyticsAIUsageMonthly",
    "HotelAuditEvent",
    "RoomStateEventTypeEnum",
    "RoomStateEventReasonCodeEnum",
    "RoomStateEvent",
    "FactReservationRowKindEnum",
    "FactRoomOccupancyStatusAtNightEnum",
    "FactReservationDaily",
    "FactRoomOccupancyDaily",
    "AuditLog",
    "AuditActionEnum",
    "SecurityAuditLog",
    "Permission",
    "RolePermissionDefault",
    "HotelPermissionOverride",
    "LaundryBatch",
    "LaundryItem",
    "StockItem",
    "StockLocation",
    "StockMovement",
    "HotelVoucher",
    "VoucherRedemption",
    "VoucherStatusEnum",
    "RefundRequest",
    "RefundPathEnum",
    "RefundStatusEnum",
    "PendingOperationalAction",
    "PendingActionTypeEnum",
    "PendingActionStatusEnum",
    "PendingActionPriorityEnum",
    "CashSession",
    "CashMovement",
    "CashCloseReport",
    "CashSessionStatusEnum",
    "CashMovementTypeEnum",
    "WaitlistEntry",
    "WaitlistStatusEnum",
    "PaymentSurchargeConfig",
    "HotelAPIKey",
    "APIKeyPurposeEnum",
    "RoomBlock",
    "RoomBlockReasonEnum",
    "CompanyDocument",
    "CompanyDocumentTypeEnum",
    "CompanyDocumentStatusEnum",
]
