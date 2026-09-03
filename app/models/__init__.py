from app.models.room import Room, RoomCategory
from app.models.guest import Guest, GuestCompanion, GuestTag, GuestRatingEnum, GuestTagTypeEnum
from app.models.guest_restriction import GuestRestriction, GuestRestrictionStatusEnum
from app.models.guest_room_avoidance import GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum
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
from app.models.hotel_role_visibility_window import HotelRoleVisibilityWindow
from app.models.company import Company
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.domain_event_retention_watermark import DomainEventRetentionWatermark
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
from app.models.daily_rate import DailyRate, PricePeriod
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
from app.models.user_session import UserSession
from app.models.user_mfa import UserMfaSecret, UserMfaRecoveryCode
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.subscription import SubscriptionPlan, HotelSubscription, SubscriptionEntitlement, HotelEntitlementOverride
from app.models.subscription_v2 import Subscription, SubscriptionEvent, SubscriptionAdjustment
from app.models.integration import IntegrationCatalog, IntegrationConnection, IntegrationEvent
from app.models.payment_link_test import PaymentLinkTest
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.payment import (
    Payment,
    PaymentLink,
    PaymentWebhookEvent,
    PaymentProviderEnum,
    PaymentStatusEnum,
    PaymentLinkStatusEnum,
)
from app.models.payment_proof import PaymentProof, PaymentProofBlob, PaymentProofStatusEnum
from app.models.security_token import SecurityToken
from app.models.rate_limit_event import RateLimitEvent
from app.models.ai_assistant import AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight
from app.models.audit_log import AuditLog, AuditActionEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.permission import (
    Permission,
    RolePermissionDefault,
    HotelPermissionOverride,
    UserPermissionOverride,
)
from app.models.temporary_action_grant import (
    TemporaryActionGrant,
    TemporaryActionGrantStatusEnum,
)
from app.models.laundry import LaundryBatch, LaundryItem
from app.models.laundry_vendor import LaundryVendor, LaundryVendorPrice, LaundryRemito, LaundryRemitoLine
from app.models.stock import StockItem, StockLocation, StockMovement
from app.models.linen import LinenItem, LinenLocation, LinenMovement
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
    CashCustodyHandoff,
    CashSessionStatusEnum,
    CashMovementTypeEnum,
    CashCustodyStatusEnum,
)
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.models.hotel_api_key import HotelAPIKey, APIKeyPurposeEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.company_document import CompanyDocument, CompanyDocumentTypeEnum, CompanyDocumentStatusEnum
from app.models.promotion import Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum
from app.models.notification import (
    Notification,
    PushSubscription,
    NotificationPreference,
    NotificationOutbox,
    DailyReportSchedule,
    NotificationSeverityEnum,
    NotificationChannelEnum,
    NotificationOutboxStatusEnum,
)
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
    "GuestRestriction", "GuestRestrictionStatusEnum",
    "GuestRoomAvoidance", "GuestRoomAvoidanceStatusEnum",
    "Reservation", "ReservationStatusEnum", "ReservationOutcomeEnum",
    "ReservationGuestSegmentEnum", "ReservationGuestSegmentSourceEnum",
    "ReservationChannelCodeEnum", "ReservationCancellationReasonCodeEnum",
    "ReservationNoShowPolicyAppliedEnum",
    "Transaction", "PaymentMethodEnum", "TransactionStatusEnum",
    "HotelConfiguration",
    "HotelRoleVisibilityWindow",
    "Company",
    "DomainEventOutbox",
    "DomainEventRetentionWatermark",
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
    "DailyRate",
    "PricePeriod",
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
    "UserSession",
    "UserMfaSecret",
    "UserMfaRecoveryCode",
    "HotelMembership",
    "StaffInvitation",
    "SubscriptionPlan",
    "HotelSubscription",
    "SubscriptionEntitlement",
    "HotelEntitlementOverride",
    "Subscription",
    "SubscriptionEvent",
    "SubscriptionAdjustment",
    "IntegrationCatalog",
    "IntegrationConnection",
    "IntegrationEvent",
    "PaymentLinkTest",
    "PaymentSurcharge",
    "PaymentSurchargeTypeEnum",
    "Payment",
    "PaymentLink",
    "PaymentWebhookEvent",
    "PaymentProviderEnum",
    "PaymentStatusEnum",
    "PaymentLinkStatusEnum",
    "PaymentProof",
    "PaymentProofStatusEnum",
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
    "UserPermissionOverride",
    "TemporaryActionGrant",
    "TemporaryActionGrantStatusEnum",
    "LaundryBatch",
    "LaundryItem",
    "StockItem",
    "StockLocation",
    "StockMovement",
    "LinenItem",
    "LinenLocation",
    "LinenMovement",
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
    "CashCustodyHandoff",
    "CashSessionStatusEnum",
    "CashMovementTypeEnum",
    "CashCustodyStatusEnum",
    "WaitlistEntry",
    "WaitlistStatusEnum",
    "HotelAPIKey",
    "APIKeyPurposeEnum",
    "RoomBlock",
    "RoomBlockReasonEnum",
    "FxRateSnapshot",
    "CompanyDocument",
    "CompanyDocumentTypeEnum",
    "CompanyDocumentStatusEnum",
    "Promotion",
    "PromotionBenefitTypeEnum",
    "PromotionScopeEnum",
    "Notification",
    "PushSubscription",
    "NotificationPreference",
    "NotificationOutbox",
    "DailyReportSchedule",
    "NotificationSeverityEnum",
    "NotificationChannelEnum",
    "NotificationOutboxStatusEnum",
]
