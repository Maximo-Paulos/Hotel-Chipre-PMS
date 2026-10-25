# master_admin models live outside app/models but share Base — import them so
# Base.metadata is complete (create_all/drop_all in tests must see every table)
import app.master_admin.models  # noqa: F401
from app.models.action_step_up_ticket_use import ActionStepUpTicketUse
from app.models.ai_assistant import (
    AIAssistantActionRun,
    AIAssistantInsight,
    AIAssistantMessage,
    AIAssistantSession,
)
from app.models.allocation import (
    AllocationAssignment,
    AllocationExplanation,
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
    LLMFeedbackEvent,
    LLMPolicySuggestion,
    ManualOverrideReason,
    ReservationAllocationLock,
    SolverMetric,
)
from app.models.analytics import (
    AnalyticsAIUsageMonthly,
    AnalyticsAlertSetting,
    AnalyticsAlertSnooze,
    AnalyticsCurrencyDisplayEnum,
    AnalyticsExportFormatEnum,
    AnalyticsExportJob,
    AnalyticsExportStatusEnum,
    AnalyticsFactRefreshJob,
    FactReservationDaily,
    FactReservationRowKindEnum,
    FactRoomOccupancyDaily,
    FactRoomOccupancyStatusAtNightEnum,
    HotelAuditEvent,
    RoomStateEvent,
    RoomStateEventReasonCodeEnum,
    RoomStateEventTypeEnum,
)
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.business_clock import HotelBusinessClock
from app.models.cancellation_review import ReservationCancellationReview
from app.models.cash_expense import CashExpense, CashExpenseStatusEnum
from app.models.cash_register import (
    CashCloseReport,
    CashCustodyHandoff,
    CashCustodyStatusEnum,
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
    CashSessionStatusEnum,
)
from app.models.commercial import (
    FxPolicy,
    ProductRoomCompatibility,
    RatePlan,
    RatePlanPrice,
    SellableProduct,
    TaxPolicy,
    TaxRule,
)
from app.models.company import Company
from app.models.company_document import (
    CompanyDocument,
    CompanyDocumentStatusEnum,
    CompanyDocumentTypeEnum,
)
from app.models.company_night_charge import (
    CompanyNightCharge,
    CompanyNightChargeAmountAdjustment,
    CompanyNightChargePaymentAllocation,
    CompanyNightlySurchargeRate,
)
from app.models.connection import Connection
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.domain_event_retention_watermark import DomainEventRetentionWatermark
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.guest import (
    Guest,
    GuestCompanion,
    GuestRatingEnum,
    GuestTag,
    GuestTagTypeEnum,
)
from app.models.guest_restriction import GuestRestriction, GuestRestrictionStatusEnum
from app.models.guest_room_avoidance import (
    GuestRoomAvoidance,
    GuestRoomAvoidanceStatusEnum,
)
from app.models.hotel_api_key import APIKeyPurposeEnum, HotelAPIKey
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.hotel_role import HotelRole
from app.models.hotel_role_visibility_window import HotelRoleVisibilityWindow
from app.models.housekeeping_checklist import (
    HousekeepingChecklist,
    HousekeepingChecklistItem,
    HousekeepingChecklistItemCodeEnum,
    HousekeepingChecklistStatusEnum,
)
from app.models.integration import (
    IntegrationCatalog,
    IntegrationConnection,
    IntegrationEvent,
)
from app.models.invitation import StaffInvitation
from app.models.job_runtime import JobDispatchRecord, ServiceHeartbeat
from app.models.laundry import LaundryBatch, LaundryItem
from app.models.laundry_discrepancy import (
    LaundryDiscrepancyAction,
    LaundryRemitoDiscrepancy,
)
from app.models.laundry_vendor import (
    LaundryRemito,
    LaundryRemitoLine,
    LaundryVendor,
    LaundryVendorPrice,
)
from app.models.linen import LinenItem, LinenLocation, LinenMovement, LinenParLevel
from app.models.marketing import MarketingLead, MarketingPricingPlan  # noqa: F401
from app.models.notification import (
    DailyReportSchedule,
    Notification,
    NotificationChannelEnum,
    NotificationOutbox,
    NotificationOutboxStatusEnum,
    NotificationPreference,
    NotificationSeverityEnum,
    PushSubscription,
)
from app.models.onboarding import OnboardingState
from app.models.operational_task import (
    OperationalTask,
    OperationalTaskAttachment,
    OperationalTaskEvent,
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
    ShiftHandoff,
    ShiftHandoffStatusEnum,
)
from app.models.operations import (
    BillingAdjustment,
    ReservationAdjustment,
    ReservationStatusHistory,
    RoomMoveEvent,
    RoomMovementGroup,
)
from app.models.ota import OTAReservationMapping, OTAWebhookCredential
from app.models.ota_core import (
    OTACancellationRule,
    OTACommissionRule,
    OTAConnection,
    OTACurrencyRate,
    OTAInventoryRule,
    OTAPriceRule,
    OTAPropertyMapping,
    OTAProvider,
    OTARatePlanMapping,
    OTAReservationLink,
    OTARoomMapping,
    OTASyncEvent,
    OTASyncJob,
)
from app.models.payment import (
    Payment,
    PaymentLink,
    PaymentLinkStatusEnum,
    PaymentProviderEnum,
    PaymentStatusEnum,
    PaymentWebhookEvent,
)
from app.models.payment_correction import PaymentCorrection
from app.models.payment_link_test import PaymentLinkTest
from app.models.payment_proof import (
    PaymentProof,
    PaymentProofBlob,
    PaymentProofStatusEnum,
)
from app.models.payment_receipt_email_delivery import PaymentReceiptEmailDelivery
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.pending_action import (
    PendingActionPriorityEnum,
    PendingActionStatusEnum,
    PendingActionTypeEnum,
    PendingOperationalAction,
)
from app.models.permission import (
    HotelPermissionOverride,
    Permission,
    RolePermissionDefault,
    UserPermissionOverride,
)
from app.models.pricing import CategoryPricing
from app.models.promotion import Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum
from app.models.public_inquiry import PublicInquiry, PublicInquiryNotificationStatus
from app.models.rate_change_draft import RateChangeDraft
from app.models.rate_limit_event import RateLimitEvent
from app.models.refund import RefundPathEnum, RefundRequest, RefundStatusEnum
from app.models.reservation import (
    Reservation,
    ReservationCancellationReasonCodeEnum,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)
from app.models.reservation_communication import (
    ReservationEmailDelivery,
    ReservationEmailKindEnum,
    ReservationEmailStatusEnum,
)
from app.models.reservation_group import ReservationGroup
from app.models.reservation_group_payment import (
    ReservationGroupPaymentAllocation,
    ReservationGroupPaymentBatch,
)
from app.models.reservation_guest_arrival import ReservationGuestArrival
from app.models.reservation_company_terms_review import ReservationCompanyTermsReview
from app.models.room import Room, RoomCategory
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.security_token import SecurityToken
from app.models.stock import (
    StockCountLine,
    StockCountSession,
    StockItem,
    StockLocation,
    StockMovement,
)
from app.models.stored_object import StoredObject, StoredObjectStatusEnum
from app.models.subscription import (
    HotelEntitlementOverride,
    HotelSubscription,
    SubscriptionEntitlement,
    SubscriptionPlan,
)
from app.models.subscription_v2 import (
    Subscription,
    SubscriptionAdjustment,
    SubscriptionEvent,
)
from app.models.temporary_action_grant import (
    TemporaryActionGrant,
    TemporaryActionGrantStatusEnum,
)
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum
from app.models.user import User
from app.models.user_mfa import UserMfaRecoveryCode, UserMfaSecret
from app.models.user_session import UserSession
from app.models.voucher import HotelVoucher, VoucherRedemption, VoucherStatusEnum
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.models.whatsapp_crm import (
    WhatsAppChannel,
    WhatsAppChannelStatusEnum,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppConversationEvent,
    WhatsAppConversationNote,
    WhatsAppConversationStatusEnum,
    WhatsAppMessage,
    WhatsAppMessageDirectionEnum,
    WhatsAppMessageStatusEnum,
    WhatsAppOutboundOutbox,
    WhatsAppProviderRoute,
)

__all__ = [
    "HotelBusinessClock",
    "Room", "RoomCategory",
    "OperationalTask", "OperationalTaskEvent", "OperationalTaskAttachment", "OperationalTaskTypeEnum",
    "OperationalTaskStatusEnum", "OperationalTaskPriorityEnum", "ShiftHandoff",
    "ShiftHandoffStatusEnum",
    "ReservationEmailDelivery",
    "ReservationEmailKindEnum",
    "ReservationEmailStatusEnum",
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
    "HotelRole",
    "Company",
    "DomainEventOutbox",
    "DomainEventRetentionWatermark",
    "StoredObject", "StoredObjectStatusEnum",
    "JobDispatchRecord", "ServiceHeartbeat",
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
    "AnalyticsFactRefreshJob",
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
    "StockCountSession",
    "StockCountLine",
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
    "ReservationCancellationReview",
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
    "MarketingPricingPlan",
    "MarketingLead",
]
