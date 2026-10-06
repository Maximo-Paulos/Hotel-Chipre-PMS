import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { type TFunction } from "i18next";

import {
  addReservationCharge,
  createReservationGroupPayment,
  createReservationGroup,
  getReservation,
  isDeferredCompanyReservation,
  listReservationGroups,
  newReservationGroupPaymentIdempotencyKey,
  markReservationNoShow,
  moveReservationRoom,
  RESERVATION_GROUP_SUMMARY_LIMIT,
  type Reservation,
  type ReservationChargePayload,
  type ReservationGroupSummary,
  type ReservationGroupPaymentPayload,
  type ReservationGroupPaymentResult,
  type ReservationNoShowPayload,
  type ReservationPayload,
  type ReservationPendingAction,
  type ReservationRoomMovePayload,
  type ReservationRoomMoveResponse,
  type ReservationSource,
  type ReservationStatus,
  type ReservationUpdatePayload
} from "../../api/reservations";
import { listCompanyOptions, type CompanyOption } from "../../api/companies";
import {
  listReservationCommunications,
  sendReservationCommunication,
  type ReservationEmailDelivery,
  type ReservationEmailKind
} from "../../api/reservationCommunications";
import {
  listRoomMovementGroups,
  revertRoomMovementGroup,
  triggerAllocationRecalculation,
  type AllocationRunResponse,
  type RoomMovementGroup
} from "../../api/allocationRuns";
import { ApiError, hasValidSession } from "../../api/client";
import { getFxConversionQuote, type FxCurrencyCode } from "../../api/fxRates";
import { getGuestProhibitedDetail } from "../../api/guestRestrictions";
import GuestQuickCreatePanel, {
  emptyQuickGuestForm,
  hasQuickGuestFormData,
  type QuickGuestFormValues
} from "../../components/GuestQuickCreatePanel";
import LocalizedDateField from "../../components/LocalizedDateField";
import ManualOtaReservationModal from "../../components/ManualOtaReservationModal";
import { RestrictionOverrideModal } from "../../components/RestrictionOverrideModal";
import { useRestrictionOverridePrompt } from "../../hooks/useRestrictionOverridePrompt";
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { checkRoomAvailability, type RoomAvailabilityResponse } from "../../api/rooms";
import {
  emailPaymentReceipt,
  getPaymentReceiptData,
  newPaymentReceiptEmailIdempotencyKey,
  type PaymentMethod,
  type PaymentRequest,
  type PaymentSummary
} from "../../api/payments";
import { useCategories } from "../../hooks/useCategories";
import { useGuest, useGuestCreate } from "../../hooks/useGuests";
import {
  usePendingReservationActions,
  useReservation,
  useReservationQuote,
  useReservationActionMutations,
  useReservationMutations,
  useReservationOperationsSummary,
  useReservations
} from "../../hooks/useReservations";
import { usePaymentMutation, usePaymentSummary } from "../../hooks/usePayments";
import { useCashSessions } from "../../hooks/useCashRegister";
import { usePaymentSurcharges } from "../../hooks/usePaymentSurcharges";
import { grossWithSurcharge } from "../../api/paymentSurcharges";
import { usePaymentLinks, usePaymentLinkCancel, usePaymentLinkCreate } from "../../hooks/usePaymentLinks";
import { usePaymentProofMutations, usePaymentProofs } from "../../hooks/usePaymentProofs";
import { fetchPaymentProofImage } from "../../api/paymentProofs";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { type HotelConfig } from "../../api/config";
import { useRooms } from "../../hooks/useRooms";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";
import { formatMoney, normalizeCurrencyCode } from "../../utils/currency";
import { escapeHtml, resolveVoucherOperationalBalance } from "../../utils/escapeHtml";
import { isLargeTotalAdjustment } from "../../utils/largeTotalAdjustment.mjs";
import { buildPaymentReceiptHtml, canPrintPaymentReceipt } from "../../utils/paymentReceiptHtml";
import { addDaysIso, formatHotelDateTime, formatLocalIsoDate, todayIso } from "../../utils/date";
import {
  canCancelReservation,
  canCheckInReservation,
  canCheckOutReservation,
  reservationStatusConfig
} from "../../utils/reservationStatus";
import ReservationStatCard from "../../components/StatCard";
import { ROOM_MOVE_REASONS, moveBlockedReason } from "../../utils/roomMove";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useCollaborativeResource } from "../../hooks/useCollaborativeResource";
import { refreshReservationState } from "../../api/queryInvalidation";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useOperationalAudit } from "../../hooks/useOperationalAudit";



type FormState = {
  guest_id: string;
  category_id: string;
  room_id: string;
  company_id: string;
  group_size: string;
  check_in_date: string;
  check_out_date: string;
  num_adults: string;
  num_children: string;
  notes: string;
  arrival_time_hint: string;
  reservation_comment: string;
  source: ReservationSource;
  status: ReservationStatus;
};

type PricingPaymentMethod = "base" | "cash" | "transfer" | "mercadopago" | "credit_card" | "paypal";

type PaymentReceiptEmailAttempt = {
  transactionId: number;
  recipientEmail: string;
  idempotencyKey: string;
  status: "confirm" | "sending" | "sent" | "failed" | "unknown";
};

const PAYMENT_CURRENCIES: FxCurrencyCode[] = ["ARS", "USD", "EUR", "BRL", "CLP", "UYU"];

const paymentMethodValues: PaymentMethod[] = [
  "cash",
  "credit_card",
  "debit_card",
  "mercado_pago",
  "bank_transfer",
  "paypal"
];
const manualPaymentMethods: PaymentMethod[] = ["credit_card", "debit_card", "bank_transfer"];

// Single source of truth for which payment methods are offered: the hotel
// configuration (enable_* flags). Avoids offering a method the backend will reject.
const paymentMethodEnabledFlag: Record<PaymentMethod, keyof HotelConfig> = {
  cash: "enable_cash",
  credit_card: "enable_credit_card",
  debit_card: "enable_debit_card",
  mercado_pago: "enable_mercado_pago",
  bank_transfer: "enable_bank_transfer",
  paypal: "enable_paypal"
};

const enabledPaymentMethods = (config?: HotelConfig | null) =>
  config
    ? paymentMethodValues.filter((value) => config[paymentMethodEnabledFlag[value]] === true)
    : paymentMethodValues;

const pricingPaymentMethodValues: PricingPaymentMethod[] = ["base", "cash", "transfer", "mercadopago", "credit_card", "paypal"];

const statusConfig = reservationStatusConfig;

const priorityClassName: Record<ReservationPendingAction["priority"], string> = {
  critical: "bg-rose-100 text-rose-800",
  high: "bg-amber-100 text-amber-800",
  medium: "bg-sky-100 text-sky-800",
  low: "bg-slate-100 text-slate-700"
};

const defaultFormState = (): FormState => ({
  guest_id: "",
  category_id: "",
  room_id: "",
  company_id: "",
  group_size: "1",
  check_in_date: "",
  check_out_date: "",
  num_adults: "1",
  num_children: "0",
  notes: "",
  arrival_time_hint: "",
  reservation_comment: "",
  source: "direct",
  status: "pending"
});

const reservationGuestLabel = (
  t: TFunction,
  reservation: {
    guest?: { first_name: string; last_name: string } | null;
    guest_id: number;
  }
) =>
  reservation.guest
    ? `${reservation.guest.first_name} ${reservation.guest.last_name}`.trim()
    : t("page.guestLabel.fallback", { id: reservation.guest_id });

const formatDateTime = (value?: string | null, timeZone?: string | null) =>
  formatHotelDateTime(value, timeZone);

const auditMetadataLines = (
  details: Record<string, unknown>,
  labels: { arrival: string; comment: string; empty: string }
) => {
  const before = details.before && typeof details.before === "object" ? details.before as Record<string, unknown> : {};
  const after = details.after && typeof details.after === "object" ? details.after as Record<string, unknown> : {};
  const beforeMetadata = details.metadata && typeof details.metadata === "object" ? details.metadata as Record<string, unknown> : before;
  const afterMetadata = details.metadata && typeof details.metadata === "object" ? details.metadata as Record<string, unknown> : after;
  const lines: string[] = [];
  for (const [field, label] of [["arrival_time_hint", labels.arrival], ["reservation_comment", labels.comment]] as const) {
    const hasChange = Object.prototype.hasOwnProperty.call(beforeMetadata, field) || Object.prototype.hasOwnProperty.call(afterMetadata, field);
    if (!hasChange) continue;
    const previous = beforeMetadata[field] ?? labels.empty;
    const next = afterMetadata[field] ?? labels.empty;
    if (previous === next) continue;
    lines.push(`${label}: ${String(previous)} → ${String(next)}`);
  }
  return lines;
};

const diffNights = (checkIn: string, checkOut: string) => {
  if (!checkIn || !checkOut) return 0;
  const start = new Date(`${checkIn}T00:00:00`);
  const end = new Date(`${checkOut}T00:00:00`);
  const diff = end.getTime() - start.getTime();
  return diff > 0 ? Math.round(diff / 86_400_000) : 0;
};

const readFileAsDataUrl = (file: File, errorMessage: string) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error(errorMessage));
    reader.readAsDataURL(file);
  });

export function ReservationsPage() {
  const { t, i18n } = useTranslation("reservations");
  // Backend codes (hotel_collect, not_applicable...) never reach the screen
  // raw; an unmapped value falls back to the code rather than a blank.
  const enumLabel = (group: "collection" | "settlement" | "nextAction", value: string) =>
    t(`page.enums.${group}.${value}`, { defaultValue: value });
  const translatedEnum = (group: string, value?: string | null) =>
    value ? t(`page.enums.${group}.${value}`, { defaultValue: t("page.enums.unknownValue") }) : t("page.enums.unknownValue");
  const sourceLabel = (value: string) => t(`page.form.sourceOptions.${value}`, { defaultValue: value });
  const { session } = useSession();
  const { openReservation } = useReservationDrawer();
  const { hasPermission } = useEffectivePermissions();
  const canManageCompanyReservation = (reservation: Pick<Reservation, "company_id">) =>
    !reservation.company_id || hasPermission("company:manage");
  const canAdjustPaidReservationTotal = hasPermission("reservation:paid_total_adjust");
  const canSetUnboundedReservationRate = hasPermission("reservation:manual_rate");
  const canSetBoundedReservationRate = hasPermission("reservation:manual_rate_limited");
  const canAdjustReservationRate = canSetUnboundedReservationRate || canSetBoundedReservationRate;
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | "all" | "">("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reservation | null>(null);
  const [formValues, setFormValues] = useState<FormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [guestForm, setGuestForm] = useState<QuickGuestFormValues>(emptyQuickGuestForm);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmountInput, setPaymentAmountInput] = useState("");
  const [paymentTenderCurrencyInput, setPaymentTenderCurrencyInput] = useState("");
  const [paymentReferenceInput, setPaymentReferenceInput] = useState("");
  const [payingGroup, setPayingGroup] = useState<ReservationGroupSummary | null>(null);
  const [groupPaymentTotalInput, setGroupPaymentTotalInput] = useState("");
  const [groupPaymentAllocations, setGroupPaymentAllocations] = useState<Record<number, string>>({});
  const [groupPaymentMethod, setGroupPaymentMethod] = useState<PaymentMethod>("cash");
  const [groupPaymentReference, setGroupPaymentReference] = useState("");
  const [groupPaymentDescription, setGroupPaymentDescription] = useState("");
  const [groupPaymentError, setGroupPaymentError] = useState<string | null>(null);
  const groupPaymentAttemptKeysRef = useRef(new Map<string, string>());
  const [collectedBefore, setCollectedBefore] = useState(false);
  const [collectedOn, setCollectedOn] = useState("");
  const [priorReceiptNote, setPriorReceiptNote] = useState("");
  const [refundTargetTransactionId, setRefundTargetTransactionId] = useState<number | null>(null);
  const [refundReasonInput, setRefundReasonInput] = useState("");
  const [refundNightAmounts, setRefundNightAmounts] = useState<Record<number, string>>({});
  const [paymentProofFile, setPaymentProofFile] = useState<File | null>(null);
  const [paymentProofPreview, setPaymentProofPreview] = useState<{ proofId: number; url: string } | null>(null);
  const [viewingPaymentProofId, setViewingPaymentProofId] = useState<number | null>(null);
  const [rejectingPaymentProofId, setRejectingPaymentProofId] = useState<number | null>(null);
  const [paymentProofRejectReason, setPaymentProofRejectReason] = useState("");
  const [pricingPaymentMethod, setPricingPaymentMethod] = useState<PricingPaymentMethod>("base");
  const [depositAmountInput, setDepositAmountInput] = useState("");
  // B4: tarifa manual opcional en la reserva directa -- cuando se completa,
  // reemplaza la cotización automática en vez de convivir con ella.
  const [manualTotalAmountInput, setManualTotalAmountInput] = useState("");
  const [manualTargetCurrency, setManualTargetCurrency] = useState<"ARS" | "USD">("ARS");
  const [manualRateReasonInput, setManualRateReasonInput] = useState("");
  const [paidTotalAmountInput, setPaidTotalAmountInput] = useState("");
  const [paidTotalChangeReasonInput, setPaidTotalChangeReasonInput] = useState("");
  const [confirmLargeTotalAdjustment, setConfirmLargeTotalAdjustment] = useState(false);
  const [lastCreatedReservation, setLastCreatedReservation] = useState<Reservation | null>(null);
  const [otaFormOpen, setOtaFormOpen] = useState(false);
  const [availabilityForm, setAvailabilityForm] = useState<{
    category_id: string;
    check_in_date: string;
    check_out_date: string;
  }>({
    category_id: "",
    check_in_date: todayIso(),
    check_out_date: addDaysIso(todayIso(), 1)
  });
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [allocationError, setAllocationError] = useState<string | null>(null);
  const [calendarRange, setCalendarRange] = useState<"week" | "month">("week");
  const [detailsReservationId, setDetailsReservationId] = useState<number | null>(null);
  const [detailsActionError, setDetailsActionError] = useState<{ reservationId: number; message: string } | null>(null);
  const [pageActionError, setPageActionError] = useState<string | null>(null);
  const [communicationRecipient, setCommunicationRecipient] = useState("");
  const [receiptEmailAttempt, setReceiptEmailAttempt] = useState<PaymentReceiptEmailAttempt | null>(null);
  const receiptEmailAttemptsRef = useRef(new Map<number, PaymentReceiptEmailAttempt>());
  const receiptEmailDialogRef = useRef<HTMLDivElement | null>(null);
  const receiptEmailTitleRef = useRef<HTMLHeadingElement | null>(null);
  const receiptEmailCloseRef = useRef<HTMLButtonElement | null>(null);
  const receiptEmailTriggerRef = useRef<HTMLButtonElement | null>(null);
  const receiptEmailAttemptRef = useRef<PaymentReceiptEmailAttempt | null>(null);
  const [roomMoveForm, setRoomMoveForm] = useState({
    to_room_id: "",
    reason_code: "",
    notes: "",
    price_action: "keep" as "keep" | "reprice",
    origin_room_disposition: "",
    origin_room_disposition_note: ""
  });
  const [chargeForm, setChargeForm] = useState({ description: "", amount: "" });
  const [noShowNotes, setNoShowNotes] = useState("");
  const [guestIdOpen, setGuestIdOpen] = useState<number | null>(null);
  const [allocationForm, setAllocationForm] = useState({
    apply: false,
    horizon_start: todayIso(),
    horizon_end: ""
  });
  const toastTimeout = useRef<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const hasReceiptEmailDialog = receiptEmailAttempt !== null;
  useEffect(() => {
    if (!hasReceiptEmailDialog) return;
    receiptEmailTitleRef.current?.focus();
    const handleDialogKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (receiptEmailAttemptRef.current?.status === "sending") return;
        receiptEmailAttemptRef.current = null;
        setReceiptEmailAttempt(null);
        window.requestAnimationFrame(() => receiptEmailTriggerRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        receiptEmailDialogRef.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])"
        ) ?? []
      ).filter((element) => element.getAttribute("aria-hidden") !== "true");
      if (!focusable.length) {
        event.preventDefault();
        receiptEmailTitleRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === receiptEmailTitleRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleDialogKeyDown);
    return () => document.removeEventListener("keydown", handleDialogKeyDown);
  }, [hasReceiptEmailDialog]);
  const { data: subscription } = useSubscriptionStatus();
  const writeBlocked = subscription?.can_write === false;
  const limitReached =
    subscription &&
    typeof subscription.room_limit === "number" &&
    subscription.room_limit > 0 &&
    subscription.rooms_in_use >= subscription.room_limit;
  const subscriptionBlocked = Boolean(subscription) && (writeBlocked || limitReached);
  const subscriptionBlockReason = subscriptionBlocked
    ? writeBlocked
      ? t("page.subscription.readOnly")
      : t("page.subscription.roomLimitReached", { used: subscription?.rooms_in_use, limit: subscription?.room_limit })
    : null;

  const filters = {
    status: statusFilter,
    fromDate: fromDate || undefined,
    toDate: toDate || undefined,
    // A2: the backend now defaults to limit=50/order=recent. This is the
    // operational reservations list (receptionists filtering by date range
    // / status), which used to return every match -- keep that shape by
    // asking for the ordering it already assumed (check_in_date ASC) and the
    // server's max page size, instead of silently truncating to 50.
    order: "check_in" as const,
    limit: 200,
    companyId: companyFilter ? Number(companyFilter) : undefined
  };

  const { data: reservations = [], isLoading, isFetching, error, refetch: refetchReservations } = useReservations(filters);
  const pendingActionsQuery = usePendingReservationActions(12);
  const { roomsQuery } = useRooms();
  const { data: categoriesData = [] } = useCategories();
  const companyOptionsQuery = useQuery<CompanyOption[]>({
    queryKey: ["company-options", session.hotelId],
    queryFn: () => listCompanyOptions(session),
    enabled: hasPermission("reservation:read") && hasValidSession(session),
    staleTime: 30_000
  });
  const companyOptions = useMemo(() => companyOptionsQuery.data ?? [], [companyOptionsQuery.data]);
  const selectedCompanyIsDeferred = Boolean(
    !editing && companyOptions.find((company) => company.id === Number(formValues.company_id))?.payment_deferred
  );
  const companyNameById = useMemo(
    () => new Map(companyOptions.map((company) => [company.id, company.display_name || company.legal_name])),
    [companyOptions]
  );
  const reservationGroupsQuery = useQuery<ReservationGroupSummary[]>({
    queryKey: ["reservation-groups", session.hotelId],
    queryFn: () => listReservationGroups(session),
    enabled: hasPermission("reservation:read") && hasValidSession(session),
    staleTime: 15_000
  });
  const categoryNameById = useMemo(() => {
    const map = new Map<number, string>();
    categoriesData.forEach((category) => map.set(category.id, category.name));
    return map;
  }, [categoriesData]);
  const guestMutation = useGuestCreate();
  const guestQuery = useGuest(guestIdOpen ?? undefined);
  const paymentSummaryQuery = usePaymentSummary(editing?.id || undefined);
  const paymentSummary = paymentSummaryQuery.data;
  const hasAnyPaymentEvidence = Boolean(
    paymentSummary?.transactions?.length ||
    Number(paymentSummary?.amount_paid ?? editing?.amount_paid ?? 0) > 0 ||
    Number(editing?.external_paid_amount ?? 0) > 0 ||
    editing?.external_paid_confirmed ||
    editing?.status === "deposit_paid" ||
    editing?.status === "fully_paid"
  );
  const canAdjustUnpaidDirectTotal = Boolean(
    editing &&
    canAdjustReservationRate &&
    editing.source === "direct" &&
    !editing.source_provider_code &&
    !editing.external_id &&
    editing.company_id == null &&
    editing.group_id == null &&
    !paymentSummaryQuery.isLoading &&
    !paymentSummaryQuery.isError &&
    !hasAnyPaymentEvidence
  );
  const canAdjustReservationTotal = Boolean(
    (hasAnyPaymentEvidence && canAdjustPaidReservationTotal) || canAdjustUnpaidDirectTotal
  );
  const cashSessionsQuery = useCashSessions();
  const paymentReservationCurrency = normalizeCurrencyCode(
    paymentSummaryQuery.data?.currency_code ?? editing?.currency_code
  );
  const paymentTenderCurrency = normalizeCurrencyCode(
    paymentTenderCurrencyInput || paymentReservationCurrency
  );
  const paymentFxQuoteQuery = useQuery({
    queryKey: ["payment-fx-quote", session.hotelId, paymentReservationCurrency, paymentTenderCurrency],
    queryFn: () => getFxConversionQuote(
      paymentReservationCurrency as FxCurrencyCode,
      paymentTenderCurrency as FxCurrencyCode,
      session
    ),
    enabled: Boolean(
      editing &&
      paymentReservationCurrency !== paymentTenderCurrency &&
      PAYMENT_CURRENCIES.includes(paymentReservationCurrency as FxCurrencyCode) &&
      PAYMENT_CURRENCIES.includes(paymentTenderCurrency as FxCurrencyCode) &&
      hasValidSession(session)
    ),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false
  });
  useEffect(() => {
    setPaymentTenderCurrencyInput(paymentReservationCurrency);
  }, [editing?.id, paymentReservationCurrency]);
  const detailsReservationQuery = useReservation(detailsReservationId ?? undefined);
  const detailsReservation =
    detailsReservationQuery.data ?? reservations.find((item) => item.id === detailsReservationId) ?? null;
  const detailsRoom = useMemo(
    () => (roomsQuery.data ?? []).find((room) => room.id === detailsReservation?.room_id) ?? null,
    [detailsReservation?.room_id, roomsQuery.data]
  );
  const detailsSummaryQuery = usePaymentSummary(detailsReservationId || undefined);
  const detailsOperationsQuery = useReservationOperationsSummary(detailsReservationId || undefined);
  const communicationsQuery = useQuery<ReservationEmailDelivery[]>({
    queryKey: ["reservation-communications", session.hotelId, detailsReservationId],
    queryFn: () => listReservationCommunications(detailsReservationId as number, session),
    enabled: Boolean(detailsReservationId && hasValidSession(session)),
    staleTime: 10_000
  });
  const detailsAuditQuery = useOperationalAudit(
    { limit: 50, reservation_id: detailsReservationId || undefined },
    Boolean(detailsReservationId && hasPermission("operations:audit:view"))
  );
  const paymentMutation = usePaymentMutation(editing?.id || undefined);
  const availabilityMutation = useGuardedMutation<RoomAvailabilityResponse, unknown, { category_id: number; check_in_date: string; check_out_date: string }>({
    mutationFn: (payload) => checkRoomAvailability(payload, session)
  });
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);
  const createGroupMutation = useGuardedMutation<ReservationGroupSummary, unknown, ReservationPayload[]>({
    mutationFn: (payloads) => createReservationGroup(payloads, session),
    onSuccess: async () => {
      await refreshReservationState(queryClient, session.hotelId);
      await queryClient.invalidateQueries({ queryKey: ["reservation-groups", session.hotelId] });
    }
  });
  const groupPaymentMutation = useGuardedMutation<
    ReservationGroupPaymentResult,
    unknown,
    { groupId: number; payload: ReservationGroupPaymentPayload }
  >({
    mutationFn: ({ groupId, payload }) => {
      const fingerprint = JSON.stringify({ groupId, payload });
      let key = groupPaymentAttemptKeysRef.current.get(fingerprint);
      if (!key) {
        key = newReservationGroupPaymentIdempotencyKey();
        if (groupPaymentAttemptKeysRef.current.size >= 20) {
          const oldest = groupPaymentAttemptKeysRef.current.keys().next().value;
          if (oldest) groupPaymentAttemptKeysRef.current.delete(oldest);
        }
        groupPaymentAttemptKeysRef.current.set(fingerprint, key);
      }
      return createReservationGroupPayment(groupId, payload, session, key);
    },
    onSuccess: async (_result, variables) => {
      groupPaymentAttemptKeysRef.current.delete(JSON.stringify(variables));
      await Promise.all([
        refreshReservationState(queryClient, session.hotelId),
        queryClient.invalidateQueries({ queryKey: ["reservation-groups", session.hotelId] })
      ]);
      setPayingGroup(null);
      setGroupPaymentError(null);
      showToast("success", t("page.groups.paymentSuccess"));
    },
    onError: (cause) => {
      setGroupPaymentError(cause instanceof Error ? cause.message : t("page.groups.paymentError"));
    }
  });
  const restrictionOverridePrompt = useRestrictionOverridePrompt();
  const { resolveExternalMutation, clearManualReviewMutation } = useReservationActionMutations(filters);
  const movementGroupsQuery = useQuery<RoomMovementGroup[]>({
    queryKey: ["room-movement-groups", session.hotelId, 6],
    queryFn: () => listRoomMovementGroups(6, session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });
  const collaborativeReservation = useCollaborativeResource({
    resourceType: "reservation",
    resourceId: editing?.id,
    initialValues: editing
      ? {
          room_id: editing.room_id,
          check_in_date: editing.check_in_date,
          check_out_date: editing.check_out_date,
          num_adults: editing.num_adults,
          num_children: editing.num_children,
          notes: editing.notes ?? null,
          arrival_time_hint: editing.arrival_time_hint ?? null,
          reservation_comment: editing.reservation_comment ?? null,
          mobility_restriction: false
        }
      : null,
    enabled: Boolean(formOpen && editing)
  });

  const invalidateAllocationState = () => refreshReservationState(queryClient, session.hotelId);

  const roomMoveMutation = useGuardedMutation<
    ReservationRoomMoveResponse,
    unknown,
    { reservationId: number; payload: ReservationRoomMovePayload }
  >({
    mutationFn: ({ reservationId, payload }) => moveReservationRoom(reservationId, payload, session),
    onSuccess: (result) => {
      const updatedReservation = result.reservation;
      queryClient.setQueryData(
        ["reservation", session.hotelId, updatedReservation.id],
        updatedReservation
      );
      queryClient.setQueriesData<Reservation[]>(
        { queryKey: ["reservations", session.hotelId] },
        (current) => current?.map((reservation) =>
          reservation.id === updatedReservation.id ? updatedReservation : reservation
        )
      );
      // The mutation response is authoritative for the moved room. Refresh
      // dependent actions, payments, and cash views in the background so a
      // slow read-model refresh does not leave the move button spinning after
      // the server has already committed the room change.
      void invalidateAllocationState().catch(() => undefined);
      setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep", origin_room_disposition: "", origin_room_disposition_note: "" });
      const currency = normalizeCurrencyCode(result.currency_code);
      if (!result.category_changed || result.amount_delta === 0) {
        showToast("success", t("page.messages.roomChanged"));
        return;
      }
      if (result.price_action === "reprice") {
        showToast("success", t("page.messages.roomChangedRepriced", { amount: formatMoney(result.quoted_total_amount, currency) }));
      } else {
        showToast(
          "info",
          t("page.messages.roomChangedKept", {
            quoted: formatMoney(result.quoted_total_amount, currency),
            delta: formatMoney(result.amount_delta, currency)
          })
        );
      }
    }
  });

  const noShowMutation = useGuardedMutation<Reservation, unknown, { reservationId: number; payload: ReservationNoShowPayload }>({
    mutationFn: ({ reservationId, payload }) => markReservationNoShow(reservationId, payload, session),
    onSuccess: async () => {
      await invalidateAllocationState();
      setNoShowNotes("");
      showToast("success", t("page.messages.noShowRegistered"));
    }
  });

  const chargeMutation = useGuardedMutation<unknown, unknown, { reservationId: number; payload: ReservationChargePayload }>({
    mutationFn: ({ reservationId, payload }) => addReservationCharge(reservationId, payload, session),
    onSuccess: async () => {
      await invalidateAllocationState();
      setChargeForm({ description: "", amount: "" });
      showToast("success", t("page.messages.chargeAdded"));
    },
    onError: (err: unknown) => {
      showToast("error", err instanceof Error ? err.message : t("page.errors.chargeFailed"));
    }
  });

  const allocationRunMutation = useGuardedMutation<AllocationRunResponse, unknown, typeof allocationForm>({
    mutationFn: (payload) =>
      triggerAllocationRecalculation(
        {
          apply: payload.apply,
          horizon_start: payload.horizon_start || null,
          horizon_end: payload.horizon_end || null
        },
        session
      ),
    onSuccess: async () => invalidateAllocationState()
  });

  const revertMovementGroupMutation = useGuardedMutation<RoomMovementGroup, unknown, number>({
    mutationFn: (groupId) => revertRoomMovementGroup(groupId, session),
    onSuccess: async () => invalidateAllocationState()
  });

  function showToast(type: "success" | "error" | "info", message: string) {
    if (type === "error") {
      if (toastTimeout.current) window.clearTimeout(toastTimeout.current);
      toastTimeout.current = null;
      setToast(null);
      if (formOpen) {
        setFormError(message);
      } else if (detailsReservationId) {
        setDetailsActionError({ reservationId: detailsReservationId, message });
      } else {
        setPageActionError(message);
      }
      return;
    }
    if (toastTimeout.current) {
      window.clearTimeout(toastTimeout.current);
    }
    setToast({ type, message });
    toastTimeout.current = window.setTimeout(() => {
      setToast(null);
      toastTimeout.current = null;
    }, 3800);
  };

  const clearToast = () => {
    if (toastTimeout.current) window.clearTimeout(toastTimeout.current);
    toastTimeout.current = null;
    setToast(null);
  };

  const today = todayIso();
  const totalRooms = roomsQuery.data?.length ?? 0;
  const moveRoomOptions = useMemo(() => {
    if (!detailsReservation) return [];
    // B5: also list rooms in other categories -- moving across categories is a
    // real operational need (upgrade/downgrade), it's just gated by capacity
    // validation and an explicit price_action on the backend now.
    return (roomsQuery.data ?? []).filter(
      (room) =>
        room.is_active &&
        room.id !== detailsReservation.room_id &&
        room.status !== "maintenance" &&
        room.status !== "blocked"
    );
  }, [detailsReservation, roomsQuery.data]);

  const categoryById = useMemo(() => {
    const map = new Map<number, { id: number; max_occupancy: number }>();
    categoriesData.forEach((cat) => map.set(cat.id, { id: cat.id, max_occupancy: cat.max_occupancy }));
    return map;
  }, [categoriesData]);

  // A destination the operator cannot use stays listed and says why: hiding it
  // would leave them guessing where the suite went.
  const moveBlockByRoomId = useMemo(() => {
    const map = new Map<number, string | null>();
    if (!detailsReservation) return map;
    const from = categoryById.get(detailsReservation.category_id);
    moveRoomOptions.forEach((room) => {
      map.set(room.id, moveBlockedReason(from, categoryById.get(room.category_id), hasPermission));
    });
    return map;
  }, [categoryById, detailsReservation, moveRoomOptions, hasPermission]);

  const selectedMoveRoom = useMemo(
    () => moveRoomOptions.find((room) => String(room.id) === roomMoveForm.to_room_id) ?? null,
    [moveRoomOptions, roomMoveForm.to_room_id]
  );
  const moveCrossesCategory = Boolean(
    selectedMoveRoom && detailsReservation && selectedMoveRoom.category_id !== detailsReservation.category_id
  );

  const categoryOptions = useMemo(
    () => categoriesData.map((cat) => ({ value: String(cat.id), label: cat.name })),
    [categoriesData]
  );

  const roomsByCategory = useMemo(() => {
    const rooms = roomsQuery.data ?? [];
    const grouped: Record<string, typeof rooms> = {};
    rooms.forEach((room) => {
      const key = String(room.category_id);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(room);
    });
    return grouped;
  }, [roomsQuery.data]);

  const roomsInSelectedCategory = formValues.category_id ? roomsByCategory[formValues.category_id] ?? [] : roomsQuery.data ?? [];
  const selectedFormCategory = useMemo(
    () => categoriesData.find((category) => String(category.id) === formValues.category_id) ?? null,
    [categoriesData, formValues.category_id]
  );
  const quoteNights = diffNights(formValues.check_in_date, formValues.check_out_date);
  const formAvailabilityQuery = useQuery<RoomAvailabilityResponse>({
    queryKey: [
      "reservation-form-availability",
      session.hotelId,
      formValues.category_id,
      formValues.check_in_date,
      formValues.check_out_date
    ],
    queryFn: () => checkRoomAvailability({
      category_id: Number(formValues.category_id),
      check_in_date: formValues.check_in_date,
      check_out_date: formValues.check_out_date
    }, session),
    enabled: Boolean(
      !editing && hasValidSession(session) && formValues.category_id &&
      formValues.check_in_date && formValues.check_out_date && quoteNights > 0
    ),
    staleTime: 10_000
  });
  const formAvailableRoomIds = useMemo(
    () => new Set(formAvailabilityQuery.data?.status === "ok" ? formAvailabilityQuery.data.available_rooms : []),
    [formAvailabilityQuery.data]
  );
  const availableRooms = editing
    ? roomsInSelectedCategory
    : roomsInSelectedCategory.filter((room) => formAvailableRoomIds.has(room.id));
  const requestedGroupRoomCount = Number(formValues.group_size) || 1;
  const hasEnoughGroupRooms = formAvailabilityQuery.data?.status === "ok" &&
    formAvailabilityQuery.data.count >= requestedGroupRoomCount;
  const groupAvailabilityBlocked = Boolean(
    !editing && requestedGroupRoomCount > 1 && formValues.category_id && quoteNights > 0 &&
    (formAvailabilityQuery.isFetching || formAvailabilityQuery.isError ||
      formAvailabilityQuery.data?.status !== "ok" || !hasEnoughGroupRooms)
  );
  const quoteCategoryId =
    !editing && selectedFormCategory && quoteNights > 0 ? Number(selectedFormCategory.id) : null;
  const quoteGuestId = Number(formValues.guest_id);
  const quoteQuery = useReservationQuote(
    quoteCategoryId && formValues.check_in_date && formValues.check_out_date
      ? {
          category_id: quoteCategoryId,
          check_in_date: formValues.check_in_date,
          check_out_date: formValues.check_out_date,
          pricing_payment_method: pricingPaymentMethod === "base" ? null : pricingPaymentMethod,
          occupancy: (Number(formValues.num_adults) || 1) + (Number(formValues.num_children) || 0),
          company_id: Number(formValues.company_id) > 0 ? Number(formValues.company_id) : null,
          // Lets an operator find out a guest is restricted before filling
          // out the whole form -- the endpoint itself has no override, the
          // real override happens at reservation creation (see submitCreate).
          guest_id: Number.isFinite(quoteGuestId) && quoteGuestId > 0 ? quoteGuestId : null
        }
      : null
  );
  const deferredCompanyBooking = selectedCompanyIsDeferred || quoteQuery.data?.company_billing_deferred === true;
  const isReservationQuoteUpdating =
    !editing && !deferredCompanyBooking && manualTotalAmountInput.trim() === "" && quoteQuery.isFetching;
  const reservationQuote = useMemo(() => {
    if (!quoteQuery.data || !selectedFormCategory || quoteNights <= 0) {
      return null;
    }
    return {
      nights: quoteQuery.data.nights,
      total: quoteQuery.data.total_amount ?? 0,
      subtotal: quoteQuery.data.subtotal_amount ?? 0,
      taxAmount: quoteQuery.data.tax_amount ?? 0,
      feeAmount: quoteQuery.data.fee_amount ?? 0,
      paymentMethod: quoteQuery.data.pricing_payment_method ?? null,
      defaultDeposit: quoteQuery.data.deposit_amount ?? null,
      currencyCode: quoteQuery.data.currency_code,
      quoteToken: quoteQuery.data.quote_token,
      promotionsApplied: quoteQuery.data.promotions_applied ?? [],
      rows: quoteQuery.data.breakdown.map((row) => ({
        date: row.date,
        amount: row.price,
        basePrice: row.base_price ?? row.price,
        source: row.source ?? "backend_quote",
        promotionsApplied: row.promotions_applied ?? []
      }))
    };
  }, [
    quoteQuery.data,
    quoteNights,
    selectedFormCategory
  ]);
  const canUseUnboundedManualRate = hasPermission("reservation:manual_rate");
  const canUseBoundedManualRate = hasPermission("reservation:manual_rate_limited");
  const isBoundedManualRate = !canUseUnboundedManualRate && canUseBoundedManualRate;
  const boundedManualRateContextAllowed = formValues.source === "direct" && !(Number(formValues.company_id) > 0);
  const boundedManualRateRange = useMemo(() => {
    const minAdjustment = quoteQuery.data?.manual_rate_min_adjustment_pct;
    const maxAdjustment = quoteQuery.data?.manual_rate_max_adjustment_pct;
    if (minAdjustment == null || maxAdjustment == null || !reservationQuote) return null;
    const minPct = Number(minAdjustment);
    const maxPct = Number(maxAdjustment);
    if (!Number.isFinite(minPct) || !Number.isFinite(maxPct)) return null;
    const roundCurrency = (amount: number) => Math.round((amount + Number.EPSILON) * 100) / 100;
    return {
      minimum: roundCurrency(reservationQuote.total * (1 + minPct / 100)),
      maximum: roundCurrency(reservationQuote.total * (1 + maxPct / 100)),
      minPct,
      maxPct
    };
  }, [quoteQuery.data, reservationQuote]);
  const boundedManualRateReady = Boolean(
    isBoundedManualRate &&
      boundedManualRateContextAllowed &&
      boundedManualRateRange &&
      !quoteQuery.isFetching &&
      !quoteQuery.isError
  );
  const canSetManualRate = canUseUnboundedManualRate || canUseBoundedManualRate;
  const manualRateCurrencyCode = isBoundedManualRate
    ? quoteQuery.data?.currency_code ?? reservationQuote?.currencyCode ?? manualTargetCurrency
    : manualTargetCurrency;
  const parsedDepositAmount = deferredCompanyBooking
    ? null
    : depositAmountInput.trim() === "" ? null : Number(depositAmountInput);
  // Si el operador no escribe una seña manual, el backend aplica la seña
  // porcentual configurada por el hotel (deposit_amount de la cotización) al
  // crear la reserva: el preview tiene que mostrar ese mismo valor, no "Por
  // configurar", para que lo mostrado antes de confirmar coincida con lo que
  // termina grabado en la reserva.
  const depositPreview =
    parsedDepositAmount !== null && Number.isFinite(parsedDepositAmount) && parsedDepositAmount >= 0
      ? parsedDepositAmount
      : (reservationQuote?.defaultDeposit ?? null);
  const quoteBalancePreview =
    reservationQuote && depositPreview !== null ? Math.max(reservationQuote.total - depositPreview, 0) : null;

  const calendarDays = useMemo(() => {
    const days: Array<{
      iso: string;
      label: string;
      occupancy: number;
      active: number;
      arrivals: number;
      departures: number;
    }> = [];
    const window = calendarRange === "month" ? 30 : 7;
    for (let i = 0; i < window; i += 1) {
      const date = new Date();
      date.setDate(date.getDate() + i);
      const iso = formatLocalIsoDate(date);
      const active = reservations.filter(
        (r) =>
          r.status !== "cancelled" &&
          new Date(r.check_in_date) <= date &&
          new Date(r.check_out_date) > date
      ).length;
      const arrivals = reservations.filter((r) => r.check_in_date === iso).length;
      const departures = reservations.filter((r) => r.check_out_date === iso).length;
      const occupancy = totalRooms > 0 ? Math.min(100, Math.round((active / totalRooms) * 100)) : 0;
      days.push({
        iso,
        label: date.toLocaleDateString("es-AR", { weekday: "short", month: "short", day: "numeric" }),
        occupancy,
        active,
        arrivals,
        departures
      });
    }
    return days;
  }, [calendarRange, reservations, totalRooms]);

  const totals = useMemo(() => {
    return reservations.reduce(
      (acc, item) => {
        if (item.status !== "cancelled" && item.status !== "checked_out") acc.active += 1;
        if (item.check_in_date === today) acc.checkInsToday += 1;
        if (item.check_out_date === today || item.status === "checked_out") acc.checkOutsToday += 1;
        if (item.status === "cancelled") acc.cancelled += 1;
        return acc;
      },
      { active: 0, checkInsToday: 0, checkOutsToday: 0, cancelled: 0 }
    );
  }, [reservations, today]);
  const pendingActions = pendingActionsQuery.data ?? [];
  const criticalPendingActions = pendingActions.filter((item) => item.priority === "critical").length;
  const reservationStatsError = Boolean(error) && reservations.length === 0;
  const reservationStatsLoading = isLoading;
  const reservationStatsValue = (value: number) =>
    reservationStatsLoading ? "…" : reservationStatsError ? "—" : value;
  const reservationStatsHelper = (normalHelper: string) =>
    reservationStatsLoading
      ? t("page.stats.loading")
      : reservationStatsError
        ? t("page.stats.error")
        : normalHelper;
  const reservationStatsHelperRole = reservationStatsLoading ? "status" : reservationStatsError ? "alert" : undefined;

  const openCreate = (initialValues: Partial<FormState> = {}) => {
    if (subscriptionBlocked) {
      setToast({ type: "error", message: subscriptionBlockReason || t("page.errors.blockedBySubscription") });
      return;
    }
    clearToast();
    setEditing(null);
    setFormValues({ ...defaultFormState(), ...initialValues });
    setFormError(null);
    setPricingPaymentMethod("base");
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setManualTargetCurrency("ARS");
    setManualRateReasonInput("");
    setPaidTotalAmountInput("");
    setPaidTotalChangeReasonInput("");
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
    setPaymentReferenceInput("");
    setCollectedBefore(false);
    setCollectedOn("");
    setPriorReceiptNote("");
    setRefundTargetTransactionId(null);
    setRefundReasonInput("");
    setRefundNightAmounts({});
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  // Quick-create shortcut (B1 global access) links here as /reservas?crear=1
  // instead of duplicating this ~600-line create form as a standalone
  // modal. Open it once on arrival and drop the flag so back/refresh
  // doesn't keep reopening it.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get("crear") === "1") {
      const positiveId = (value: string | null) => {
        const parsed = Number(value);
        return Number.isSafeInteger(parsed) && parsed > 0 ? String(parsed) : "";
      };
      const validDate = (value: string | null) => {
        if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
        const parsed = new Date(`${value}T00:00:00`);
        return Number.isNaN(parsed.getTime()) || formatLocalIsoDate(parsed) !== value ? "" : value;
      };
      const checkIn = validDate(searchParams.get("check_in_date"));
      const requestedCheckOut = validDate(searchParams.get("check_out_date"));
      const initialValues: Partial<FormState> = {
        room_id: positiveId(searchParams.get("room_id")),
        category_id: positiveId(searchParams.get("category_id"))
      };
      if (checkIn) {
        initialValues.check_in_date = checkIn;
        initialValues.check_out_date = requestedCheckOut > checkIn ? requestedCheckOut : addDaysIso(checkIn, 1);
      }
      openCreate(initialValues);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          ["crear", "room_id", "category_id", "check_in_date", "check_out_date"].forEach((key) => next.delete(key));
          return next;
        },
        { replace: true }
      );
    }
    // The global shortcut can change the query while this page is already mounted.
    // Re-run when the location search changes; the first run still handles direct links.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, setSearchParams]);

  const openEdit = (reservation: Reservation) => {
    if (!canManageCompanyReservation(reservation)) return;
    clearToast();
    setEditing(reservation);
    setFormValues({
      guest_id: String(reservation.guest_id),
      category_id: String(reservation.category_id),
      room_id: reservation.room_id ? String(reservation.room_id) : "",
      company_id: reservation.company_id ? String(reservation.company_id) : "",
      group_size: "1",
      check_in_date: reservation.check_in_date,
      check_out_date: reservation.check_out_date,
      num_adults: String(reservation.num_adults),
      num_children: String(reservation.num_children),
      notes: reservation.notes || "",
      arrival_time_hint: reservation.arrival_time_hint || "",
      reservation_comment: reservation.reservation_comment || "",
      source: reservation.source,
      status: reservation.status
    });
    setFormError(null);
    setPricingPaymentMethod("base");
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setManualTargetCurrency("ARS");
    setManualRateReasonInput("");
    setPaidTotalAmountInput(Number(reservation.total_amount || 0).toFixed(2));
    setPaidTotalChangeReasonInput("");
    setConfirmLargeTotalAdjustment(false);
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
    setPaymentReferenceInput("");
    setCollectedBefore(false);
    setCollectedOn("");
    setPriorReceiptNote("");
    setRefundTargetTransactionId(null);
    setRefundReasonInput("");
    setRefundNightAmounts({});
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    if (formBusy) return;
    setFormOpen(false);
    setEditing(null);
    setFormError(null);
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setManualRateReasonInput("");
    setPaidTotalAmountInput("");
    setPaidTotalChangeReasonInput("");
    setConfirmLargeTotalAdjustment(false);
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
    setPaymentReferenceInput("");
    setCollectedBefore(false);
    setCollectedOn("");
    setPriorReceiptNote("");
    setRefundTargetTransactionId(null);
    setRefundReasonInput("");
    setRefundNightAmounts({});
    setPaymentProofFile(null);
  };

  const collaborativeFormValues: FormState = editing
    ? {
        ...formValues,
        room_id:
          collaborativeReservation.draftValues.room_id === null || collaborativeReservation.draftValues.room_id === undefined
            ? ""
            : String(collaborativeReservation.draftValues.room_id),
        check_in_date: String(collaborativeReservation.draftValues.check_in_date ?? formValues.check_in_date),
        check_out_date: String(collaborativeReservation.draftValues.check_out_date ?? formValues.check_out_date),
        num_adults: String(collaborativeReservation.draftValues.num_adults ?? formValues.num_adults),
        num_children: String(collaborativeReservation.draftValues.num_children ?? formValues.num_children),
        notes: String(collaborativeReservation.draftValues.notes ?? ""),
        arrival_time_hint: String(collaborativeReservation.draftValues.arrival_time_hint ?? ""),
        reservation_comment: String(collaborativeReservation.draftValues.reservation_comment ?? "")
      }
    : formValues;

  const setReservationField = (
    field: "room_id" | "check_in_date" | "check_out_date" | "num_adults" | "num_children" | "notes" | "arrival_time_hint" | "reservation_comment",
    value: string
  ) => {
    setFormValues((previous) => ({ ...previous, [field]: value }));
    if (!editing) return;
    const normalizedValue =
      field === "room_id"
        ? value
          ? Number(value)
          : null
        : field === "num_adults" || field === "num_children"
          ? Number(value)
          : field === "arrival_time_hint" || field === "reservation_comment"
            ? value || null
            : value;
    collaborativeReservation.setField(field, normalizedValue);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (editing && !canManageCompanyReservation(editing)) return;
    if (subscriptionBlocked) {
      setFormError(subscriptionBlockReason || t("page.subscription.inactive"));
      return;
    }

    const currentFormValues = collaborativeFormValues;
    const categoryIdNum = Number(currentFormValues.category_id);
    let guestIdNum = Number(currentFormValues.guest_id);
    if (!editing && (!guestIdNum || Number.isNaN(guestIdNum))) {
      if (!hasQuickGuestFormData(guestForm)) {
        setFormError(t("page.errors.guestRequired"));
        return;
      }

      try {
        const newGuest = await guestMutation.mutateAsync({
          first_name: guestForm.first_name.trim() || "Invitado",
          last_name: guestForm.last_name.trim() || "Sin apellido",
          email: guestForm.email.trim() || undefined,
          phone: guestForm.phone.trim() || undefined,
          document_type: guestForm.document_type,
          document_number: guestForm.document_number.trim() || undefined
        });
        guestIdNum = newGuest.id;
        setFormValues((prev) => ({ ...prev, guest_id: String(newGuest.id) }));
        setGuestForm(emptyQuickGuestForm());
        showToast("success", t("page.messages.guestAutoCreated"));
      } catch (err) {
        const msg = err instanceof Error ? err.message : t("page.errors.guestCreateFailed");
        setFormError(msg);
        showToast("error", msg);
        return;
      }
    }    if (!categoryIdNum || Number.isNaN(categoryIdNum)) {
      setFormError(t("page.errors.categoryRequired"));
      return;
    }
    if (!currentFormValues.check_in_date || !currentFormValues.check_out_date) {
      setFormError(t("page.errors.datesRequired"));
      return;
    }

    const baseDatesValid = new Date(currentFormValues.check_out_date) > new Date(currentFormValues.check_in_date);
    if (!baseDatesValid) {
      setFormError(t("page.errors.datesInvalid"));
      return;
    }
    const groupSize = Number(currentFormValues.group_size || 1);
    if (!editing && (!Number.isInteger(groupSize) || groupSize < 1 || groupSize > 10)) {
      setFormError(t("page.errors.groupSizeInvalid"));
      return;
    }
    if (!editing && groupSize > 1 && currentFormValues.source !== "direct") {
      setFormError(t("page.errors.groupRequiresDirect"));
      return;
    }
    const manualTotalAmount = deferredCompanyBooking
      ? null
      : manualTotalAmountInput.trim() === "" ? null : Number(manualTotalAmountInput);
    if (!editing && groupSize > 1 && manualTotalAmount !== null) {
      setFormError(t("page.errors.groupManualRateUnsupported"));
      return;
    }
    if (!editing && manualTotalAmount !== null && (!Number.isFinite(manualTotalAmount) || manualTotalAmount < 0)) {
      setFormError(t("page.errors.invalidManualRate"));
      return;
    }
    const manualRateReason = manualRateReasonInput.trim();
    if (!editing && manualTotalAmount !== null && !manualRateReason) {
      setFormError(t("page.errors.manualRateReasonRequired"));
      return;
    }
    if (!editing && manualTotalAmount !== null && isBoundedManualRate) {
      if (!boundedManualRateContextAllowed) {
        setFormError(t("page.errors.boundedManualRateDirectOnly"));
        return;
      }
      if (!boundedManualRateReady || !boundedManualRateRange || !reservationQuote) {
        setFormError(t("page.errors.boundedManualRateUnavailable"));
        return;
      }
      if (normalizeCurrencyCode(quoteQuery.data?.currency_code) !== normalizeCurrencyCode(manualRateCurrencyCode)) {
        setFormError(t("page.errors.boundedManualRateCurrency"));
        return;
      }
      if (manualTotalAmount < boundedManualRateRange.minimum || manualTotalAmount > boundedManualRateRange.maximum) {
        setFormError(t("page.errors.boundedManualRateRange", {
          minimum: formatMoney(boundedManualRateRange.minimum, manualRateCurrencyCode),
          maximum: formatMoney(boundedManualRateRange.maximum, manualRateCurrencyCode)
        }));
        return;
      }
    }
    const comparableManualRateQuote = Boolean(
      !editing &&
      formValues.source === "direct" &&
      !(Number(currentFormValues.company_id) > 0) &&
      reservationQuote &&
      normalizeCurrencyCode(quoteQuery.data?.currency_code) === normalizeCurrencyCode(manualRateCurrencyCode)
    );
    const requiresLargeManualRateConfirmation = Boolean(
      manualTotalAmount !== null &&
      comparableManualRateQuote &&
      isLargeTotalAdjustment(reservationQuote?.total ?? Number.NaN, manualTotalAmount)
    );
    if (requiresLargeManualRateConfirmation && !confirmLargeTotalAdjustment) {
      setFormError(t("page.errors.largeTotalAdjustmentConfirmationRequired"));
      return;
    }
    const effectiveTotal = manualTotalAmount ?? reservationQuote?.total;
    if (!editing && parsedDepositAmount !== null) {
      if (!Number.isFinite(parsedDepositAmount) || parsedDepositAmount < 0) {
        setFormError(t("page.errors.invalidDeposit"));
        return;
      }
      if (effectiveTotal !== undefined && parsedDepositAmount > effectiveTotal) {
        setFormError(t("page.errors.depositExceedsTotal"));
        return;
      }
    }

    const commonPayload = {
      category_id: categoryIdNum,
      room_id: currentFormValues.room_id ? Number(currentFormValues.room_id) : null,
      check_in_date: currentFormValues.check_in_date,
      check_out_date: currentFormValues.check_out_date,
      num_adults: Number(currentFormValues.num_adults) || 1,
      num_children: Number(currentFormValues.num_children) || 0,
      notes: currentFormValues.notes || undefined,
      arrival_time_hint: currentFormValues.arrival_time_hint || null,
      reservation_comment: currentFormValues.reservation_comment.trim() || null
    };

    if (editing) {
      // "status" y "category_id" no forman parte de ReservationUpdate en el
      // backend (ver app/schemas/reservation.py): se ignoran en silencio.
      // Los selectores correspondientes están deshabilitados en modo edición
      // para no sugerir un cambio que no persiste; los estados reales se
      // cambian con Check-in/Check-out/Cancelar/Marcar no-show.
      const { category_id, ...updatePayload } = commonPayload;
      void category_id;
      const paidTotalAmount = paidTotalAmountInput.trim() === "" ? null : Number(paidTotalAmountInput);
      const currentTotal = Number(editing.total_amount || 0);
      const paidTotalChanged = paidTotalAmount !== null &&
        Math.round((paidTotalAmount + Number.EPSILON) * 100) !== Math.round((currentTotal + Number.EPSILON) * 100);
      if (paidTotalChanged && (!Number.isFinite(paidTotalAmount) || paidTotalAmount < 0)) {
        setFormError(t("page.errors.invalidPaidTotal"));
        return;
      }
      const paidTotalChangeReason = paidTotalChangeReasonInput.trim();
      if (paidTotalChanged && !paidTotalChangeReason) {
        setFormError(t("page.errors.paidTotalReasonRequired"));
        return;
      }
      if (
        paidTotalChanged &&
        paidTotalAmount !== null &&
        isLargeTotalAdjustment(currentTotal, paidTotalAmount) &&
        !confirmLargeTotalAdjustment
      ) {
        setFormError(t("page.errors.largeTotalAdjustmentConfirmationRequired"));
        return;
      }
      const updateData: ReservationUpdatePayload = { ...updatePayload };
      if (paidTotalChanged && paidTotalAmount !== null) {
        updateData.total_amount = paidTotalAmount;
        updateData.paid_total_change_reason = paidTotalChangeReason;
        updateData.confirm_large_total_adjustment = confirmLargeTotalAdjustment;
      }
      const submitUpdate = async (payload: ReservationUpdatePayload, forceRegularMutation = false): Promise<void> => {
        try {
          // When the authenticated collaboration channel is available, PATCH
          // performs the field-level merge under the server's current version.
          // A degraded Redis/WebSocket path never blocks ordinary PMS writes;
          // the regular endpoint remains the safe fallback.
          if (!forceRegularMutation && collaborativeReservation.status !== "idle") {
            if (Object.keys(collaborativeReservation.conflicts).length > 0) {
              setFormError(t("page.errors.collabConflicts"));
              return;
            }
            if (collaborativeReservation.isDirty) await collaborativeReservation.save();
          } else {
            await updateMutation.mutateAsync({
              id: editing.id,
              payload: { ...payload, client_version: editing.version }
            });
          }
          showToast("success", t("page.messages.reservationUpdated"));
          closeForm();
        } catch (err: unknown) {
          // GuestRestriction blocked the update -- prompt for an override
          // reason and retry the same request through the atomic endpoint.
          if (
            restrictionOverridePrompt.handleError(err, (override) =>
              void submitUpdate({ ...payload, restriction_override: override }, true)
            )
          ) {
            return;
          }
          const msg = err instanceof Error ? err.message : t("page.errors.saveFailed");
          setFormError(msg);
          showToast("error", msg);
        }
      };
      await submitUpdate(updateData, paidTotalChanged);
    } else {
      // B4: con tarifa manual, la cotización automática (y su quote_token) no
      // aplica -- el backend usaría el total manual igual, pero no tiene
      // sentido bloquear la creación esperando una cotización que no se va a
      // usar (y que puede ni existir si la categoría no tiene tarifa cargada).
      if (manualTotalAmount === null && (!reservationQuote?.quoteToken || quoteQuery.isFetching)) {
        setFormError(t("page.errors.waitForQuote"));
        return;
      }
      const createPayload: ReservationPayload = {
        ...commonPayload,
        guest_id: guestIdNum,
        source: formValues.source,
        company_id: Number(currentFormValues.company_id) > 0 ? Number(currentFormValues.company_id) : null,
        pricing_payment_method: pricingPaymentMethod === "base" ? null : pricingPaymentMethod,
        deposit_amount: parsedDepositAmount,
        ...(manualTotalAmount !== null
          ? {
              total_amount: manualTotalAmount,
              target_currency: manualRateCurrencyCode,
              manual_rate_reason: manualRateReason,
              confirm_large_total_adjustment: confirmLargeTotalAdjustment
            }
          : { quote_token: reservationQuote?.quoteToken })
      };
      const submitCreate = async (payload: ReservationPayload): Promise<void> => {
        try {
          if (groupSize > 1) {
            await createGroupMutation.mutateAsync(
              Array.from({ length: groupSize }, () => ({ ...payload, room_id: null }))
            );
            showToast("success", t("page.messages.reservationGroupCreated", { count: groupSize }));
            closeForm();
            return;
          }
          const created = await createMutation.mutateAsync(payload);
          showToast("success", t("page.messages.reservationCreated"));
          if (manualTotalAmount !== null) {
            // Keep the form open just long enough to show the operator what
            // currency/cotización the manual total was saved with -- closing
            // immediately would hide fx_rate_snapshot right after they asked
            // for a currency conversion.
            setLastCreatedReservation(created);
          } else {
            closeForm();
          }
        } catch (err: unknown) {
          if (
            restrictionOverridePrompt.handleError(err, (override) =>
              void submitCreate({ ...payload, restriction_override: override })
            )
          ) {
            return;
          }
          const rawMessage = err instanceof Error ? err.message : t("page.errors.createFailed");
          const noRoomsMatch = /^No rooms available in category (.+) for the requested dates$/.exec(rawMessage);
          const message = noRoomsMatch
            ? t("page.errors.noRoomsAvailable", { category: noRoomsMatch[1] })
            : rawMessage;
          setFormError(message);
          showToast("error", message);
        }
      };
      await submitCreate(createPayload);
    }
  };

  const canCancel = canCancelReservation;
  const canCheckIn = canCheckInReservation;
  const canCheckOut = canCheckOutReservation;
  const canNoShow = (status: ReservationStatus) => ["pending", "deposit_paid", "fully_paid"].includes(status);
  const canMoveRoom = (status: ReservationStatus) => !["cancelled", "checked_out", "no_show"].includes(status);
  const canAddCharge = (status: ReservationStatus) =>
    hasPermission("reservation:charge") && !["cancelled", "checked_out", "no_show"].includes(status);
  const metadataOnlyEdit = Boolean(
    editing && ["checked_in", "checked_out", "cancelled", "no_show"].includes(editing.status)
  );

  const showReservationActionError = (reservationId: number, message: string) => {
    setDetailsReservationId(reservationId);
    setDetailsActionError({ reservationId, message });
  };

  const handleCancel = async (reservation: Reservation) => {
    if (!canManageCompanyReservation(reservation)) return;
    try {
      await cancelMutation.mutateAsync(reservation.id);
      showToast("success", t("page.messages.cancelled"));
    } catch (err: unknown) {
      showReservationActionError(reservation.id, err instanceof Error ? err.message : t("page.errors.cancelFailed"));
    }
  };

  const handleCheckOut = async (reservation: Reservation) => {
    clearToast();
    // Cierra el loop cobro→estadía→egreso: si queda saldo, llevamos al operador a
    // cobrarlo (Pago total, que cae en la caja) en vez de fallar el check-out.
    // reservation.balance_due sólo cubre total_amount - amount_paid: no ve los
    // consumos cargados después del pago (BillingAdjustment), así que ese saldo
    // "operativo" recién lo conoce el backend al intentar el check-out.
    const balance = reservation.balance_due ?? 0;
    if (balance > 0.01) {
      if (canManageCompanyReservation(reservation)) openEdit(reservation);
      else openReservation(reservation.id);
      showToast(
        "info",
        t("page.messages.balancePendingCheckOut", { balance: formatMoney(balance, normalizeCurrencyCode(reservation.currency_code)) })
      );
      return;
    }
    try {
      await checkOutMutation.mutateAsync(reservation.id);
      showToast("success", t("page.messages.checkOutDone"));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t("page.errors.checkOutFailed");
      if (/saldo pendiente/i.test(message)) {
        if (canManageCompanyReservation(reservation)) openEdit(reservation);
        else openReservation(reservation.id);
        showToast("info", `${message}${t("page.messages.checkOutBalanceHint")}`);
        return;
      }
      showReservationActionError(reservation.id, message);
    }
  };

  const handleCheckAvailability = async () => {
    setAvailabilityError(null);
    if (!availabilityForm.category_id || !availabilityForm.check_in_date || !availabilityForm.check_out_date) {
      setAvailabilityError(t("page.errors.availabilityFieldsRequired"));
      return;
    }
    const payload = {
      category_id: Number(availabilityForm.category_id),
      check_in_date: availabilityForm.check_in_date,
      check_out_date: availabilityForm.check_out_date
    };
    try {
      const data = await availabilityMutation.mutateAsync(payload);
      if (data.status === "ok") {
        showToast("success", t("page.messages.availableCount", { count: data.count }));
      } else {
        showToast("info", data.message);
      }
    } catch (err: unknown) {
      setAvailabilityError(err instanceof Error ? err.message : t("page.errors.availabilityFailed"));
    }
  };

  const handleAllocationRun = async () => {
    setAllocationError(null);
    if (subscriptionBlocked) {
      setAllocationError(subscriptionBlockReason || t("page.errors.blockedBySubscriptionAllocation"));
      return;
    }
    if (
      allocationForm.horizon_start &&
      allocationForm.horizon_end &&
      new Date(allocationForm.horizon_end) < new Date(allocationForm.horizon_start)
    ) {
      setAllocationError(t("page.errors.horizonInvalid"));
      return;
    }

    if (allocationForm.apply && !window.confirm(t("page.allocation.confirmApply"))) return;

    try {
      const run = await allocationRunMutation.mutateAsync(allocationForm);
      showToast("success", t("page.messages.allocationRecalculated", { created: run.assignments_created, moved: run.moved_count }));
    } catch (err: unknown) {
      setAllocationError(err instanceof Error ? err.message : t("page.errors.allocationFailed"));
    }
  };

  const handleRevertMovementGroup = async (group: RoomMovementGroup) => {
    const moves = group.move_events.length;
    const confirmed = window.confirm(
      t("page.confirm.revertGroup", {
        id: group.id,
        count: moves,
        moveWord: moves === 1 ? t("page.allocation.moveSingular") : t("page.allocation.movePlural")
      })
    );
    if (!confirmed) return;

    try {
      const revertedGroup = await revertMovementGroupMutation.mutateAsync(group.id);
      if (revertedGroup.is_reverted) {
        showToast("success", t("page.messages.groupReverted", { id: group.id }));
      } else {
        showToast("info", t("page.messages.groupRevertPartial", { id: group.id }));
      }
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.revertGroupFailed"));
    }
  };

  const isManualPaymentMethod = manualPaymentMethods.includes(paymentMethod);
  const canOperateCash = hasPermission("cash:operate");
  const canEmailPaymentReceipt = hasPermission("payment:receipt_email");
  const paymentFxRate = paymentTenderCurrency === paymentReservationCurrency
    ? 1
    : Number(paymentFxQuoteQuery.data?.rate ?? 0);
  const paymentFxReady = Number.isFinite(paymentFxRate) && paymentFxRate > 0;
  const hasMatchingCashSession = Boolean(
    collectedBefore ||
    paymentMethod !== "cash" ||
    cashSessionsQuery.data?.some(
      (cashSession) => cashSession.status === "open" && cashSession.currency_code.toUpperCase() === paymentTenderCurrency
    )
  );
  const canRegisterSelectedPayment = canOperateCash &&
    (paymentMethod === "cash" || isManualPaymentMethod) &&
    paymentFxReady &&
    hasMatchingCashSession;
  const canRecordPriorReceipt = hasPermission("cash:record_prior_receipt");
  const canRefundPayment = hasPermission("payment:refund");
  const refundablePaymentOptions = (paymentSummary?.transactions ?? [])
    .filter((transaction) => transaction.status === "completed" && transaction.type !== "refund")
    .map((transaction) => {
      const refundedAmount = (paymentSummary?.transactions ?? [])
        .filter(
          (refund) =>
            refund.status === "completed" &&
            refund.type === "refund" &&
            refund.refund_of_transaction_id === transaction.id
        )
        .reduce((total, refund) => total + Number(refund.amount || 0), 0);
      return {
        ...transaction,
        refundableRemaining: Math.max(0, Number(transaction.amount || 0) - refundedAmount)
      };
    })
    .filter((transaction) => transaction.refundableRemaining > 0.01);
  const selectedRefundTargetId =
    refundablePaymentOptions.find((transaction) => transaction.id === refundTargetTransactionId)?.id ??
    refundablePaymentOptions[0]?.id ??
    null;
  const selectedRefundTarget = refundablePaymentOptions.find((transaction) => transaction.id === selectedRefundTargetId) ?? null;
  const companyNightRefundableAllocations = selectedRefundTarget?.company_night_charge_refundable_allocations ?? [];
  const isCompanyNightRefund = companyNightRefundableAllocations.length > 0;
  const refundCents = (amount: number) => Math.round((amount + Number.EPSILON) * 100);
  const enteredCompanyNightRefunds = companyNightRefundableAllocations.map((allocation) => {
    const rawAmount = refundNightAmounts[allocation.charge_id] ?? "";
    const hasValue = rawAmount.trim().length > 0;
    const amount = hasValue ? Number(rawAmount) : 0;
    const amountCents = Number.isFinite(amount) ? refundCents(amount) : NaN;
    const remainingAmount = Number(allocation.remaining_amount);
    const remainingCents = Number.isFinite(remainingAmount) ? refundCents(remainingAmount) : -1;
    const valid = !hasValue || (
      Number.isFinite(amount) &&
      Math.abs(amount * 100 - amountCents) < 0.0001 &&
      amountCents > 0 &&
      amountCents <= remainingCents
    );
    return { ...allocation, rawAmount, hasValue, amountCents, remainingAmount, remainingCents, valid };
  });
  const selectedCompanyNightRefunds = enteredCompanyNightRefunds.filter(
    (allocation) => allocation.hasValue && allocation.valid && allocation.amountCents > 0
  );
  const hasInvalidCompanyNightRefund = enteredCompanyNightRefunds.some((allocation) => !allocation.valid);
  const companyNightRefundBaseAmount = selectedCompanyNightRefunds.reduce(
    (total, allocation) => total + allocation.amountCents,
    0
  ) / 100;
  const originalTenderAmount = Number(selectedRefundTarget?.amount ?? 0);
  const originalAppliedAmount = Number(selectedRefundTarget?.applied_amount ?? 0);
  const originalTenderPerAppliedUnit = originalTenderAmount > 0 && originalAppliedAmount > 0
    ? originalTenderAmount / originalAppliedAmount
    : null;
  const companyNightRefundTenderAmount = isCompanyNightRefund && originalTenderPerAppliedUnit
    ? refundCents(companyNightRefundBaseAmount * originalTenderPerAppliedUnit) / 100
    : null;
  const companyNightRefundAppliedAmount = companyNightRefundTenderAmount !== null && originalTenderPerAppliedUnit
    ? refundCents(companyNightRefundTenderAmount / originalTenderPerAppliedUnit) / 100
    : null;
  const companyNightRefundMatchesAppliedAmount = companyNightRefundBaseAmount > 0 &&
    companyNightRefundAppliedAmount !== null &&
    Math.abs(refundCents(companyNightRefundAppliedAmount) - refundCents(companyNightRefundBaseAmount)) <= 1;
  const companyNightRefundWithinSource = companyNightRefundTenderAmount !== null && selectedRefundTarget !== null &&
    refundCents(companyNightRefundTenderAmount) <= refundCents(selectedRefundTarget.refundableRemaining);
  const canSubmitCompanyNightRefund = isCompanyNightRefund &&
    selectedCompanyNightRefunds.length > 0 &&
    !hasInvalidCompanyNightRefund &&
    companyNightRefundTenderAmount !== null &&
    companyNightRefundTenderAmount > 0 &&
    companyNightRefundMatchesAppliedAmount &&
    companyNightRefundWithinSource;
  const companyNightRefundValidationMessage = !isCompanyNightRefund
    ? null
    : originalTenderPerAppliedUnit === null
      ? t("drawer.errors.refundAppliedAmountUnavailable")
      : selectedRefundTarget && paymentTenderCurrency !== selectedRefundTarget.currency
        ? t("drawer.errors.refundMustUseOriginalCurrency", { currency: selectedRefundTarget.currency })
      : hasInvalidCompanyNightRefund
        ? t("drawer.errors.refundNightAmountInvalid")
        : companyNightRefundBaseAmount > 0 && !companyNightRefundWithinSource
          ? t("drawer.errors.refundNightAmountExceedsSource")
          : companyNightRefundBaseAmount > 0 && !companyNightRefundMatchesAppliedAmount
            ? t("drawer.errors.refundNightRoundingMismatch")
            : null;
  useEffect(() => {
    setRefundNightAmounts({});
    setPaymentAmountInput("");
  }, [selectedRefundTargetId]);
  const hotelConfigQuery = useHotelConfig();
  const availablePaymentMethods = useMemo(
    () => enabledPaymentMethods(hotelConfigQuery.data),
    [hotelConfigQuery.data]
  );
  // Keep the selected method valid: if config disables the current one, fall back
  // to the first enabled method.
  React.useEffect(() => {
    if (availablePaymentMethods.length === 0) return;
    if (!availablePaymentMethods.includes(paymentMethod)) {
      setPaymentMethod(availablePaymentMethods[0]);
    }
  }, [availablePaymentMethods, paymentMethod]);
  const hasOpenCashSession = useMemo(
    () => (cashSessionsQuery.data ?? []).some((s) => s.status === "open"),
    [cashSessionsQuery.data]
  );
  const surchargesQuery = usePaymentSurcharges();
  const activeSurcharge = useMemo(
    () => (surchargesQuery.data ?? []).find((s) => s.payment_method === paymentMethod && s.is_active) ?? null,
    [surchargesQuery.data, paymentMethod]
  );
  const groupPaymentMethods = availablePaymentMethods.filter(
    (method): method is Exclude<PaymentMethod, "mercado_pago" | "paypal"> =>
      method !== "mercado_pago" && method !== "paypal"
  );
  const groupPaymentSurcharge = (surchargesQuery.data ?? []).find(
    (surcharge) => surcharge.payment_method === groupPaymentMethod && surcharge.is_active
  ) ?? null;
  const groupPaymentTotal = Number(groupPaymentTotalInput);
  const groupPaymentGross = Number.isFinite(groupPaymentTotal)
    ? grossWithSurcharge(groupPaymentTotal, groupPaymentSurcharge)
    : 0;
  const groupAllocatedCents = Object.values(groupPaymentAllocations).reduce((sum, raw) => {
    const amount = Number(raw);
    return Number.isFinite(amount) && amount > 0 ? sum + Math.round((amount + Number.EPSILON) * 100) : sum;
  }, 0);
  const groupRequestedCents = Number.isFinite(groupPaymentTotal) && groupPaymentTotal > 0
    ? Math.round((groupPaymentTotal + Number.EPSILON) * 100)
    : 0;
  const groupPaymentManualMethod = manualPaymentMethods.includes(groupPaymentMethod);

  const openGroupPayment = (group: ReservationGroupSummary) => {
    if (group.company_billing_deferred) return;
    const remaining = group.reservations.filter((child) => Number(child.balance_due ?? 0) > 0);
    const initialAllocations = Object.fromEntries(
      remaining.map((child) => [child.id, Number(child.balance_due).toFixed(2)])
    );
    const initialTotal = remaining.reduce((sum, child) => sum + Number(child.balance_due ?? 0), 0);
    setPayingGroup(group);
    setGroupPaymentAllocations(initialAllocations);
    setGroupPaymentTotalInput(initialTotal > 0 ? initialTotal.toFixed(2) : "");
    setGroupPaymentMethod(groupPaymentMethods[0] ?? "cash");
    setGroupPaymentReference("");
    setGroupPaymentDescription("");
    setGroupPaymentError(null);
  };

  const submitGroupPayment = async () => {
    if (!payingGroup || groupPaymentMutation.isPending) return;
    const receivedAmount = Number(groupPaymentTotalInput);
    if (!Number.isFinite(receivedAmount) || receivedAmount <= 0) {
      setGroupPaymentError(t("page.groups.paymentInvalidTotal"));
      return;
    }
    if (!groupPaymentMethods.includes(groupPaymentMethod as Exclude<PaymentMethod, "mercado_pago" | "paypal">)) {
      setGroupPaymentError(t("page.groups.paymentMethodUnavailable"));
      return;
    }
    if (groupPaymentManualMethod && !groupPaymentReference.trim()) {
      setGroupPaymentError(t("page.groups.paymentReferenceRequired"));
      return;
    }
    const allocations = payingGroup.reservations
      .map((child) => ({
        reservation_id: child.id,
        received_amount: Number(groupPaymentAllocations[child.id] || 0)
      }))
      .filter((item) => Number.isFinite(item.received_amount) && item.received_amount > 0);
    const allocationCents = allocations.reduce(
      (sum, item) => sum + Math.round((item.received_amount + Number.EPSILON) * 100),
      0
    );
    if (!allocations.length || allocationCents !== Math.round((receivedAmount + Number.EPSILON) * 100)) {
      setGroupPaymentError(t("page.groups.paymentAllocationMismatch"));
      return;
    }
    if (allocations.some((allocation) => {
      const child = payingGroup.reservations.find((item) => item.id === allocation.reservation_id);
      return child?.balance_due == null || allocation.received_amount - Number(child.balance_due) > 0.01;
    })) {
      setGroupPaymentError(t("page.groups.paymentExceedsBalance"));
      return;
    }
    const payload: ReservationGroupPaymentPayload = {
      received_amount: receivedAmount,
      currency: payingGroup.currency_code,
      payment_method: groupPaymentMethod as Exclude<PaymentMethod, "mercado_pago" | "paypal">,
      manual_reference: groupPaymentManualMethod ? groupPaymentReference.trim() : undefined,
      description: groupPaymentDescription.trim() || undefined,
      allocations
    };
    try {
      await groupPaymentMutation.mutateAsync({ groupId: payingGroup.id, payload });
    } catch {
      // The guarded mutation keeps its detailed API error in this form until closed.
    }
  };
  const editingGuest = useGuest(editing?.guest_id || undefined).data;
  const paymentLinksQuery = usePaymentLinks(editing?.id || undefined);
  const paymentLinkCreate = usePaymentLinkCreate(editing?.id || undefined);
  const paymentLinkCancel = usePaymentLinkCancel(editing?.id || undefined);
  const canReadPaymentProofs =
    hasPermission("payment:proof:view") ||
    hasPermission("payment:proof:review") ||
    hasPermission("cash:operate");
  const paymentProofsQuery = usePaymentProofs(editing?.id || undefined, canReadPaymentProofs);
  const paymentProofMutations = usePaymentProofMutations(editing?.id || undefined);
  // Closing mid-save would drop the in-flight payment/link result, so the
  // close controls are disabled (not silently ignored) until it settles.
  const reservationSavePending =
    createMutation.isPending || createGroupMutation.isPending || updateMutation.isPending;
  const formBusy =
    createMutation.isPending ||
    createGroupMutation.isPending ||
    updateMutation.isPending ||
    collaborativeReservation.isSaving ||
    paymentMutation.isPending ||
    paymentProofMutations.submitMutation.isPending ||
    paymentProofMutations.approveMutation.isPending ||
    paymentProofMutations.rejectMutation.isPending ||
    paymentLinkCreate.isPending ||
    paymentLinkCancel.isPending;
  const detailsSummary = detailsSummaryQuery.data;
  const detailsOperations = detailsOperationsQuery.data;
  const detailsDeferredCompanyBilling = isDeferredCompanyReservation(detailsReservation);
  const detailsFinancialsLoading = detailsSummaryQuery.isLoading;
  const detailsGuest = useGuest(detailsReservation?.guest_id || undefined).data;
  React.useEffect(() => {
    setCommunicationRecipient(detailsGuest?.email ?? "");
  }, [detailsReservationId, detailsGuest?.email]);
  const editingCurrencyCode = normalizeCurrencyCode(paymentSummary?.currency_code ?? editing?.currency_code);
  const proposedTotalDraft = paidTotalAmountInput.trim() === "" ? null : Number(paidTotalAmountInput);
  const proposedManualRateTotalDraft = manualTotalAmountInput.trim() === "" ? null : Number(manualTotalAmountInput);
  const largeManualRateAdjustmentDraft = Boolean(
    !editing &&
    formValues.source === "direct" &&
    !(Number(formValues.company_id) > 0) &&
    proposedManualRateTotalDraft !== null &&
    Number.isFinite(proposedManualRateTotalDraft) &&
    proposedManualRateTotalDraft >= 0 &&
    reservationQuote &&
    normalizeCurrencyCode(quoteQuery.data?.currency_code) === normalizeCurrencyCode(manualRateCurrencyCode) &&
    isLargeTotalAdjustment(reservationQuote.total, proposedManualRateTotalDraft)
  );
  const largeTotalAdjustmentDraft = Boolean(
    editing &&
    proposedTotalDraft !== null &&
    Number.isFinite(proposedTotalDraft) &&
    proposedTotalDraft >= 0 &&
    isLargeTotalAdjustment(Number(editing.total_amount || 0), proposedTotalDraft)
  );
  const tenderPerReservationUnit = paymentTenderCurrency === editingCurrencyCode
    ? 1
    : Number(paymentFxQuoteQuery.data?.rate ?? 0);
  const conversionReady = Number.isFinite(tenderPerReservationUnit) && tenderPerReservationUnit > 0;
  const convertReservationToTender = (amount: number) =>
    conversionReady ? Number((amount * tenderPerReservationUnit).toFixed(2)) : null;
  const convertTenderToReservation = (amount: number) =>
    conversionReady ? Number((amount / tenderPerReservationUnit).toFixed(2)) : null;
  const suggestedDepositAmount = Math.max(
    Number(paymentSummary?.deposit_required ?? 0) - Number(paymentSummary?.amount_paid ?? 0),
    0
  );
  const requestedDepositPreview = paymentAmountInput.trim()
    ? Number(paymentAmountInput)
    : convertReservationToTender(suggestedDepositAmount) ?? suggestedDepositAmount;
  const depositAmountPreview = Number.isFinite(requestedDepositPreview) && requestedDepositPreview > 0
    ? Number(requestedDepositPreview.toFixed(2))
    : null;
  const canApprovePaymentProof = hasPermission("payment:proof:review");
  const detailsCurrencyCode = normalizeCurrencyCode(
    detailsSummary?.currency_code ??
      detailsOperations?.financial_summary.currency_code ??
      detailsReservation?.currency_code
  );
  const getPriorReceiptFields = (): Pick<PaymentRequest, "collected_before" | "collected_on" | "prior_receipt_note"> | null => {
    if (!collectedBefore) return {};
    if (paymentTenderCurrency !== editingCurrencyCode) {
      showToast("error", t("drawer.errors.priorReceiptOtherCurrency"));
      return null;
    }
    if (!canRecordPriorReceipt || paymentMethod !== "cash") {
      showToast("error", t("page.errors.priorReceiptPermissionRequired"));
      return null;
    }
    if (!collectedOn || !priorReceiptNote.trim()) {
      showToast("error", t("page.errors.priorReceiptDetailsRequired"));
      return null;
    }
    return {
      collected_before: true,
      collected_on: collectedOn,
      prior_receipt_note: priorReceiptNote.trim()
    };
  };
  const communicationMutation = useGuardedMutation<
    { delivery: ReservationEmailDelivery; deduplicated: boolean },
    unknown,
    { kind: ReservationEmailKind; resend: boolean; recipient?: string }
  >({
    mutationFn: ({ kind, resend, recipient }) => {
      if (!detailsReservationId) throw new Error(t("page.errors.communicationReservationMissing"));
      return sendReservationCommunication(
        detailsReservationId,
        { kind, recipient_email: (recipient ?? communicationRecipient).trim() || null, resend },
        session
      );
    },
    onSuccess: async (result) => {
      await communicationsQuery.refetch();
      const statusMessage = result.delivery.status === "accepted"
        ? t("page.errors.communicationAccepted")
        : result.delivery.status === "unknown"
          ? t("page.errors.communicationUnknown")
          : result.delivery.status === "failed"
            ? t("page.errors.communicationFailed")
            : t("page.errors.communicationPending");
      showToast(result.deduplicated ? "info" : result.delivery.status === "accepted" ? "success" : "error", statusMessage);
    },
    onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : t("page.errors.communicationFailed"))
  });

  const handlePayDeposit = async () => {
    if (!editing || !paymentSummary) return;
    if (!canRegisterSelectedPayment) {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const manualReference = isManualPaymentMethod ? paymentReferenceInput.trim() : undefined;
    if (isManualPaymentMethod && !manualReference) {
      showToast("error", t("drawer.errors.manualPaymentReferenceRequired"));
      return;
    }
    const due = Math.max(
      Number(paymentSummary.deposit_required ?? 0) - Number(paymentSummary.amount_paid ?? 0),
      0
    );
    if (due <= 0.01) {
      showToast("info", t("page.messages.depositAlreadyCovered"));
      return;
    }
    const enteredAmount = paymentAmountInput.trim();
    const suggestedTenderAmount = convertReservationToTender(due);
    const requestedAmount = enteredAmount
      ? Number(enteredAmount)
      : suggestedTenderAmount ?? due;
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    const appliedPreview = convertTenderToReservation(requestedAmount);
    if (!Number.isFinite(requestedAmount) || requestedAmount <= 0 || appliedPreview === null || appliedPreview <= 0) {
      showToast("error", t("page.errors.invalidPartialAmount"));
      return;
    }
    const amount = Number(requestedAmount.toFixed(2));
    const roundedBalance = Number(balance.toFixed(2));
    if (!Number.isFinite(balance) || appliedPreview > roundedBalance + 0.01) {
      showToast("error", t("page.errors.invalidPartialAmount"));
      return;
    }
    const roundedSuggested = Number((suggestedTenderAmount ?? due).toFixed(2));
    if (
      enteredAmount &&
      amount !== roundedSuggested &&
      !window.confirm(
        t("page.confirm.depositAmountDiff", {
          suggested: formatMoney(roundedSuggested, paymentTenderCurrency),
          amount: formatMoney(amount, paymentTenderCurrency)
        })
      )
    ) {
      return;
    }
    const priorReceiptFields = getPriorReceiptFields();
    if (!priorReceiptFields) return;
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount,
        payment_method: paymentMethod,
        transaction_type: "deposit",
        currency: paymentTenderCurrency,
        manual_reference: manualReference,
        ...priorReceiptFields
      });
      setPaymentAmountInput("");
      setPaymentReferenceInput("");
      setCollectedBefore(false);
      setCollectedOn("");
      setPriorReceiptNote("");
      showToast("success", t("page.messages.depositRegistered"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handlePayFull = async () => {
    if (!editing || !paymentSummary) return;
    if (!canRegisterSelectedPayment) {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const manualReference = isManualPaymentMethod ? paymentReferenceInput.trim() : undefined;
    if (isManualPaymentMethod && !manualReference) {
      showToast("error", t("drawer.errors.manualPaymentReferenceRequired"));
      return;
    }
    const due = paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0;
    if (due <= 0.01) {
      showToast("info", t("page.messages.noBalanceDue"));
      return;
    }
    const priorReceiptFields = getPriorReceiptFields();
    if (!priorReceiptFields) return;
    const tenderAmount = convertReservationToTender(Number(due));
    if (tenderAmount === null) {
      showToast("error", paymentFxQuoteQuery.error instanceof Error ? paymentFxQuoteQuery.error.message : t("drawer.errors.paymentFxQuoteUnavailable"));
      return;
    }
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: tenderAmount,
        payment_method: paymentMethod,
        transaction_type: "full_payment",
        currency: paymentTenderCurrency,
        manual_reference: manualReference,
        ...priorReceiptFields
      });
      setPaymentReferenceInput("");
      setCollectedBefore(false);
      setCollectedOn("");
      setPriorReceiptNote("");
      showToast("success", t("page.messages.fullPaymentDone"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handlePayPartial = async () => {
    if (!editing || !paymentSummary) return;
    if (!canRegisterSelectedPayment) {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const manualReference = isManualPaymentMethod ? paymentReferenceInput.trim() : undefined;
    if (isManualPaymentMethod && !manualReference) {
      showToast("error", t("drawer.errors.manualPaymentReferenceRequired"));
      return;
    }
    const amount = Number(paymentAmountInput);
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    const appliedPreview = convertTenderToReservation(amount);
    if (!Number.isFinite(amount) || amount <= 0 || appliedPreview === null || appliedPreview > balance + 0.01) {
      showToast("error", t("page.errors.invalidPartialAmount"));
      return;
    }
    const priorReceiptFields = getPriorReceiptFields();
    if (!priorReceiptFields) return;
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "partial_payment",
        currency: paymentTenderCurrency,
        manual_reference: manualReference,
        ...priorReceiptFields
      });
      setPaymentAmountInput("");
      setPaymentReferenceInput("");
      setCollectedBefore(false);
      setCollectedOn("");
      setPriorReceiptNote("");
      showToast("success", t("page.messages.partialPaymentDone"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handleRefund = async () => {
    if (!editing || !paymentSummary) return;
    if (!canRefundPayment) return;
    if (paymentMethod !== "cash") {
      showToast("info", t("page.messages.refundCashOnly"));
      return;
    }
    const refundTarget = refundablePaymentOptions.find((transaction) => transaction.id === selectedRefundTargetId);
    if (!refundTarget) {
      showToast("error", t("drawer.errors.refundSourceRequired"));
      return;
    }
    const refundReason = refundReasonInput.trim();
    if (!refundReason) {
      showToast("error", t("drawer.errors.refundReasonRequired"));
      return;
    }
    if (paymentTenderCurrency !== refundTarget.currency) {
      showToast("error", t("drawer.errors.refundMustUseOriginalCurrency", { currency: refundTarget.currency }));
      return;
    }
    if (isCompanyNightRefund && !canSubmitCompanyNightRefund) {
      showToast("error", companyNightRefundValidationMessage ?? t("drawer.errors.refundNightAmountInvalid"));
      return;
    }
    const amount = isCompanyNightRefund
      ? companyNightRefundTenderAmount ?? 0
      : Number(paymentAmountInput);
    if (!Number.isFinite(amount) || amount <= 0 || amount > refundTarget.refundableRemaining + 0.01) {
      showToast("error", t("page.errors.invalidRefundAmount"));
      return;
    }
    if (!window.confirm(t("page.confirm.refund", { amount: formatMoney(amount, refundTarget.currency) }))) return;
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "refund",
        currency: refundTarget.currency,
        description: t("page.messages.refundManualDescription"),
        refund_of_transaction_id: refundTarget.id,
        refund_reason: refundReason,
        ...(isCompanyNightRefund
          ? {
              company_night_charge_refund_allocations: selectedCompanyNightRefunds.map((allocation) => ({
                charge_id: allocation.charge_id,
                amount: allocation.amountCents / 100
              }))
            }
          : {})
      });
      setPaymentAmountInput("");
      setRefundReasonInput("");
      setRefundNightAmounts({});
      showToast("success", t("page.messages.refundDone"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.refundFailed"));
    }
  };

  const handleSubmitTransferProof = async () => {
    if (!editing || !paymentSummary) return;
    if (!paymentProofFile) {
      showToast("error", t("page.errors.proofImageRequired"));
      return;
    }
    const amount = Number(paymentAmountInput);
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > balance + 0.01) {
      showToast("error", t("page.errors.invalidPartialAmount"));
      return;
    }
    try {
      await paymentProofMutations.submitMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        image_base64: await readFileAsDataUrl(paymentProofFile, t("page.errors.proofReadFailed")),
        original_filename: paymentProofFile.name
      });
      setPaymentAmountInput("");
      setPaymentProofFile(null);
      showToast("success", t("page.messages.proofSubmitted"));
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.proofSubmitFailed"));
    }
  };

  const handleViewPaymentProof = async (proofId: number) => {
    setViewingPaymentProofId(proofId);
    try {
      const blob = await fetchPaymentProofImage(proofId, session);
      if (paymentProofPreview) URL.revokeObjectURL(paymentProofPreview.url);
      setPaymentProofPreview({ proofId, url: URL.createObjectURL(blob) });
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.proofOpenFailed"));
    } finally {
      setViewingPaymentProofId(null);
    }
  };

  const closePaymentProofPreview = () => {
    if (paymentProofPreview) URL.revokeObjectURL(paymentProofPreview.url);
    setPaymentProofPreview(null);
  };

  const handleApprovePaymentProof = async (proofId: number) => {
    try {
      await paymentProofMutations.approveMutation.mutateAsync(proofId);
      showToast("success", t("page.messages.proofApproved"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.proofApproveFailed"));
    }
  };

  const handleRejectPaymentProof = async (proofId: number) => {
    const reason = paymentProofRejectReason.trim();
    if (!reason) {
      showToast("error", t("page.errors.rejectReasonRequired"));
      return;
    }
    try {
      await paymentProofMutations.rejectMutation.mutateAsync({ proofId, reason });
      setRejectingPaymentProofId(null);
      setPaymentProofRejectReason("");
      showToast("success", t("page.messages.proofRejected"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.proofRejectFailed"));
    }
  };

  const handleGenerateDepositLink = async () => {
    if (!editing || !paymentSummary) return;
    const due =
      Math.max(
        Number(paymentSummary.deposit_required ?? 0) - Number(paymentSummary.amount_paid ?? 0),
        0
      ) ||
      (paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (due <= 0.01) {
      showToast("info", t("page.messages.noAmountForLink"));
      return;
    }
    const email = editingGuest?.email?.trim();
    if (!email) {
      showToast("error", t("page.errors.guestEmailRequired"));
      return;
    }
    try {
      const created = await paymentLinkCreate.mutateAsync({
        reservation_id: editing.id,
        requested_amount: Number(due.toFixed(2)),
        recipient_email: email,
        recipient_name: editingGuest ? `${editingGuest.first_name} ${editingGuest.last_name}`.trim() : undefined,
        recipient_phone: editingGuest?.phone || undefined,
        currency: editingCurrencyCode,
        title: t("page.form.depositLinkTitle", { code: editing.confirmation_code })
      });
      showToast(
        "success",
        created.execution_mode === "local_only" || !created.payable
          ? t("page.messages.localLinkCreated")
          : t("page.messages.depositLinkGenerated")
      );
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.linkGenerateFailed"));
    }
  };

  const handleCancelPaymentLink = async (linkId: number) => {
    try {
      await paymentLinkCancel.mutateAsync(linkId);
      showToast("success", t("page.messages.linkCancelled"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.linkCancelFailed"));
    }
  };

  const openDetails = (reservation: Reservation) => {
    clearToast();
    setDetailsReservationId(reservation.id);
    setDetailsActionError(null);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep", origin_room_disposition: "", origin_room_disposition_note: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openDetailsById = (reservationId: number) => {
    clearToast();
    setDetailsReservationId(reservationId);
    setDetailsActionError(null);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep", origin_room_disposition: "", origin_room_disposition_note: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openRefundReview = async (reservationId: number) => {
    clearToast();
    let reservation = reservations.find((item) => item.id === reservationId);
    if (!reservation) {
      try {
        reservation = await getReservation(reservationId, session);
      } catch {
        showToast("error", t("page.pendingActions.refundReviewOpenError"));
        return;
      }
    }
    if (!canManageCompanyReservation(reservation)) {
      openDetailsById(reservationId);
      return;
    }
    // Open the existing reservation/payment form. The refund mutation still
    // requires its normal permission, cash session, reason, and step-up checks.
    openEdit(reservation);
  };
  const closeDetails = () => {
    setDetailsReservationId(null);
    setDetailsActionError(null);
    setCommunicationRecipient("");
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep", origin_room_disposition: "", origin_room_disposition_note: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openGuest = (guestId: number) => setGuestIdOpen(guestId);
  const closeGuest = () => setGuestIdOpen(null);

  const handleResolveExternal = async (reservationId: number) => {
    try {
      await resolveExternalMutation.mutateAsync({
        reservationId,
        payload: { notes: t("page.messages.externalResolveNote") }
      });
      showToast("success", t("page.messages.externalResolved"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.externalResolveFailed"));
    }
  };

  const handleClearManualReview = async (reservationId: number) => {
    try {
      await clearManualReviewMutation.mutateAsync({
        reservationId,
        payload: { notes: t("page.messages.manualReviewCloseNote") }
      });
      showToast("success", t("page.messages.manualReviewClosed"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.manualReviewCloseFailed"));
    }
  };

  const handleRoomMove = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!detailsReservation || !canManageCompanyReservation(detailsReservation)) return;
    if (!roomMoveForm.to_room_id || !roomMoveForm.reason_code.trim()) {
      showToast("error", t("page.errors.roomMoveFieldsRequired"));
      return;
    }
    if (detailsReservation.version == null) {
      showToast("error", t("page.errors.roomMoveVersionUnavailable"));
      return;
    }
    if (detailsReservation.status === "checked_in" && (!roomMoveForm.origin_room_disposition || (roomMoveForm.origin_room_disposition !== "cleaning" && !roomMoveForm.origin_room_disposition_note.trim()))) {
      showToast("error", t("page.errors.roomMoveOriginDispositionRequired"));
      return;
    }
    try {
      await roomMoveMutation.mutateAsync({
        reservationId: detailsReservation.id,
        payload: {
          client_version: detailsReservation.version,
          to_room_id: Number(roomMoveForm.to_room_id),
          reason_code: roomMoveForm.reason_code.trim(),
          notes: roomMoveForm.notes.trim() || null,
          price_action: roomMoveForm.price_action,
          origin_room_disposition: detailsReservation.status === "checked_in" ? roomMoveForm.origin_room_disposition as "cleaning" | "available" | "maintenance" : null,
          origin_room_disposition_note: detailsReservation.status === "checked_in" ? roomMoveForm.origin_room_disposition_note.trim() || null : null
        }
      });
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.roomMoveFailed"));
    }
  };

  const handleNoShow = async () => {
    if (!detailsReservation || !canNoShow(detailsReservation.status)) return;
    if (!window.confirm(t("page.confirm.noShow"))) return;
    try {
      await noShowMutation.mutateAsync({
        reservationId: detailsReservation.id,
        payload: { client_version: detailsReservation.version ?? 0, notes: noShowNotes.trim() || null }
      });
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.noShowFailed"));
    }
  };

  const exportVoucher = () => {
    if (!detailsReservation) return;
    if (detailsFinancialsLoading || detailsOperationsQuery.isLoading) {
      showToast("info", t("page.messages.waitForFinancialSummary"));
      return;
    }
    const summary = detailsSummary;
    const operationalBalanceDue = resolveVoucherOperationalBalance(
      detailsOperations?.financial_summary.operational_balance_due,
      summary?.operational_balance_due
    );
    if (!isDeferredCompanyReservation(detailsReservation) && operationalBalanceDue === null) {
      showToast("error", t("drawer.errors.voucherFinancialSummaryUnavailable"));
      return;
    }
    const guest = detailsGuest;
    const win = window.open("", "_blank");
    if (!win) {
      showToast("error", t("page.details.receipt.popupBlocked"));
      return;
    }
    const htmlText = (value: unknown) => escapeHtml(value);
    const html = `
      <html>
        <head>
          <title>${htmlText(t("page.voucher.title", { code: detailsReservation.confirmation_code }))}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 16px; color: #0f172a; }
            h1 { margin: 0 0 8px 0; }
            .grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
            .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
            .muted { color: #475569; font-size: 12px; margin: 0; }
            .label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.02em; }
          </style>
        </head>
        <body>
          <h1>${htmlText(t("page.voucher.heading"))}</h1>
          <p class="muted">${htmlText(t("page.voucher.code", { code: detailsReservation.confirmation_code }))}</p>
          <div class="grid">
            <div class="card">
              <p class="label">${htmlText(t("page.voucher.reservationLabel"))}</p>
              <p>${htmlText(t("page.voucher.checkIn"))} <strong>${htmlText(detailsReservation.check_in_date)}</strong></p>
              <p>${htmlText(t("page.voucher.checkOut"))} <strong>${htmlText(detailsReservation.check_out_date)}</strong></p>
              <p>${htmlText(t("page.voucher.roomCat"))} <strong>${htmlText(detailsReservation.room_number ?? t("page.voucher.unassigned"))} / ${htmlText(detailsReservation.category_name ?? categoryNameById.get(detailsReservation.category_id) ?? t("page.common.informationUnavailable"))}</strong></p>
              <p>${htmlText(t("page.voucher.status"))} <strong>${htmlText(statusConfig[detailsReservation.status]?.label ?? detailsReservation.status)}</strong></p>
            </div>
            <div class="card">
              <p class="label">${htmlText(t("page.voucher.guestLabel"))}</p>
              <p>${htmlText(guest ? `${guest.first_name} ${guest.last_name}` : t("page.voucher.guestIdFallback", { id: detailsReservation.guest_id }))}</p>
              <p>${htmlText(t("page.voucher.email"))} ${htmlText(guest?.email ?? "-")}</p>
              <p>${htmlText(t("page.voucher.phone"))} ${htmlText(guest?.phone ?? "-")}</p>
            </div>
          </div>
          <div class="card" style="margin-top:12px;">
            <p class="label">${htmlText(t("page.voucher.financeLabel"))}</p>
            ${isDeferredCompanyReservation(detailsReservation)
              ? `<p>${htmlText(t("page.details.deferredCompanyFinance"))}</p>`
              : `<p>${htmlText(t("page.voucher.total"))} <strong>${htmlText(formatMoney(detailsOperations?.financial_summary.operational_total_amount ?? summary?.operational_total_amount ?? detailsReservation.total_amount ?? 0, detailsCurrencyCode))}</strong></p>
            <p>${htmlText(t("page.voucher.paid"))} <strong>${htmlText(formatMoney(detailsOperations?.financial_summary.amount_paid ?? summary?.amount_paid ?? detailsReservation.amount_paid ?? 0, detailsCurrencyCode))}</strong></p>
            <p>${htmlText(t("page.voucher.balance"))} <strong>${htmlText(formatMoney(operationalBalanceDue ?? 0, detailsCurrencyCode))}</strong></p>`}
          </div>
        </body>
      </html>`;
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
    win.close();
  };

  const printPaymentReceipt = async (transaction: PaymentSummary["transactions"][number]) => {
    if (!detailsReservation || !canPrintPaymentReceipt(transaction.status, canOperateCash)) return;

    // Open synchronously from the click so browser popup protection still permits the async fetch.
    const win = window.open("", "_blank");
    if (!win) {
      showToast("error", t("page.details.receipt.popupBlocked"));
      return;
    }
    win.opener = null;
    win.document.write("<!doctype html><meta charset=\"utf-8\"><title>Hotels-PMS</title><p>" + escapeHtml(t("page.details.receipt.loading")) + "</p>");
    win.document.close();

    try {
      // The server rechecks permission, hotel scope and payment status and returns only persisted receipt fields.
      const receiptData = await getPaymentReceiptData(transaction.id, session);
      if (!canPrintPaymentReceipt(receiptData.status, canOperateCash)) {
        win.close();
        showToast("error", t("page.details.receipt.unavailable"));
        return;
      }
      const amount = Number(receiptData.amount);
      const grossAmount = Number(receiptData.gross_amount ?? receiptData.amount);
      const surchargeAmount = Number(receiptData.fee_amount ?? 0);
      if (![amount, grossAmount, surchargeAmount].every(Number.isFinite)) {
        win.close();
        showToast("error", t("page.details.receipt.invalidAmount"));
        return;
      }

      const language = t("page.details.receipt.language") as "en" | "es";
      const locale = language === "en" ? "en-US" : "es-AR";
      const createdAt = new Date(receiptData.created_at);
      let receiptDate = receiptData.created_at;
      if (!Number.isNaN(createdAt.getTime())) {
        try {
          receiptDate = new Intl.DateTimeFormat(locale, {
            dateStyle: "medium",
            timeStyle: "short",
            hourCycle: "h23",
            timeZone: receiptData.hotel_timezone
          }).format(createdAt);
        } catch {
          receiptDate = new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
            timeStyle: "short",
            hourCycle: "h23"
          }).format(createdAt);
        }
      }

      const isRefund = receiptData.type === "refund";
      const hasSurcharge = !isRefund && Math.abs(surchargeAmount) > 0.01;
      const appliedCurrency = receiptData.applied_currency || receiptData.currency;
      const hasFxConversion = appliedCurrency !== receiptData.currency
        && Number.isFinite(Number(receiptData.fx_rate_snapshot))
        && Number(receiptData.fx_rate_snapshot) > 0;
      const amountToShow = isRefund ? Math.abs(amount) : Math.abs(grossAmount);
      const receiptHtml = buildPaymentReceiptHtml({
        language,
        title: t("page.details.receipt.documentTitle", { id: receiptData.id }),
        heading: isRefund ? t("page.details.receipt.refundHeading") : t("page.details.receipt.heading"),
        internalNotice: t("page.details.receipt.internalNotice"),
        hotelLabel: t("page.details.receipt.hotelLabel"),
        hotelName: receiptData.hotel_name,
        operationLabel: t("page.details.receipt.operationLabel"),
        operationId: receiptData.id,
        reservationLabel: t("page.details.receipt.reservationLabel"),
        reservationCode: receiptData.confirmation_code,
        dateLabel: t("page.details.receipt.dateLabel"),
        date: receiptDate,
        movementLabel: t("page.details.receipt.movementLabel"),
        movement: t("page.details.receipt.types." + receiptData.type, { defaultValue: receiptData.type }),
        paymentMethodLabel: t("page.details.receipt.paymentMethodLabel"),
        paymentMethod: t("drawer.payment.methods." + receiptData.method, { defaultValue: receiptData.method }),
        statusLabel: t("page.details.receipt.statusLabel"),
        status: t("page.details.receipt.statuses." + receiptData.status, { defaultValue: receiptData.status }),
        appliedAmountLabel: hasSurcharge || hasFxConversion ? t("page.details.receipt.appliedAmountLabel") : undefined,
        appliedAmount: hasSurcharge || hasFxConversion
          ? formatMoney(Math.abs(Number(receiptData.applied_amount ?? amount)), appliedCurrency)
          : null,
        fxRateLabel: hasFxConversion ? t("page.details.receipt.fxRateLabel") : undefined,
        fxRate: hasFxConversion
          ? `1 ${appliedCurrency} = ${Number(receiptData.fx_rate_snapshot).toLocaleString(language === "es" ? "es-AR" : "en-US", { maximumFractionDigits: 6 })} ${receiptData.currency}`
          : null,
        surchargeLabel: hasSurcharge ? t("page.details.receipt.surchargeLabel") : undefined,
        surcharge: hasSurcharge ? formatMoney(Math.abs(surchargeAmount), receiptData.currency) : null,
        amountLabel: isRefund ? t("page.details.receipt.refundAmountLabel") : t("page.details.receipt.amountLabel"),
        amount: formatMoney(amountToShow, receiptData.currency),
        referenceLabel: t("page.details.receipt.referenceLabel"),
        manualReference: receiptData.manual_reference,
        refundOfLabel: t("page.details.receipt.refundOfLabel"),
        refundOfTransactionId: receiptData.refund_of_transaction_id
      });

      if (win.closed) return;
      win.document.open();
      win.document.write(receiptHtml);
      win.document.close();
      win.focus();
      win.onafterprint = () => win.close();
      win.setTimeout(() => win.print(), 100);
    } catch {
      if (!win.closed) win.close();
      showToast("error", t("page.details.receipt.unavailable"));
    }
  };

  const openReceiptEmailDialog = (transactionId: number, trigger: HTMLButtonElement) => {
    if (!canOperateCash || !canEmailPaymentReceipt) return;
    receiptEmailTriggerRef.current = trigger;
    const recipientEmail = detailsGuest?.email?.trim() ?? "";
    const previousAttempt = receiptEmailAttemptsRef.current.get(transactionId);
    const previousOutcomeBlocksNewAttempt = previousAttempt &&
      ["sending", "sent", "unknown"].includes(previousAttempt.status);
    const attempt = previousOutcomeBlocksNewAttempt ||
      (previousAttempt && previousAttempt.recipientEmail === recipientEmail)
      ? previousAttempt
      : recipientEmail
        ? {
            transactionId,
            recipientEmail,
            idempotencyKey: newPaymentReceiptEmailIdempotencyKey(transactionId),
            status: "confirm" as const
          }
        : {
            transactionId,
            recipientEmail: "",
            idempotencyKey: "",
            status: "failed" as const
          };
    receiptEmailAttemptsRef.current.set(transactionId, attempt);
    receiptEmailAttemptRef.current = attempt;
    setReceiptEmailAttempt(attempt);
  };

  const closeReceiptEmailDialog = () => {
    if (receiptEmailAttemptRef.current?.status === "sending") return;
    receiptEmailAttemptRef.current = null;
    setReceiptEmailAttempt(null);
    window.requestAnimationFrame(() => receiptEmailTriggerRef.current?.focus());
  };

  const sendReceiptEmail = async () => {
    const currentAttempt = receiptEmailAttemptRef.current;
    if (
      !currentAttempt ||
      !currentAttempt.recipientEmail ||
      !currentAttempt.idempotencyKey ||
      !["confirm", "failed"].includes(currentAttempt.status)
    ) {
      return;
    }
    const sendingAttempt: PaymentReceiptEmailAttempt = { ...currentAttempt, status: "sending" };
    receiptEmailAttemptsRef.current.set(currentAttempt.transactionId, sendingAttempt);
    receiptEmailAttemptRef.current = sendingAttempt;
    setReceiptEmailAttempt(sendingAttempt);
    window.requestAnimationFrame(() => receiptEmailTitleRef.current?.focus());

    try {
      await emailPaymentReceipt(
        sendingAttempt.transactionId,
        { recipient_email: sendingAttempt.recipientEmail },
        session,
        sendingAttempt.idempotencyKey
      );
      const sentAttempt: PaymentReceiptEmailAttempt = { ...sendingAttempt, status: "sent" };
      receiptEmailAttemptsRef.current.set(sentAttempt.transactionId, sentAttempt);
      receiptEmailAttemptRef.current = sentAttempt;
      setReceiptEmailAttempt(sentAttempt);
      window.requestAnimationFrame(() => receiptEmailCloseRef.current?.focus());
    } catch (error: unknown) {
      const detail = error instanceof ApiError &&
        error.payload && typeof error.payload === "object" && "detail" in error.payload &&
        typeof error.payload.detail === "string"
        ? error.payload.detail.toLocaleLowerCase()
        : "";
      const definiteEmailPreflightFailure = error instanceof ApiError &&
        error.status === 503 && detail.includes("correo del hotel no está disponible");
      const priorUnknownOutcome = error instanceof ApiError && error.status === 409 &&
        /(resultado.*no está confirmado|envío previo sin resultado|envío anterior no está confirmado)/i.test(detail);
      const unknownOutcome = priorUnknownOutcome ||
        (error instanceof ApiError
          ? error.status === 408 || (error.status >= 500 && !definiteEmailPreflightFailure)
          : true);
      const failedAttempt: PaymentReceiptEmailAttempt = {
        ...sendingAttempt,
        status: unknownOutcome ? "unknown" : "failed"
      };
      receiptEmailAttemptsRef.current.set(failedAttempt.transactionId, failedAttempt);
      receiptEmailAttemptRef.current = failedAttempt;
      setReceiptEmailAttempt(failedAttempt);
      if (unknownOutcome) window.requestAnimationFrame(() => receiptEmailCloseRef.current?.focus());
    }
  };

  const guestHistory = useMemo(
    () => (guestIdOpen ? reservations.filter((r) => r.guest_id === guestIdOpen) : []),
    [guestIdOpen, reservations]
  );

  const recentMovementGroups = movementGroupsQuery.data ?? [];

  return (
    <div className="space-y-6">
      {toast && (
        <div
          className="fixed right-6 top-20 z-40 flex w-80 items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xl"
          role={toast.type === "error" ? "alert" : "status"}
          aria-live={toast.type === "error" ? "assertive" : "polite"}
        >
          <span
            className={`mt-1 h-2 w-2 rounded-full ${
              toast.type === "success" ? "bg-emerald-500" : toast.type === "error" ? "bg-rose-500" : "bg-amber-500"
            }`}
          />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">
              {toast.type === "success" ? t("page.toast.success") : toast.type === "error" ? t("page.toast.error") : t("page.toast.info")}
            </p>
            <p className="text-sm text-slate-700">{toast.message}</p>
          </div>
          <button className="ml-auto text-xs text-slate-500 hover:text-slate-800" onClick={() => setToast(null)} type="button">
            {t("page.toast.close")}
          </button>
        </div>
      )}
      {pageActionError && (
        <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" data-testid="reservation-page-action-error" role="alert" aria-live="assertive">
          <p className="flex-1">{pageActionError}</p>
          <button type="button" className="text-xs font-semibold hover:text-rose-950" onClick={() => setPageActionError(null)}>
            {t("page.toast.close")}
          </button>
        </div>
      )}
      {checkInMutation.isPending && (
        <div className="fixed right-6 top-20 z-40 rounded-xl border border-sky-200 bg-white p-3 text-sm text-sky-900 shadow-xl" role="status" aria-live="polite">
          {t("page.messages.checkInProcessing")}
        </div>
      )}
      {checkOutMutation.isPending && (
        <div className="fixed right-6 top-20 z-40 rounded-xl border border-sky-200 bg-white p-3 text-sm text-sky-900 shadow-xl" role="status" aria-live="polite">
          {t("page.messages.checkOutProcessing")}
        </div>
      )}
      {subscriptionBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {subscriptionBlockReason} {t("page.subscriptionBanner.cta")}{" "}
          <Link to="/settings/subscription" className="font-semibold underline">
            {t("page.subscriptionBanner.linkLabel")}
          </Link>
          .
        </div>
      )}

      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.header.eyebrow")}</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{t("page.header.title")}</h1>
          <p className="text-sm text-slate-600">{t("page.header.subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:opacity-60"
            onClick={() => openCreate()}
            type="button"
            disabled={subscriptionBlocked}
          >
            {t("page.header.createButton")}
          </button>
          {hasPermission("reservation:ota_record") ? (
            <button
              className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:opacity-60"
              onClick={() => {
                if (subscriptionBlocked) {
                  setToast({ type: "error", message: subscriptionBlockReason || t("page.errors.blockedBySubscription") });
                  return;
                }
                setOtaFormOpen(true);
              }}
              type="button"
              disabled={subscriptionBlocked}
              data-testid="open-manual-ota"
            >
              {t("page.header.otaButton")}
            </button>
          ) : null}
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            {t("page.header.dashboardLink")}
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <ReservationStatCard label={t("page.stats.activeLabel")} value={reservationStatsValue(totals.active)} helper={reservationStatsHelper(t("page.stats.activeHelper"))} helperRole={reservationStatsHelperRole} testId="reservation-stat-active" />
        <ReservationStatCard label={t("page.stats.checkInsTodayLabel")} value={reservationStatsValue(totals.checkInsToday)} helper={reservationStatsHelper(today)} helperRole={reservationStatsHelperRole} testId="reservation-stat-checkins" />
        <ReservationStatCard label={t("page.stats.checkOutsTodayLabel")} value={reservationStatsValue(totals.checkOutsToday)} helper={reservationStatsHelper(today)} helperRole={reservationStatsHelperRole} testId="reservation-stat-checkouts" />
        <ReservationStatCard label={t("page.stats.cancelledLabel")} value={reservationStatsValue(totals.cancelled)} helper={reservationStatsHelper(t("page.stats.cancelledHelper"))} helperRole={reservationStatsHelperRole} testId="reservation-stat-cancelled" />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.pendingActions.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.pendingActions.title")}</h2>
            <p className="text-sm text-slate-600">
              {t("page.pendingActions.description")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
              {pendingActionsQuery.isError
                ? t("page.pendingActions.unavailableCount")
                : t("page.pendingActions.openCount", { count: pendingActions.length })}
            </span>
            {criticalPendingActions > 0 ? (
              <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700">
                {t("page.pendingActions.criticalCount", { count: criticalPendingActions })}
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {pendingActionsQuery.isLoading ? (
            <p className="text-sm text-slate-500" role="status" data-testid="reservations-pending-actions-loading">{t("page.pendingActions.loading")}</p>
          ) : pendingActionsQuery.isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert" data-testid="reservations-pending-actions-error">
              <span>{t("page.pendingActions.error")}</span>
              <button
                type="button"
                onClick={() => void pendingActionsQuery.refetch()}
                className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100"
              >
                {t("page.pendingActions.retry")}
              </button>
            </div>
          ) : pendingActions.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {t("page.pendingActions.empty")}
            </div>
          ) : (
            pendingActions.map((action) => {
              const priorityClass = priorityClassName[action.priority];
              const isResolveExternal =
                action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
              const isManualReview = action.code === "manual_review_required";
              const isDepositRefundReview = action.code === "refund_deposit";

              return (
                <div key={`${action.reservation_id}:${action.action_key}`} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${priorityClass}`}>
                          {t(`page.priority.${action.priority}`)}
                        </span>
                        <span className="text-xs font-semibold text-slate-700">{action.confirmation_code}</span>
                        <span className="text-xs text-slate-500">
                          {action.check_in_date} → {action.check_out_date}
                        </span>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{action.title}</p>
                        <p className="text-sm text-slate-600">{action.detail}</p>
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                        <span>
                          {t("page.pendingActions.statusPrefix", {
                            status: statusConfig[action.reservation_status as ReservationStatus]?.label ?? action.reservation_status
                          })}
                        </span>
                        <span>{t("page.pendingActions.sourcePrefix", { source: sourceLabel(action.source_provider_code || action.source) })}</span>
                        {action.payment_collection_model ? (
                          <span>{t("page.pendingActions.collectionPrefix", { model: enumLabel("collection", action.payment_collection_model) })}</span>
                        ) : null}
                        {action.settlement_status ? (
                          <span>{t("page.pendingActions.settlementPrefix", { status: enumLabel("settlement", action.settlement_status) })}</span>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openDetailsById(action.reservation_id)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300"
                      >
                        {t("page.pendingActions.viewButton")}
                      </button>
                      {isDepositRefundReview && canRefundPayment ? (
                        <button
                          type="button"
                          data-testid={`pending-action-review-refund-${action.reservation_id}`}
                          onClick={() => void openRefundReview(action.reservation_id)}
                          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900 hover:border-amber-300"
                        >
                          {t("page.pendingActions.reviewRefund")}
                        </button>
                      ) : null}
                      {isManualReview ? (
                        <button
                          type="button"
                          onClick={() => handleClearManualReview(action.reservation_id)}
                          disabled={clearManualReviewMutation.isPending}
                          className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {t("page.pendingActions.closeReview")}
                        </button>
                      ) : null}
                      {isResolveExternal ? (
                        <button
                          type="button"
                          onClick={() => handleResolveExternal(action.reservation_id)}
                          disabled={resolveExternalMutation.isPending}
                          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {t("page.pendingActions.markResolved")}
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.calendar.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">
              {calendarRange === "week" ? t("page.calendar.titleWeek") : t("page.calendar.titleMonth")}
            </h2>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCalendarRange("week")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "week" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              {t("page.calendar.week")}
            </button>
            <button
              type="button"
              onClick={() => setCalendarRange("month")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "month" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              {t("page.calendar.month")}
            </button>
          </div>
        </div>
        <div className="mt-3 space-y-2">
          {calendarDays.map((day) => (
            <div key={day.iso} className="flex items-center gap-3">
              <div className="w-40 text-sm font-semibold text-slate-800">{day.label}</div>
              <div className="relative h-3 flex-1 rounded-full bg-slate-100">
                <div
                  className="absolute left-0 top-0 h-3 rounded-full bg-brand-500"
                  style={{ width: `${day.occupancy}%`, minWidth: day.occupancy > 0 ? "6px" : "0" }}
                />
              </div>
              <span className="w-12 text-xs text-right font-semibold text-slate-700">{day.occupancy}%</span>
              <div className="flex gap-2 text-[11px]">
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">{t("page.calendar.arrivals", { count: day.arrivals })}</span>
                <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">{t("page.calendar.departures", { count: day.departures })}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.filters.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.filters.title")}</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
            <LocalizedDateField
              id="reservation-filter-from"
              label={t("page.common.from")}
              value={fromDate}
              onChange={setFromDate}
              className="flex flex-col"
              inputClassName="mt-1 rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              labelClassName="text-xs font-semibold text-slate-600"
              placeholder={t("page.dateInput.datePlaceholder")}
              chooseDateLabel={t("page.dateInput.chooseDate")}
              invalidMessage={t("page.dateInput.invalidDate")}
            />
            <LocalizedDateField
              id="reservation-filter-to"
              label={t("page.common.to")}
              value={toDate}
              onChange={setToDate}
              className="flex flex-col"
              inputClassName="mt-1 rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              labelClassName="text-xs font-semibold text-slate-600"
              placeholder={t("page.dateInput.datePlaceholder")}
              chooseDateLabel={t("page.dateInput.chooseDate")}
              invalidMessage={t("page.dateInput.invalidDate")}
            />
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              {t("page.filters.status")}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ReservationStatus | "all" | "")}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              >
                <option value="">{t("page.statusOptions.all")}</option>
                <option value="pending">{t("page.statusOptions.pending")}</option>
                <option value="deposit_paid">{t("page.statusOptions.depositPaid")}</option>
                <option value="fully_paid">{t("page.statusOptions.fullyPaid")}</option>
                <option value="pre_check_in">{t("page.statusOptions.preCheckIn")}</option>
                <option value="checked_in">{t("page.statusOptions.checkedIn")}</option>
                <option value="checked_out">{t("page.statusOptions.checkedOut")}</option>
                <option value="cancelled">{t("page.statusOptions.cancelled")}</option>
              </select>
            </label>
            {hasPermission("company:manage") && companyOptions.length > 0 && (
              <label className="flex flex-col text-xs font-semibold text-slate-600">
                {t("page.filters.company")}
                <select
                  data-testid="reservation-company-filter"
                  value={companyFilter}
                  onChange={(event) => setCompanyFilter(event.target.value)}
                  className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
                >
                  <option value="">{t("page.filters.allCompanies")}</option>
                  {companyOptions.map((company) => (
                    <option key={company.id} value={company.id}>{company.display_name || company.legal_name}</option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              onClick={() => {
                setFromDate("");
                setToDate("");
                setStatusFilter("");
                setCompanyFilter("");
              }}
              className="self-end rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
            >
              {t("page.filters.clear")}
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.availability.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.availability.title")}</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {availabilityMutation.isPending && <span className="text-slate-600" role="status" aria-live="polite">{t("page.availability.querying")}</span>}
            {availabilityMutation.isError && <span className="text-rose-600" role="alert">{t("page.availability.queryError")}</span>}
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="text-xs font-semibold text-slate-600">
            {t("page.availability.category")}
            <select
              value={availabilityForm.category_id}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, category_id: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            >
              <option value="">{t("page.availability.categoryPlaceholder")}</option>
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <LocalizedDateField
            id="availability-check-in"
            label={t("page.availability.checkIn")}
            value={availabilityForm.check_in_date}
            onChange={(value) => setAvailabilityForm((prev) => ({ ...prev, check_in_date: value }))}
            className="w-full"
            labelClassName="text-xs font-semibold text-slate-600"
            inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm"
            placeholder={t("page.dateInput.datePlaceholder")}
            chooseDateLabel={t("page.dateInput.chooseDate")}
            invalidMessage={t("page.dateInput.invalidDate")}
          />
          <LocalizedDateField
            id="availability-check-out"
            label={t("page.availability.checkOut")}
            value={availabilityForm.check_out_date}
            onChange={(value) => setAvailabilityForm((prev) => ({ ...prev, check_out_date: value }))}
            className="w-full"
            labelClassName="text-xs font-semibold text-slate-600"
            inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm"
            placeholder={t("page.dateInput.datePlaceholder")}
            chooseDateLabel={t("page.dateInput.chooseDate")}
            invalidMessage={t("page.dateInput.invalidDate")}
          />
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleCheckAvailability}
              className="w-full rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
              disabled={availabilityMutation.isPending}
            >
              {t("page.availability.submit")}
            </button>
          </div>
        </div>
        {availabilityMutation.data && (
          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {availabilityMutation.data.status === "ok" ? (
              <div className="space-y-1">
                <p>
                  {t("page.availability.available", { count: availabilityMutation.data.count })}
                </p>
                <p className="text-xs text-slate-600">
                  {t("page.availability.ids", {
                    ids: availabilityMutation.data.available_rooms.join(", ") || t("page.availability.noMatches")
                  })}
                </p>
              </div>
            ) : (
              <p>{availabilityMutation.data.message}</p>
            )}
          </div>
        )}
        {availabilityError && (
          <div className="mt-3 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" data-testid="availability-action-error" role="alert" aria-live="assertive">
            <p className="flex-1">{availabilityError}</p>
            <button type="button" className="text-xs font-semibold hover:text-rose-950" onClick={() => setAvailabilityError(null)}>
              {t("page.toast.close")}
            </button>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.allocation.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.allocation.title")}</h2>
            <p className="text-sm text-slate-600">
              {t("page.allocation.description")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {allocationRunMutation.isPending ? <span>{t("page.allocation.recalculating")}</span> : null}
            {movementGroupsQuery.isFetching ? <span>{t("page.allocation.updatingGroups")}</span> : null}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-5">
          <LocalizedDateField
            id="allocation-horizon-from"
            label={t("page.common.from")}
            value={allocationForm.horizon_start}
            onChange={(value) => setAllocationForm((prev) => ({ ...prev, horizon_start: value }))}
            className="w-full"
            labelClassName="text-xs font-semibold text-slate-600"
            inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm"
            placeholder={t("page.dateInput.datePlaceholder")}
            chooseDateLabel={t("page.dateInput.chooseDate")}
            invalidMessage={t("page.dateInput.invalidDate")}
          />
          <LocalizedDateField
            id="allocation-horizon-to"
            label={t("page.common.to")}
            value={allocationForm.horizon_end}
            onChange={(value) => setAllocationForm((prev) => ({ ...prev, horizon_end: value }))}
            className="w-full"
            labelClassName="text-xs font-semibold text-slate-600"
            inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm"
            placeholder={t("page.dateInput.datePlaceholder")}
            chooseDateLabel={t("page.dateInput.chooseDate")}
            invalidMessage={t("page.dateInput.invalidDate")}
          />
          <label className="flex items-center gap-2 self-end rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={allocationForm.apply}
              onChange={(e) => setAllocationForm((prev) => ({ ...prev, apply: e.target.checked }))}
              className="h-4 w-4 rounded border-slate-300 text-brand-600"
            />
            {t("page.allocation.applyChanges")}
          </label>
          <div className="flex items-end md:col-span-2">
            <button
              type="button"
              onClick={handleAllocationRun}
              disabled={allocationRunMutation.isPending || subscriptionBlocked}
              className="w-full rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t("page.allocation.run")}
            </button>
          </div>
        </div>

        {allocationError && (
          <div className="mt-3 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" data-testid="allocation-action-error" role="alert" aria-live="assertive">
            <p className="flex-1">{allocationError}</p>
            <button type="button" className="text-xs font-semibold hover:text-rose-950" onClick={() => setAllocationError(null)}>
              {t("page.toast.close")}
            </button>
          </div>
        )}

        {allocationRunMutation.data ? (
          <div className="mt-3 grid gap-2 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-900 sm:grid-cols-4">
            <div>
              <p className="text-xs text-emerald-700">{t("page.allocation.run_id")}</p>
              <p className="font-semibold">#{allocationRunMutation.data.run_id}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">{t("page.allocation.status")}</p>
              <p className="font-semibold">{allocationRunMutation.data.status}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">{t("page.allocation.assigned")}</p>
              <p className="font-semibold">{allocationRunMutation.data.assignments_created}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">{t("page.allocation.movedUnassigned")}</p>
              <p className="font-semibold">
                {allocationRunMutation.data.moved_count} / {allocationRunMutation.data.unassigned_count}
              </p>
            </div>
          </div>
        ) : null}

        <div className="mt-4 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.allocation.recentGroups")}</p>
            <button
              type="button"
              onClick={() => movementGroupsQuery.refetch()}
              className="text-xs font-semibold text-brand-700 hover:underline"
            >
              {t("page.allocation.refresh")}
            </button>
          </div>
          {movementGroupsQuery.isError ? (
            <div className="px-3 py-3 text-sm text-rose-700">
              {t("page.allocation.loadError")}{" "}
              {movementGroupsQuery.error instanceof Error ? movementGroupsQuery.error.message : t("page.allocation.unknownError")}
            </div>
          ) : movementGroupsQuery.isLoading ? (
            <div className="px-3 py-3 text-sm text-slate-500">{t("page.allocation.loadingGroups")}</div>
          ) : recentMovementGroups.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-600">{t("page.allocation.noGroups")}</div>
          ) : (
            <div className="divide-y divide-slate-200">
              {recentMovementGroups.map((group) => {
                const moveCount = group.move_events.length;
                return (
                  <div key={group.id} className="flex flex-col gap-3 px-3 py-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{t("page.allocation.group", { id: group.id })}</p>
                        <span
                          className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                            group.is_reverted ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {group.is_reverted ? t("page.allocation.reverted") : t("page.allocation.active")}
                        </span>
                        <span className="text-xs text-slate-500">{formatDateTime(group.created_at, hotelConfigQuery.data?.hotel_timezone)}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("page.allocation.groupTrigger", {
                          reason: group.trigger_reason,
                          count: moveCount,
                          moveWord: moveCount === 1 ? t("page.allocation.moveSingular") : t("page.allocation.movePlural")
                        })}
                      </p>
                      {group.notes ? <p className="mt-1 text-xs text-slate-500">{group.notes}</p> : null}
                    </div>
                    {hasPermission("reservation:movement_group_revert") ? (
                      <button
                        type="button"
                        onClick={() => handleRevertMovementGroup(group)}
                        disabled={group.is_reverted || revertMovementGroupMutation.isPending || subscriptionBlocked}
                        className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {t("page.allocation.revert")}
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.list.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.list.title")}</h2>
            {isFetching && <p className="text-xs text-slate-500">{t("page.list.updating")}</p>}
            {error && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-rose-700" role="alert" data-testid="reservations-load-error">
                <span>{t("page.list.loadError", { message: (error as Error).message })}</span>
                <button
                  type="button"
                  onClick={() => void refetchReservations()}
                  className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 font-semibold text-rose-800 hover:bg-rose-100"
                >
                  {t("page.list.retry")}
                </button>
              </div>
            )}
          </div>
          <span className="text-xs text-slate-500">{t("page.list.total", { count: reservations.length })}</span>
        </div>
        {(reservationGroupsQuery.data?.length ?? 0) > 0 && (
          <section className="border-b border-slate-200 p-4" aria-label={t("page.groups.title")}>
            <h3 className="mb-3 text-sm font-semibold text-slate-800">{t("page.groups.title")}</h3>
            <div className="grid gap-3 lg:grid-cols-2">
              {reservationGroupsQuery.data?.slice(0, RESERVATION_GROUP_SUMMARY_LIMIT).map((group) => {
                const groupDeferredBilling = Boolean(
                  group.company_billing_deferred ||
                  (group.company_id && companyOptions.find((company) => company.id === group.company_id)?.payment_deferred !== false)
                );
                return (
                  <article
                  key={group.id}
                  data-testid={`reservation-group-summary-${group.id}`}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-slate-900">{group.guest_name}</p>
                      {group.company_name && <p className="text-xs text-slate-600">{group.company_name}</p>}
                    </div>
                    <span className="rounded-full bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-800">
                      {t("page.groups.rooms", { count: group.reservation_count })}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    {group.check_in_date} → {group.check_out_date} · {group.reservation_codes.join(", ")}
                  </p>
                  {groupDeferredBilling ? (
                    <p className="mt-3 text-xs text-amber-900">{t("page.groups.deferredCompanyBilling")}</p>
                  ) : <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div><dt className="text-slate-500">{t("page.groups.total")}</dt><dd className="font-semibold">{formatMoney(group.total_amount, group.currency_code)}</dd></div>
                    <div><dt className="text-slate-500">{t("page.groups.paid")}</dt><dd className="font-semibold">{formatMoney(group.amount_paid, group.currency_code)}</dd></div>
                    <div><dt className="text-slate-500">{t("page.groups.balance")}</dt><dd className="font-semibold">{formatMoney(group.balance_due, group.currency_code)}</dd></div>
                  </dl>}
                  {hasPermission("cash:operate") && !groupDeferredBilling && Number(group.balance_due ?? 0) > 0 && (
                    <button
                      type="button"
                      onClick={() => openGroupPayment(group)}
                      disabled={groupPaymentMutation.isPending || groupPaymentMethods.length === 0}
                      className="mt-3 rounded-lg bg-brand-700 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
                      data-testid={`reservation-group-payment-${group.id}`}
                    >
                      {t("page.groups.registerPayment")}
                    </button>
                  )}
                  </article>
                );
              })}
            </div>
          </section>
        )}
        {/* Dense table needs real column width -- desktop/tablet only. */}
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">{t("page.list.columns.code")}</th>
                <th className="px-4 py-2">{t("page.list.columns.guest")}</th>
                <th className="px-4 py-2">{t("page.list.columns.company")}</th>
                <th className="px-4 py-2">{t("page.list.columns.roomCat")}</th>
                <th className="px-4 py-2">{t("page.list.columns.checkIn")}</th>
                <th className="px-4 py-2">{t("page.list.columns.arrivalTime")}</th>
                <th className="px-4 py-2">{t("page.list.columns.checkOut")}</th>
                <th className="px-4 py-2">{t("page.list.columns.status")}</th>
                <th className="px-4 py-2 text-right">{t("page.list.columns.amount")}</th>
                <th className="px-4 py-2 text-right">{t("page.list.columns.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {!isLoading && reservations.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-sm text-slate-500" colSpan={10}>
                    {t("page.list.noResults")}
                  </td>
                </tr>
              )}
              {reservations.map((reservation) => {
                const cfg = statusConfig[reservation.status];
                return (
                  <tr key={reservation.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2 font-semibold text-slate-900">{reservation.confirmation_code}</td>
                    <td className="px-4 py-2 text-slate-700">
                      <button className="text-left font-semibold text-brand-700 hover:underline" onClick={() => openGuest(reservation.guest_id)} type="button">
                        {reservationGuestLabel(t, reservation)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.company_id ? companyNameById.get(reservation.company_id) ?? t("page.list.companyLinked") : "—"}
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {t("page.list.roomCat", {
                        room: reservation.room_number ? t("page.common.room", { number: reservation.room_number }) : t("page.common.unassigned"),
                        category: reservation.category_name ?? categoryNameById.get(reservation.category_id) ?? t("page.common.informationUnavailable")
                      })}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_in_date}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.arrival_time_hint || <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_out_date}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${cfg?.className ?? "bg-slate-100 text-slate-800"}`}>
                        {cfg?.label ?? reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">
                      {isDeferredCompanyReservation(reservation)
                        ? t("page.list.deferredCompanyBilling")
                        : formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-700">
                      <div className="flex flex-wrap justify-end gap-1">
                        {canManageCompanyReservation(reservation) ? (
                          <button
                            type="button"
                            onClick={() => openEdit(reservation)}
                            className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300 disabled:opacity-50"
                            disabled={subscriptionBlocked}
                          >
                            {t("page.list.edit")}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => openDetails(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300"
                        >
                          {t("page.list.file")}
                        </button>
                        {canManageCompanyReservation(reservation) ? (
                          <button
                            type="button"
                            disabled={!canCancel(reservation.status) || cancelMutation.isPending || subscriptionBlocked}
                            onClick={() => handleCancel(reservation)}
                            className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {t("page.list.cancel")}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isPending || subscriptionBlocked}
                          onClick={() => openReservation(reservation.id)}
                          title={t("page.list.checkInTooltipOpen")}
                          className="rounded-lg border border-emerald-200 px-2 py-1 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {t("page.list.checkIn")}
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckOut(reservation.status) || checkOutMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCheckOut(reservation)}
                          className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {t("page.list.checkOut")}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Mobile alternative to the table above: one card per reservation
            with the same data/actions, stacked instead of columned. */}
        <div className="divide-y divide-slate-200 md:hidden">
          {!isLoading && reservations.length === 0 && (
            <p className="px-4 py-4 text-sm text-slate-500">{t("page.list.noResults")}</p>
          )}
          {reservations.map((reservation) => {
            const cfg = statusConfig[reservation.status];
            return (
              <div key={reservation.id} className="flex flex-col gap-2 px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900">{reservation.confirmation_code}</p>
                    <button
                      type="button"
                      className="truncate text-left text-sm font-semibold text-brand-700 hover:underline"
                      onClick={() => openGuest(reservation.guest_id)}
                    >
                      {reservationGuestLabel(t, reservation)}
                    </button>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${cfg?.className ?? "bg-slate-100 text-slate-800"}`}>
                    {cfg?.label ?? reservation.status}
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  {t("page.list.roomCat", {
                    room: reservation.room_number ? t("page.common.room", { number: reservation.room_number }) : t("page.common.unassigned"),
                    category: reservation.category_name ?? categoryNameById.get(reservation.category_id) ?? t("page.common.informationUnavailable")
                  })}
                </p>
                {reservation.company_id ? (
                  <p className="text-xs text-slate-600">{t("page.list.columns.company")}: {companyNameById.get(reservation.company_id) ?? t("page.list.companyLinked")}</p>
                ) : null}
                <p className="text-xs text-slate-600">
                  {reservation.check_in_date} → {reservation.check_out_date}
                </p>
                {reservation.arrival_time_hint ? (
                  <p className="text-xs font-semibold text-slate-700">{t("page.list.columns.arrivalTime")}: {reservation.arrival_time_hint}</p>
                ) : null}
                {reservation.reservation_comment ? (
                  <p className="truncate text-xs text-amber-700" title={reservation.reservation_comment}>📝 {reservation.reservation_comment}</p>
                ) : null}
                <p className="text-sm font-semibold text-slate-900">
                  {isDeferredCompanyReservation(reservation)
                    ? t("page.list.deferredCompanyBilling")
                    : formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                </p>
                <div className="flex flex-wrap gap-2 pt-1 text-xs text-slate-700">
                  {canManageCompanyReservation(reservation) ? (
                    <button
                      type="button"
                      onClick={() => openEdit(reservation)}
                      className="min-h-11 rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300 disabled:opacity-50"
                      disabled={subscriptionBlocked}
                    >
                      {t("page.list.edit")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => openDetails(reservation)}
                    className="min-h-11 rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300"
                  >
                    {t("page.list.file")}
                  </button>
                  {canManageCompanyReservation(reservation) ? (
                    <button
                      type="button"
                      disabled={!canCancel(reservation.status) || cancelMutation.isPending || subscriptionBlocked}
                      onClick={() => handleCancel(reservation)}
                      className="min-h-11 rounded-lg border border-rose-200 px-3 py-2 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t("page.list.cancel")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    disabled={!canCheckIn(reservation.status) || checkInMutation.isPending || subscriptionBlocked}
                    onClick={() => openReservation(reservation.id)}
                    title={t("page.list.checkInTooltipOpen")}
                    className="min-h-11 rounded-lg border border-emerald-200 px-3 py-2 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("page.list.checkIn")}
                  </button>
                  <button
                    type="button"
                    disabled={!canCheckOut(reservation.status) || checkOutMutation.isPending || subscriptionBlocked}
                    onClick={() => handleCheckOut(reservation)}
                    className="min-h-11 rounded-lg border border-sky-200 px-3 py-2 text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("page.list.checkOut")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {formOpen && (
        <div className="fixed inset-0 z-30 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6">
          <div className="w-full max-w-2xl max-h-[90vh] animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{editing ? t("page.form.editEyebrow") : t("page.form.createEyebrow")}</p>
                <h3 className="text-lg font-semibold text-slate-900">{t("page.form.title")}</h3>
                <p className="text-xs text-slate-500">{t("page.form.subtitle")}</p>
              </div>
              <button
                onClick={closeForm}
                type="button"
                disabled={formBusy}
                className="text-sm text-slate-500 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("page.common.close")}
              </button>
            </div>

            {subscriptionBlocked && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {subscriptionBlockReason} {t("page.form.subscriptionBlockedHint")}{" "}
                <Link to="/settings/subscription" className="font-semibold underline">
                  {t("page.form.subscriptionLink")}
                </Link>
                .
              </div>
            )}
            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <fieldset
                disabled={isReservationQuoteUpdating}
                aria-busy={isReservationQuoteUpdating}
                className={`min-w-0 space-y-4 ${isReservationQuoteUpdating ? "opacity-60" : ""}`}
              >
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                {t("page.form.sectionData")}
              </div>
              {editing && collaborativeReservation.status !== "idle" && (
                <div
                  className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900"
                  data-testid="reservation-collaboration"
                  role="status"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">
                      {collaborativeReservation.status === "connected"
                        ? t("page.form.collab.connected")
                        : collaborativeReservation.status === "connecting"
                          ? t("page.form.collab.connecting")
                          : collaborativeReservation.status === "reconnecting"
                            ? t("page.form.collab.reconnecting")
                            : collaborativeReservation.status === "saving"
                              ? t("page.form.collab.saving")
                              : collaborativeReservation.status === "conflict"
                                ? t("page.form.collab.conflict")
                                : t("page.form.collab.degraded")}
                    </span>
                    {collaborativeReservation.peers.length > 0 && (
                      <span className="text-xs">
                        {t("page.form.collab.otherPeople", { count: collaborativeReservation.peers.length })}
                      </span>
                    )}
                  </div>
                  {collaborativeReservation.peers.some((peer) => peer.fields.length > 0) && (
                    <p className="text-xs text-sky-800">
                      {t("page.form.collab.remoteFields", {
                        fields: Array.from(new Set(collaborativeReservation.peers.flatMap((peer) => peer.fields))).join(", ")
                      })}
                    </p>
                  )}
                  {Object.values(collaborativeReservation.conflicts).map((conflict) => (
                    <div
                      key={conflict.field}
                      className="flex flex-wrap items-center justify-between gap-2 rounded border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-950"
                      data-testid={`reservation-conflict-${conflict.field}`}
                    >
                      <span>
                        <strong>{conflict.field}</strong>: {t("page.form.collab.yourValue")} “{String(conflict.localValue ?? t("page.form.collab.emptyValue"))}” · {t("page.form.collab.remoteValue")} “
                        {String(conflict.remoteValue ?? t("page.form.collab.emptyValue"))}”
                      </span>
                      <span className="flex gap-2">
                        <button
                          type="button"
                          className="font-semibold underline"
                          onClick={() => collaborativeReservation.keepMine(conflict.field)}
                        >
                          {t("page.form.collab.keepMine")}
                        </button>
                        <button
                          type="button"
                          className="font-semibold underline"
                          onClick={() => collaborativeReservation.useRemote(conflict.field)}
                        >
                          {t("page.form.collab.useRemote")}
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                <GuestQuickCreatePanel
                  guestId={formValues.guest_id}
                  onGuestIdChange={(value) => setFormValues((prev) => ({ ...prev, guest_id: value }))}
                  guestIdDisabled={Boolean(editing)}
                  form={guestForm}
                  onFormChange={setGuestForm}
                  onGuestCreated={() => showToast("success", t("page.form.guestCreatedMessage"))}
                />
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.category")}
                  <select
                    value={formValues.category_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, category_id: e.target.value, room_id: "" }))}
                    disabled={Boolean(editing)}
                    title={editing ? t("page.form.categoryDisabledTitle") : undefined}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="">{t("page.form.categoryPlaceholder")}</option>
                    {categoryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {hasPermission("company:manage") && <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.company")}
                  <select
                    data-testid="reservation-company-select"
                    value={formValues.company_id}
                    onChange={(event) => {
                      const companyId = Number(event.target.value);
                      const selectedCompany = companyOptions.find((company) => company.id === companyId);
                      setFormValues((previous) => ({ ...previous, company_id: event.target.value }));
                      if (selectedCompany?.payment_deferred) {
                        setManualTotalAmountInput("");
                        setDepositAmountInput("");
                        setManualRateReasonInput("");
                      }
                    }}
                    disabled={Boolean(editing) || companyOptionsQuery.isLoading}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="">{t("page.form.individualReservation")}</option>
                    {companyOptions.map((company) => (
                      <option key={company.id} value={company.id} disabled={!company.is_active}>
                        {company.display_name || company.legal_name}{company.is_active ? "" : ` · ${t("page.form.companyInactive")}`}
                      </option>
                    ))}
                  </select>
                  {editing && formValues.company_id && (
                    <span className="mt-1 block font-normal text-slate-500">{t("page.form.companyEditHint")}</span>
                  )}
                </label>}
                {!editing && formValues.source === "direct" && (
                  <label className="text-xs font-semibold text-slate-600">
                    {t("page.form.groupSize")}
                    <select
                      data-testid="reservation-group-size"
                      value={formValues.group_size}
                      onChange={(event) => {
                        const groupSize = event.target.value;
                        setFormValues((previous) => ({
                          ...previous,
                          group_size: groupSize,
                          room_id: Number(groupSize) > 1 ? "" : previous.room_id
                        }));
                        if (Number(groupSize) > 1) setManualTotalAmountInput("");
                      }}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                    >
                      {Array.from({ length: 10 }, (_, index) => index + 1).map((count) => (
                        <option key={count} value={count}>{count}</option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {!editing && Number(formValues.group_size) > 1 ? (
                  <div className="rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-brand-800" data-testid="reservation-group-auto-assignment">
                    {t("page.form.groupAutoAssign", { count: Number(formValues.group_size) })}
                  </div>
                ) : (
                  <label className="text-xs font-semibold text-slate-600">
                    {t("page.form.room")}
                    <select
                      value={collaborativeFormValues.room_id}
                      onChange={(e) => setReservationField("room_id", e.target.value)}
                      onFocus={() => editing && collaborativeReservation.focusField("room_id")}
                      onBlur={() => editing && collaborativeReservation.blurField("room_id")}
                      disabled={metadataOnlyEdit}
                      title={metadataOnlyEdit ? t("page.form.metadataOnlyEditTitle") : undefined}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                    >
                      <option value="">
                        {!editing && formValues.category_id && quoteNights > 0 && formAvailabilityQuery.isFetching
                          ? t("page.form.roomAvailability.loading")
                          : availableRooms.length > 0 || editing
                            ? t("page.common.unassigned")
                            : t("page.form.roomAvailability.noRooms")}
                      </option>
                      {availableRooms.map((room) => (
                        <option key={room.id} value={room.id}>
                          {t("page.form.roomOption", { number: room.room_number || t("page.common.informationUnavailable"), category: categoryNameById.get(room.category_id) ?? t("page.common.informationUnavailable") })}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.source")}
                  <select
                    value={formValues.source}
                    onChange={(e) => {
                      const source = e.target.value as ReservationSource;
                      setFormValues((prev) => ({
                        ...prev,
                        source,
                        group_size: "1",
                        company_id: source === "direct" ? prev.company_id : ""
                      }));
                    }}
                    disabled={Boolean(editing)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="direct">{t("page.form.sourceOptions.direct")}</option>
                    <option value="booking">{t("page.form.sourceOptions.booking")}</option>
                    <option value="expedia">{t("page.form.sourceOptions.expedia")}</option>
                    <option value="other_ota">{t("page.form.sourceOptions.other_ota")}</option>
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <LocalizedDateField
                  id="reservation-form-check-in"
                  label={t("page.form.checkIn")}
                  value={collaborativeFormValues.check_in_date}
                  onChange={(value) => setReservationField("check_in_date", value)}
                  onFocus={() => editing && collaborativeReservation.focusField("check_in_date")}
                  onBlur={() => editing && collaborativeReservation.blurField("check_in_date")}
                  disabled={metadataOnlyEdit}
                  title={metadataOnlyEdit ? t("page.form.metadataOnlyEditTitle") : undefined}
                  className="w-full"
                  labelClassName="text-xs font-semibold text-slate-600"
                  inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  placeholder={t("page.dateInput.datePlaceholder")}
                  chooseDateLabel={t("page.dateInput.chooseDate")}
                  invalidMessage={t("page.dateInput.invalidDate")}
                />
                <LocalizedDateField
                  id="reservation-form-check-out"
                  label={t("page.form.checkOut")}
                  value={collaborativeFormValues.check_out_date}
                  onChange={(value) => setReservationField("check_out_date", value)}
                  onFocus={() => editing && collaborativeReservation.focusField("check_out_date")}
                  onBlur={() => editing && collaborativeReservation.blurField("check_out_date")}
                  disabled={metadataOnlyEdit}
                  title={metadataOnlyEdit ? t("page.form.metadataOnlyEditTitle") : undefined}
                  className="w-full"
                  labelClassName="text-xs font-semibold text-slate-600"
                  inputClassName="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  placeholder={t("page.dateInput.datePlaceholder")}
                  chooseDateLabel={t("page.dateInput.chooseDate")}
                  invalidMessage={t("page.dateInput.invalidDate")}
                />
              </div>

              {!editing && formValues.category_id && quoteNights > 0 ? (
                <div
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
                  data-testid="reservation-form-availability"
                >
                  {formAvailabilityQuery.isFetching ? (
                    <p role="status" aria-live="polite" className="text-slate-600">
                      {t("page.form.roomAvailability.loading")}
                    </p>
                  ) : formAvailabilityQuery.isError ? (
                    <div className="flex flex-wrap items-center justify-between gap-2" role="alert">
                      <p className="text-rose-800">
                        {t("page.form.roomAvailability.error", {
                          message: formAvailabilityQuery.error instanceof Error
                            ? formAvailabilityQuery.error.message
                            : t("page.common.informationUnavailable")
                        })}
                      </p>
                      <button
                        type="button"
                        onClick={() => void formAvailabilityQuery.refetch()}
                        className="font-semibold text-brand-700 underline"
                      >
                        {t("page.form.roomAvailability.retry")}
                      </button>
                    </div>
                  ) : formAvailabilityQuery.data?.status === "placeholder" ? (
                    <p role="alert" className="text-amber-900">{t("page.form.roomAvailability.unavailable")}</p>
                  ) : formAvailabilityQuery.data?.status === "ok" ? (
                    <p className={hasEnoughGroupRooms || requestedGroupRoomCount === 1 ? "text-emerald-800" : "text-rose-800"}>
                      {requestedGroupRoomCount > 1
                        ? t("page.form.roomAvailability.groupCount", {
                            available: formAvailabilityQuery.data.count,
                            requested: requestedGroupRoomCount
                          })
                        : t("page.form.roomAvailability.count", { count: formAvailabilityQuery.data.count })}
                    </p>
                  ) : null}
                </div>
              ) : null}

              {!editing && !deferredCompanyBooking && (
                <div className="rounded-lg border border-brand-100 bg-brand-50 p-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-xs font-semibold text-slate-600">
                      {t("page.form.pricingMethod")}
                      <select
                        value={pricingPaymentMethod}
                        onChange={(e) => setPricingPaymentMethod(e.target.value as PricingPaymentMethod)}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      >
                        {pricingPaymentMethodValues.map((value) => (
                          <option key={value} value={value}>
                            {t(`page.pricingMethods.${value}`)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      {t("page.form.manualDeposit")}
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={depositAmountInput}
                        onChange={(e) => setDepositAmountInput(e.target.value)}
                        placeholder={t("page.form.depositPlaceholder")}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      />
                    </label>
                  </div>

                  {canSetManualRate && Number(formValues.group_size) > 1 && (
                    <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                      {t("page.errors.groupManualRateUnsupported")}
                    </p>
                  )}

                  {canSetManualRate && Number(formValues.group_size) === 1 && (
                    <div className="mt-3 rounded-lg border border-brand-200 bg-brand-50/60 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">{t("page.form.manualRateTitle")}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("page.form.manualRateHint")}
                      </p>
                      {isBoundedManualRate && !boundedManualRateContextAllowed ? (
                        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                          {t("page.form.boundedManualRateDirectOnly")}
                        </p>
                      ) : null}
                      {isBoundedManualRate && boundedManualRateContextAllowed && quoteQuery.isFetching ? (
                        <p className="mt-2 text-xs text-slate-600">{t("page.form.boundedManualRateCalculating")}</p>
                      ) : null}
                      {isBoundedManualRate && boundedManualRateContextAllowed && quoteQuery.isError ? (
                        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                          {t("page.form.boundedManualRateQuoteUnavailable")}
                        </p>
                      ) : null}
                      {isBoundedManualRate && boundedManualRateContextAllowed && !quoteQuery.isFetching && !quoteQuery.isError && quoteQuery.data && !boundedManualRateRange ? (
                        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                          {t("page.form.boundedManualRatePolicyUnconfigured")}
                        </p>
                      ) : null}
                      {isBoundedManualRate && boundedManualRateRange ? (
                        <p className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-900">
                          {t("page.form.boundedManualRateAllowedRange", {
                            minimum: formatMoney(boundedManualRateRange.minimum, manualRateCurrencyCode),
                            maximum: formatMoney(boundedManualRateRange.maximum, manualRateCurrencyCode)
                          })}
                        </p>
                      ) : null}
                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <label className="text-xs font-semibold text-slate-600">
                          {t("page.form.manualAmount")}
                          <input
                            type="number"
                            min={0}
                            max={isBoundedManualRate ? boundedManualRateRange?.maximum : undefined}
                            step="0.01"
                            value={manualTotalAmountInput}
                            onChange={(e) => {
                              setManualTotalAmountInput(e.target.value);
                              setConfirmLargeTotalAdjustment(false);
                            }}
                            placeholder={t("page.form.manualAmountPlaceholder")}
                            disabled={isBoundedManualRate && !boundedManualRateReady}
                            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                          />
                        </label>
                        {isBoundedManualRate ? (
                          <label className="text-xs font-semibold text-slate-600">
                            {t("page.form.currency")}
                            <input
                              value={quoteQuery.data?.currency_code ?? ""}
                              readOnly
                              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800"
                            />
                          </label>
                        ) : (
                          <label className="text-xs font-semibold text-slate-600">
                            {t("page.form.currency")}
                            <select
                              value={manualTargetCurrency}
                              onChange={(e) => {
                                setManualTargetCurrency(e.target.value as "ARS" | "USD");
                                setConfirmLargeTotalAdjustment(false);
                              }}
                              disabled={manualTotalAmountInput.trim() === ""}
                              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                            >
                              <option value="ARS">ARS</option>
                              <option value="USD">USD</option>
                            </select>
                          </label>
                        )}
                      </div>
                      <label className="mt-3 block text-xs font-semibold text-slate-600">
                        {t("page.form.manualRateReason")}
                        <textarea
                          rows={2}
                          maxLength={500}
                          value={manualRateReasonInput}
                          onChange={(event) => setManualRateReasonInput(event.target.value)}
                          placeholder={t("page.form.manualRateReasonPlaceholder")}
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                        />
                        <span className="mt-1 block text-xs font-normal text-slate-500">{t("page.form.manualRateReasonHint")}</span>
                      </label>
                    </div>
                  )}

                  {manualTotalAmountInput.trim() !== "" ? (
                    <div className="mt-3 rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      {t("page.form.manualTotalPreview", { amount: formatMoney(Number(manualTotalAmountInput) || 0, manualRateCurrencyCode) })}
                    </div>
                  ) : (
                    <>
                      <div className="mt-3 grid gap-2 sm:grid-cols-4">
                        <div className="rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteNights")}</p>
                          <p className="font-semibold">{reservationQuote?.nights ?? quoteNights}</p>
                        </div>
                        <div className="rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteTotalFinal")}</p>
                          <p className="font-semibold">
                            {quoteQuery.isFetching
                              ? t("page.form.quoteUpdating")
                              : quoteQuery.isError
                                ? t("page.form.quoteUnavailable")
                              : formatMoney(reservationQuote?.total ?? 0, reservationQuote?.currencyCode ?? "ARS")}
                          </p>
                        </div>
                        <div className="rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteDeposit")}</p>
                          <p className="font-semibold">
                            {quoteQuery.isError
                              ? t("page.form.quoteDepositUnavailable")
                              : depositPreview !== null
                              ? formatMoney(depositPreview, reservationQuote?.currencyCode ?? "ARS")
                              : t("page.form.quoteDepositPending")}
                          </p>
                        </div>
                        <div className="rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteBalance")}</p>
                          <p className="font-semibold">
                            {quoteBalancePreview !== null
                              ? formatMoney(quoteBalancePreview, reservationQuote?.currencyCode ?? "ARS")
                              : "-"}
                          </p>
                        </div>
                      </div>

                      {!quoteQuery.isError && reservationQuote && (reservationQuote.subtotal !== reservationQuote.total || reservationQuote.taxAmount > 0 || reservationQuote.feeAmount > 0) ? (
                        <p className="mt-2 text-xs text-slate-600">
                          {t("page.form.quoteSubtotalLine", {
                            subtotal: formatMoney(reservationQuote.subtotal, reservationQuote.currencyCode),
                            tax: reservationQuote.taxAmount > 0 ? t("page.form.quoteTaxSuffix", { amount: formatMoney(reservationQuote.taxAmount, reservationQuote.currencyCode) }) : "",
                            fee: reservationQuote.feeAmount > 0 ? t("page.form.quoteFeeSuffix", { amount: formatMoney(reservationQuote.feeAmount, reservationQuote.currencyCode) }) : "",
                            method: reservationQuote.paymentMethod ? t("page.form.quoteMethodSuffix", { method: reservationQuote.paymentMethod }) : ""
                          })}
                        </p>
                      ) : null}

                      {!quoteQuery.isError && reservationQuote && reservationQuote.promotionsApplied.length > 0 ? (
                        <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 p-2">
                          <p className="text-xs font-semibold text-emerald-800">{t("page.form.promotionsApplied")}</p>
                          <ul className="mt-1 flex flex-wrap gap-1.5">
                            {Object.values(
                              reservationQuote.promotionsApplied.reduce<Record<string, { code: string; total: number }>>((acc, promo) => {
                                const key = promo.code;
                                const entry = acc[key] ?? { code: promo.code, total: 0 };
                                entry.total += Number(promo.amount_deducted) || 0;
                                acc[key] = entry;
                                return acc;
                              }, {})
                            ).map((entry) => (
                              <li key={entry.code} className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-emerald-800 shadow-sm">
                                {entry.code}: -{formatMoney(entry.total, reservationQuote.currencyCode)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      {quoteQuery.isError ? (
                        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
                          <p>
                            {/* The backend always answers price-quote failures with 400 (never
                                404), so the missing-rate case can't be told apart by status code.
                                Detect it from the backend's own message instead (pricing_policy_service
                                raises "No active/matching price..." / "Rate plan not found..." for
                                every "nothing configured" scenario). */}
                            {getGuestProhibitedDetail(quoteQuery.error)
                              ? // The quote endpoint never accepts an override (it's a preview, not
                                // the actual booking) -- the auto-priced path is blocked without a
                                // quote_token, so the only way through is a manual total, which
                                // skips the quote_token requirement and lets the create button surface
                                // its own override prompt.
                                t("page.form.quoteErrorRestricted")
                              : quoteQuery.error instanceof ApiError && /price|rate plan/i.test(quoteQuery.error.message)
                              ? t("page.form.quoteErrorNoRate")
                              : t("page.form.quoteErrorGeneric")}
                          </p>
                          <button
                            type="button"
                            onClick={() => void quoteQuery.refetch()}
                            disabled={quoteQuery.isFetching}
                            className="mt-2 rounded-lg border border-rose-300 bg-white px-3 py-2 font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                          >
                            {t("page.form.quoteRetry")}
                          </button>
                        </div>
                      ) : reservationQuote?.rows.length ? (
                        <div className="mt-3 overflow-x-auto rounded-lg border border-brand-100 bg-white/70">
                          <table className="min-w-full text-left text-xs">
                            <thead className="bg-white text-slate-500">
                              <tr>
                                <th className="px-3 py-2 font-semibold">{t("page.form.quoteRowNight")}</th>
                                <th className="px-3 py-2 font-semibold">{t("page.form.quoteRowSource")}</th>
                                {reservationQuote.promotionsApplied.length > 0 ? (
                                  <>
                                    <th className="px-3 py-2 text-right font-semibold">{t("page.form.quoteRowBase")}</th>
                                    <th className="px-3 py-2 font-semibold">{t("page.form.quoteRowPromo")}</th>
                                  </>
                                ) : null}
                                <th className="px-3 py-2 text-right font-semibold">{t("page.form.quoteRowAmount")}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {reservationQuote.rows.slice(0, 6).map((row) => (
                                <tr key={row.date} className="border-t border-brand-100">
                                  <td className="px-3 py-2 text-slate-700">{row.date}</td>
                                  <td className="px-3 py-2 text-slate-500">{translatedEnum("rateSource", row.source)}</td>
                                  {reservationQuote.promotionsApplied.length > 0 ? (
                                    <>
                                      <td className="px-3 py-2 text-right text-slate-500">
                                        {formatMoney(row.basePrice, reservationQuote.currencyCode)}
                                      </td>
                                      <td className="px-3 py-2 text-slate-500">
                                        {row.promotionsApplied.length
                                          ? row.promotionsApplied.map((p) => p.code).join(", ")
                                          : "—"}
                                      </td>
                                    </>
                                  ) : null}
                                  <td className="px-3 py-2 text-right font-semibold text-slate-800">
                                    {formatMoney(row.amount, reservationQuote.currencyCode)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {reservationQuote.rows.length > 6 ? (
                            <p className="border-t border-brand-100 px-3 py-2 text-xs text-slate-500">
                              {t("page.form.quoteMoreRows", { count: reservationQuote.rows.length - 6 })}
                            </p>
                          ) : null}
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-slate-600">
                          {quoteNights > 0
                            ? t("page.form.quoteCalculating")
                            : t("page.form.quotePickDates")}
                        </p>
                      )}
                    </>
                  )}
                  {largeManualRateAdjustmentDraft ? (
                    <div className="mt-3 rounded-lg border border-amber-300 bg-white p-3" role="alert" data-testid="manual-rate-adjustment-warning">
                      <p className="text-sm text-amber-950">
                        {t("page.form.largeManualRateAdjustmentWarning", {
                          current: formatMoney(reservationQuote?.total ?? 0, manualRateCurrencyCode),
                          proposed: formatMoney(proposedManualRateTotalDraft ?? 0, manualRateCurrencyCode)
                        })}
                      </p>
                      <label className="mt-2 flex items-start gap-2 text-sm text-slate-800">
                        <input
                          type="checkbox"
                          data-testid="manual-rate-adjustment-confirm"
                          checked={confirmLargeTotalAdjustment}
                          onChange={(event) => setConfirmLargeTotalAdjustment(event.target.checked)}
                          className="mt-0.5"
                        />
                        <span>{t("page.form.largeTotalAdjustmentConfirm")}</span>
                      </label>
                    </div>
                  ) : null}
                </div>
              )}

              {!editing && deferredCompanyBooking ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950" data-testid="deferred-company-booking-note">
                  {t("page.form.deferredCompanyBilling")}
                </p>
              ) : null}

              {lastCreatedReservation ? (
                <div
                  className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"
                  role="status"
                >
                  <p className="font-semibold">
                    {t("page.form.lastCreated", {
                      code: lastCreatedReservation.confirmation_code,
                      currency: normalizeCurrencyCode(lastCreatedReservation.currency_code)
                    })}
                  </p>
                  {lastCreatedReservation.fx_rate_snapshot ? (
                    <p className="mt-1">
                      {t("page.form.lastCreatedRate", {
                        currency: manualTargetCurrency,
                        rate: lastCreatedReservation.fx_rate_snapshot.toLocaleString("es-AR")
                      })}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-emerald-800">
                      {t("page.form.lastCreatedNoRate", { currency: normalizeCurrencyCode(lastCreatedReservation.currency_code) })}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={closeForm}
                    disabled={formBusy}
                    className="mt-2 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {t("page.common.close")}
                  </button>
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.adults")}
                  <input
                    type="number"
                    min={1}
                    value={collaborativeFormValues.num_adults}
                    onChange={(e) => setReservationField("num_adults", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("num_adults")}
                    onBlur={() => editing && collaborativeReservation.blurField("num_adults")}
                    disabled={metadataOnlyEdit}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.children")}
                  <input
                    type="number"
                    min={0}
                    value={collaborativeFormValues.num_children}
                    onChange={(e) => setReservationField("num_children", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("num_children")}
                    onBlur={() => editing && collaborativeReservation.blurField("num_children")}
                    disabled={metadataOnlyEdit}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.status")}
                  <select
                    value={formValues.status}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, status: e.target.value as ReservationStatus }))}
                    disabled={Boolean(editing)}
                    title={editing ? t("page.form.statusDisabledTitle") : undefined}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="pending">{t("page.statusOptions.pending")}</option>
                    <option value="deposit_paid">{t("page.statusOptions.depositPaid")}</option>
                    <option value="fully_paid">{t("page.statusOptions.fullyPaid")}</option>
                    <option value="pre_check_in">{t("page.statusOptions.preCheckIn")}</option>
                    <option value="checked_in">{t("page.statusOptions.checkedIn")}</option>
                    <option value="checked_out">{t("page.statusOptions.checkedOut")}</option>
                    <option value="cancelled">{t("page.statusOptions.cancelled")}</option>
                  </select>
                </label>
              </div>

              <label className="text-xs font-semibold text-slate-600">
                {t("page.form.notes")}
                <textarea
                  value={collaborativeFormValues.notes}
                  placeholder={t("page.form.notesPlaceholder")}
                  onChange={(e) => setReservationField("notes", e.target.value)}
                  onFocus={() => editing && collaborativeReservation.focusField("notes")}
                  onBlur={() => editing && collaborativeReservation.blurField("notes")}
                  disabled={metadataOnlyEdit}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  rows={3}
                />
              </label>

              {metadataOnlyEdit ? (
                <p className="text-xs text-slate-500">{t("page.form.metadataOnlyEditHint")}</p>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.arrivalTimeHint")}
                  <input
                    type="time"
                    value={collaborativeFormValues.arrival_time_hint}
                    onChange={(e) => setReservationField("arrival_time_hint", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("arrival_time_hint")}
                    onBlur={() => editing && collaborativeReservation.blurField("arrival_time_hint")}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.reservationComment")}
                  <textarea
                    value={collaborativeFormValues.reservation_comment}
                    maxLength={1000}
                    onChange={(e) => setReservationField("reservation_comment", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("reservation_comment")}
                    onBlur={() => editing && collaborativeReservation.blurField("reservation_comment")}
                    placeholder={t("page.form.reservationCommentPlaceholder")}
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <span className="mt-1 block text-xs font-normal text-slate-500">{t("page.form.reservationCommentHint")}</span>
                </label>
              </div>

              {editing && !isDeferredCompanyReservation(editing) && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-emerald-700">{t("page.form.paymentsTitle")}</p>
                      <p className="text-xs text-emerald-800">{t("page.form.paymentsSubtitle")}</p>
                    </div>
                    {paymentSummaryQuery.isFetching && <span className="text-xs text-emerald-700">{t("page.form.updating")}</span>}
                  </div>
                  {paymentSummary ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-4">
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">{t("page.form.summaryTotal")}</p>
                        <p className="font-semibold">
                          {formatMoney(paymentSummary.operational_total_amount ?? paymentSummary.total_amount ?? 0, editingCurrencyCode)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">{t("page.form.summaryPaid")}</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.amount_paid ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">{t("page.form.summaryDepositRequired")}</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.deposit_required ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">{t("page.form.summaryBalance")}</p>
                        <p className="font-semibold">
                          {formatMoney(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0, editingCurrencyCode)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-600">{t("page.form.loadingSummary")}</p>
                  )}

                  {canAdjustReservationTotal ? (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="reservation-total-adjustment">
                      <p className="text-sm font-semibold text-amber-950">{t("page.form.paidTotalAdjustmentTitle")}</p>
                      <p className="mt-1 text-xs text-amber-900">
                        {hasAnyPaymentEvidence
                          ? t("page.form.paidTotalAdjustmentHint")
                          : canSetBoundedReservationRate && !canSetUnboundedReservationRate
                            ? t("page.form.boundedUnpaidTotalAdjustmentHint")
                            : t("page.form.unpaidTotalAdjustmentHint")}
                      </p>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        <label className="text-xs font-semibold text-slate-700">
                          {t("page.form.paidTotalAdjustmentAmount")}
                          <input
                            data-testid="reservation-total-adjustment-amount"
                            type="number"
                            min="0"
                            step="0.01"
                            value={paidTotalAmountInput}
                            onChange={(event) => {
                              setPaidTotalAmountInput(event.target.value);
                              setConfirmLargeTotalAdjustment(false);
                            }}
                            className="mt-1 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-slate-800"
                          />
                        </label>
                        <label className="text-xs font-semibold text-slate-700">
                          {t("page.form.paidTotalAdjustmentReason")}
                          <textarea
                            data-testid="reservation-total-adjustment-reason"
                            maxLength={500}
                            value={paidTotalChangeReasonInput}
                            onChange={(event) => setPaidTotalChangeReasonInput(event.target.value)}
                            placeholder={t("page.form.paidTotalAdjustmentReasonPlaceholder")}
                            rows={2}
                            className="mt-1 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-slate-800"
                          />
                        </label>
                      </div>
                      {largeTotalAdjustmentDraft ? (
                        <div className="mt-3 rounded-lg border border-amber-300 bg-white p-3" role="alert" data-testid="reservation-total-adjustment-warning">
                          <p className="text-sm text-amber-950">
                            {t("page.form.largeTotalAdjustmentWarning", {
                              current: formatMoney(Number(editing.total_amount || 0), editingCurrencyCode),
                              proposed: formatMoney(proposedTotalDraft ?? 0, editingCurrencyCode)
                            })}
                          </p>
                          <label className="mt-2 flex items-start gap-2 text-sm text-slate-800">
                            <input
                              type="checkbox"
                              data-testid="reservation-total-adjustment-confirm"
                              checked={confirmLargeTotalAdjustment}
                              onChange={(event) => setConfirmLargeTotalAdjustment(event.target.checked)}
                              className="mt-0.5"
                            />
                            <span>{t("page.form.largeTotalAdjustmentConfirm")}</span>
                          </label>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="mt-3 grid gap-2 sm:grid-cols-6 sm:items-end">
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                      {t("page.form.paymentMethod")}
                      <select
                        value={paymentMethod}
                        onChange={(e) => {
                          setPaymentMethod(e.target.value as PaymentMethod);
                          setPaymentReferenceInput("");
                          if (e.target.value !== "cash") {
                            setCollectedBefore(false);
                            setCollectedOn("");
                            setPriorReceiptNote("");
                          }
                        }}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      >
                        {availablePaymentMethods.map((value) => (
                          <option key={value} value={value}>
                            {t(`page.paymentMethods.${value}`)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Moneda recibida
                      <select
                        value={paymentTenderCurrency}
                        onChange={(event) => setPaymentTenderCurrencyInput(event.target.value)}
                        disabled={collectedBefore}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm disabled:bg-slate-100"
                        data-testid="payment-tender-currency"
                      >
                        {PAYMENT_CURRENCIES.map((currencyCode) => (
                          <option key={currencyCode} value={currencyCode}>{currencyCode}</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                      {isCompanyNightRefund
                        ? t("page.form.companyNightRefundCashAmount", { currency: selectedRefundTarget?.currency ?? paymentTenderCurrency })
                        : paymentMethod === "cash" && canRefundPayment
                          ? t("page.form.cashMovementAmount")
                          : t("page.form.amountToCharge")}
                      {isCompanyNightRefund ? (
                        <input
                          aria-label={t("page.form.companyNightRefundCashAmount", { currency: selectedRefundTarget?.currency ?? paymentTenderCurrency })}
                          type="text"
                          readOnly
                          aria-readonly="true"
                          value={companyNightRefundTenderAmount !== null && companyNightRefundBaseAmount > 0
                            ? formatMoney(companyNightRefundTenderAmount, selectedRefundTarget?.currency ?? paymentTenderCurrency)
                            : "—"}
                          aria-describedby="company-night-refund-cash-hint"
                          className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                          data-testid="company-night-refund-tender-amount"
                        />
                      ) : (
                        <input
                          aria-label={paymentMethod === "cash" && canRefundPayment
                            ? t("page.form.cashMovementAmount")
                            : t("page.form.amountToChargeAria")}
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={paymentAmountInput}
                          onChange={(event) => setPaymentAmountInput(event.target.value)}
                          aria-describedby="payment-fx-conversion-help"
                          placeholder={paymentMethod === "cash" && canRefundPayment
                            ? t("page.form.cashMovementAmountPlaceholder")
                            : t("page.form.amountToChargePlaceholder")}
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                        />
                      )}
                    </label>
                    <div className="sm:col-span-6" id="payment-fx-conversion-help" aria-live="polite">
                      {isCompanyNightRefund ? (
                        <div className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950" id="company-night-refund-cash-hint" data-testid="company-night-refund-conversion-hint">
                          <p>{t("page.form.companyNightRefundCashHint")}</p>
                          {companyNightRefundValidationMessage ? (
                            <p className="mt-1 text-rose-800" role="alert">{companyNightRefundValidationMessage}</p>
                          ) : null}
                        </div>
                      ) : paymentTenderCurrency !== editingCurrencyCode ? (
                        paymentFxQuoteQuery.isError ? (
                          <p className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" data-testid="payment-fx-error">
                            No se pudo obtener una cotización vigente desde DolarAPI. El cobro queda bloqueado hasta poder consultar el mercado elegido por el hotel.
                          </p>
                        ) : paymentFxQuoteQuery.isLoading || !paymentFxQuoteQuery.data ? (
                          <p className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600" role="status">
                            Consultando cotización vigente desde DolarAPI…
                          </p>
                        ) : (
                          <div className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950" data-testid="payment-fx-quote">
                            <p className="font-semibold">
                              DolarAPI · {paymentFxQuoteQuery.data.configured_market === "blue" ? "Blue" : "Oficial"} · 1 {editingCurrencyCode} = {paymentFxRate.toLocaleString("es-AR", { maximumFractionDigits: 6 })} {paymentTenderCurrency}
                              {paymentFxQuoteQuery.data.quote_details?.source_quote?.is_derived_blue || paymentFxQuoteQuery.data.quote_details?.target_quote?.is_derived_blue ? " · equivalente blue derivado" : ""}
                            </p>
                            <p className="mt-1">
                              El importe recibido se aplica al saldo en {editingCurrencyCode} con esta cotización y el spread configurado. No se usa otro mercado si esta cotización falla.
                              {paymentAmountInput && Number.isFinite(Number(paymentAmountInput)) && Number(paymentAmountInput) > 0 && conversionReady
                                ? t("page.form.fxCreditEstimate", { amount: formatMoney(convertTenderToReservation(Number(paymentAmountInput)) ?? 0, editingCurrencyCode) })
                                : ""}
                            </p>
                          </div>
                        )
                      ) : null}
                      {paymentMethod === "cash" && paymentTenderCurrency !== editingCurrencyCode && !hasMatchingCashSession ? (
                        <p className="mt-1 text-xs text-amber-800">Abrí una caja en {paymentTenderCurrency} para registrar ese efectivo y poder arquearlo en su moneda.</p>
                      ) : null}
                    </div>
                    {paymentMethod === "cash" && canRecordPriorReceipt ? (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 sm:col-span-6">
                        <label className="flex items-start gap-2 text-sm font-semibold text-slate-800">
                          <input
                            type="checkbox"
                            checked={collectedBefore}
                            disabled={paymentTenderCurrency !== editingCurrencyCode}
                            onChange={(event) => setCollectedBefore(event.target.checked)}
                            className="mt-0.5"
                            data-testid="prior-receipt-toggle"
                          />
                          <span>{t("page.form.collectedBeforeSystem")}</span>
                        </label>
                        {collectedBefore ? (
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <LocalizedDateField
                              id="prior-receipt-date"
                              label={t("page.form.priorReceiptDate")}
                              value={collectedOn}
                              onChange={setCollectedOn}
                              required
                              className="w-full"
                              labelClassName="text-xs font-semibold text-slate-600"
                              inputClassName="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 pr-10 text-sm font-normal text-slate-800 shadow-sm"
                              placeholder={t("page.dateInput.datePlaceholder")}
                              chooseDateLabel={t("page.dateInput.chooseDate")}
                              invalidMessage={t("page.dateInput.invalidDate")}
                              testId="prior-receipt-date"
                            />
                            <label className="text-xs font-semibold text-slate-600">
                              {t("page.form.priorReceiptReason")}
                              <input
                                type="text"
                                required
                                maxLength={240}
                                value={priorReceiptNote}
                                onChange={(event) => setPriorReceiptNote(event.target.value)}
                                placeholder={t("page.form.priorReceiptReasonPlaceholder")}
                                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                                data-testid="prior-receipt-reason"
                              />
                            </label>
                            <p className="text-xs font-normal text-amber-900 sm:col-span-2">
                              {t("page.form.priorReceiptCashHint")}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {paymentMethod === "cash" && canRefundPayment ? (
                      <>
                        <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                          {t("page.form.refundSource")}
                          <select
                            value={selectedRefundTargetId ?? ""}
                            onChange={(event) => {
                              const nextId = event.target.value ? Number(event.target.value) : null;
                              const nextSource = refundablePaymentOptions.find((transaction) => transaction.id === nextId);
                              setRefundTargetTransactionId(nextId);
                              setRefundNightAmounts({});
                              setPaymentAmountInput("");
                              if (nextSource?.company_night_charge_refundable_allocations?.length) {
                                setPaymentTenderCurrencyInput(nextSource.currency);
                              }
                            }}
                            disabled={refundablePaymentOptions.length === 0}
                            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm disabled:bg-slate-100"
                          >
                            {refundablePaymentOptions.length === 0 ? (
                              <option value="">{t("page.form.noRefundablePayments")}</option>
                            ) : null}
                            {refundablePaymentOptions.map((transaction) => (
                              <option key={transaction.id} value={transaction.id}>
                                {transaction.method} · {formatMoney(transaction.amount, transaction.currency)} · {t("page.form.refundRemaining", { amount: formatMoney(transaction.refundableRemaining, transaction.currency) })}
                              </option>
                            ))}
                          </select>
                        </label>
                        {isCompanyNightRefund ? (
                          <section className="rounded-lg border border-violet-200 bg-violet-50/70 p-3 sm:col-span-6" aria-labelledby="company-night-refund-heading" data-testid="company-night-refund-allocations">
                            <h3 id="company-night-refund-heading" className="text-sm font-semibold text-violet-950">
                              {t("page.form.companyNightRefundTitle")}
                            </h3>
                            <p className="mt-1 text-xs text-violet-900">
                              {t("page.form.companyNightRefundHint", { currency: paymentReservationCurrency })}
                            </p>
                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              {enteredCompanyNightRefunds.map((allocation) => {
                                const date = new Intl.DateTimeFormat(
                                  i18n.resolvedLanguage?.startsWith("en") ? "en-US" : "es-AR",
                                  { dateStyle: "medium", timeZone: "UTC" }
                                ).format(new Date(`${allocation.stay_date}T00:00:00Z`));
                                const inputId = `company-night-refund-${allocation.charge_id}`;
                                const availableAmount = Number.isFinite(allocation.remainingAmount)
                                  ? Math.max(0, allocation.remainingAmount)
                                  : 0;
                                return (
                                  <label key={allocation.charge_id} htmlFor={inputId} className="rounded-md border border-violet-100 bg-white p-3 text-xs font-semibold text-slate-700">
                                    <span className="block">{t("page.form.companyNightRefundNight", { date })}</span>
                                    <span className="mt-1 block font-normal text-slate-600">
                                      {t("page.form.companyNightRefundAvailable", {
                                        amount: formatMoney(availableAmount, paymentReservationCurrency)
                                      })}
                                    </span>
                                    <span className="mt-2 block">{t("page.form.companyNightRefundAmount")}</span>
                                    <input
                                      id={inputId}
                                      type="number"
                                      min="0.01"
                                      max={availableAmount}
                                      step="0.01"
                                      inputMode="decimal"
                                      value={allocation.rawAmount}
                                      disabled={allocation.remainingCents <= 0}
                                      onChange={(event) => setRefundNightAmounts((current) => ({
                                        ...current,
                                        [allocation.charge_id]: event.target.value
                                      }))}
                                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm disabled:bg-slate-100"
                                      data-testid={`company-night-refund-amount-${allocation.charge_id}`}
                                    />
                                  </label>
                                );
                              })}
                            </div>
                          </section>
                        ) : null}
                        <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                          {t("page.form.refundReason")}
                          <input
                            type="text"
                            maxLength={240}
                            value={refundReasonInput}
                            onChange={(event) => setRefundReasonInput(event.target.value)}
                            placeholder={t("page.form.refundReasonPlaceholder")}
                            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                          />
                        </label>
                      </>
                    ) : null}
                    {isManualPaymentMethod ? (
                      <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                        {paymentMethod === "bank_transfer"
                          ? t("page.form.manualTransferReference")
                          : t("page.form.manualCardReference")}
                        <input
                          type="text"
                          required
                          maxLength={120}
                          value={paymentReferenceInput}
                          onChange={(event) => setPaymentReferenceInput(event.target.value)}
                          placeholder={paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReferencePlaceholder")
                            : t("page.form.manualCardReferencePlaceholder")}
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                        />
                        <span className="mt-1 block font-normal text-slate-500">
                          {paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReferenceHint")
                            : t("page.form.manualCardReferenceHint")}
                        </span>
                      </label>
                    ) : null}
                    <button
                      type="button"
                      onClick={handlePayPartial}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || !canRegisterSelectedPayment}
                      className="rounded-lg border border-sky-200 bg-sky-100 px-3 py-2 text-sm font-semibold text-sky-800 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Cobro parcial
                    </button>
                    <button
                      type="button"
                      onClick={handlePayDeposit}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || !canRegisterSelectedPayment}
                      className="rounded-lg border border-amber-200 bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {depositAmountPreview === null
                        ? t("page.form.registerDeposit")
                        : t("page.form.registerDepositAmount", {
                            amount: formatMoney(depositAmountPreview, paymentTenderCurrency)
                          })}
                    </button>
                    <button
                      type="button"
                      onClick={handlePayFull}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || !canRegisterSelectedPayment}
                      className="rounded-lg border border-emerald-200 bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-800 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {t("page.form.fullPayment")}
                    </button>
                    <button
                      type="button"
                      onClick={handleRefund}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash" || !canRefundPayment || !selectedRefundTargetId || !refundReasonInput.trim() || paymentTenderCurrency !== selectedRefundTarget?.currency || (isCompanyNightRefund && !canSubmitCompanyNightRefund)}
                      className="rounded-lg border border-brand-200 bg-brand-100 px-3 py-2 text-sm font-semibold text-brand-800 hover:border-brand-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {t("page.form.registerRefund")}
                    </button>
                    {paymentMutation.isError && (
                      <p className="text-xs text-rose-600">{t("page.form.paymentError")}</p>
                    )}
                    {paymentMutation.isPending && (
                      <p className="text-sm text-sky-800 sm:col-span-6" role="status" aria-live="polite">
                        {t("page.form.paymentProcessing")}
                      </p>
                    )}
                    {!canOperateCash ? (
                      <p className="text-xs text-amber-700 sm:col-span-6">{t("page.form.paymentPermissionRequired")}</p>
                    ) : null}
                  </div>

                  {paymentMethod === "cash" && (
                    hasOpenCashSession ? (
                      <p className="mt-2 text-xs text-emerald-700">
                        {t("page.form.cashSessionHint")}
                      </p>
                    ) : (
                      <p className="mt-2 text-xs text-amber-700">
                        {t("page.form.noCashSessionHint")}{" "}
                        <Link to="/caja" className="font-semibold underline">
                          {t("page.form.openCashRegister")}
                        </Link>
                        .
                      </p>
                    )
                  )}

                  {paymentMethod === "bank_transfer" && (
                    <div className="mt-3 space-y-3 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-3 text-xs text-slate-700">
                      <div>
                        <p className="font-semibold text-slate-800">{t("page.form.transferProofTitle")}</p>
                        <p className="mt-1 text-slate-600">{t("page.form.transferProofHint")}</p>
                      </div>
                      <label className="block text-xs font-semibold text-slate-700">
                        {t("page.form.transferProofImage")}
                        <input
                          aria-label={t("page.form.transferProofImage")}
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          onChange={(event) => setPaymentProofFile(event.target.files?.[0] ?? null)}
                          className="mt-1 block w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-normal"
                        />
                      </label>
                      <button
                        type="button"
                        onClick={handleSubmitTransferProof}
                        disabled={paymentProofMutations.submitMutation.isPending || paymentSummaryQuery.isLoading || paymentTenderCurrency !== editingCurrencyCode}
                        className="rounded-lg border border-amber-300 bg-amber-100 px-3 py-2 text-xs font-semibold text-amber-900 hover:border-amber-400 disabled:opacity-60"
                      >
                        {paymentProofMutations.submitMutation.isPending ? t("page.form.sendingProof") : t("page.form.sendProof")}
                      </button>
                      {(paymentProofsQuery.data ?? []).length > 0 && (
                        <ul className="space-y-2 border-t border-amber-200 pt-2">
                          {(paymentProofsQuery.data ?? []).map((proof) => (
                            <li key={proof.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white px-2 py-2">
                              <span className="min-w-0">
                                {formatMoney(proof.amount, proof.currency)} · {proof.status}
                                {proof.rejection_reason ? ` · ${proof.rejection_reason}` : ""}
                              </span>
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => void handleViewPaymentProof(proof.id)}
                                  disabled={viewingPaymentProofId === proof.id}
                                  className="rounded-lg border border-slate-200 px-2 py-1 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                                >
                                  {viewingPaymentProofId === proof.id ? t("page.form.openingProof") : t("page.form.viewProof")}
                                </button>
                                {canApprovePaymentProof && proof.status === "pending" && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => void handleApprovePaymentProof(proof.id)}
                                      disabled={paymentProofMutations.approveMutation.isPending}
                                      className="rounded-lg border border-emerald-200 px-2 py-1 font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
                                    >
                                      {t("page.form.approveProof")}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setRejectingPaymentProofId(rejectingPaymentProofId === proof.id ? null : proof.id)}
                                      disabled={paymentProofMutations.rejectMutation.isPending}
                                      className="rounded-lg border border-rose-200 px-2 py-1 font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                                    >
                                      {t("page.form.rejectProof")}
                                    </button>
                                  </>
                                )}
                              </div>
                              {canApprovePaymentProof && rejectingPaymentProofId === proof.id && proof.status === "pending" && (
                                <div className="flex w-full flex-wrap items-center gap-2">
                                  <label className="sr-only" htmlFor={`payment-proof-reason-${proof.id}`}>
                                    {t("page.form.rejectReasonLabel")}
                                  </label>
                                  <input
                                    id={`payment-proof-reason-${proof.id}`}
                                    value={paymentProofRejectReason}
                                    onChange={(event) => setPaymentProofRejectReason(event.target.value)}
                                    placeholder={t("page.form.rejectReasonPlaceholder")}
                                    className="min-w-[12rem] flex-1 rounded-lg border border-rose-200 px-2 py-1 text-xs"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleRejectPaymentProof(proof.id)}
                                    disabled={paymentProofMutations.rejectMutation.isPending}
                                    className="rounded-lg bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                                  >
                                    {t("page.form.confirmReject")}
                                  </button>
                                </div>
                              )}
                              {paymentProofPreview?.proofId === proof.id && (
                                <div className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2">
                                  <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold text-slate-700">
                                    <span>{t("page.form.proofPreviewTitle")}</span>
                                    <button type="button" onClick={closePaymentProofPreview} className="underline">
                                      {t("page.common.close")}
                                    </button>
                                  </div>
                                  <img src={paymentProofPreview.url} alt={proof.original_filename || t("page.form.proofAltFallback")} className="max-h-64 w-full rounded object-contain" />
                                </div>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* bank_transfer is reconciled from a proof of an already-sent amount
                      (submit_transfer_proof caps it at the balance due) -- approval never
                      adds a surcharge on top (see payment_service.process_payment
                      apply_surcharge=False), so showing a higher final figure here would
                      promise a surcharge that is never actually charged. */}
                  {activeSurcharge && paymentMethod !== "bank_transfer" && paymentSummary && (paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0) > 0 && (
                    <p className="mt-2 text-xs text-amber-700">
                      {t("page.form.surchargePrefix", {
                        method: t(`page.paymentMethods.${paymentMethod}`),
                        value:
                          activeSurcharge.surcharge_type === "percentage"
                            ? `${activeSurcharge.amount}%`
                            : formatMoney(activeSurcharge.amount, editingCurrencyCode),
                        balance: formatMoney(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0, editingCurrencyCode)
                      })}{" "}
                      <strong>
                        {formatMoney(
                          grossWithSurcharge(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0, activeSurcharge),
                          editingCurrencyCode
                        )}
                      </strong>
                      .
                    </p>
                  )}

                  <div className="mt-3 rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-xs text-slate-700">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-slate-800">{t("page.form.depositRequestTitle")}</p>
                      <button
                        type="button"
                        onClick={handleGenerateDepositLink}
                        disabled={paymentLinkCreate.isPending || paymentSummaryQuery.isLoading}
                        className="rounded-lg border border-sky-200 bg-white px-3 py-1 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:opacity-60"
                      >
                        {paymentLinkCreate.isPending ? t("page.form.creatingLink") : t("page.form.createLinkRequest")}
                      </button>
                    </div>
                    {(paymentLinksQuery.data ?? []).length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {(paymentLinksQuery.data ?? []).map((lnk) => {
                          const payableUrl =
                            lnk.execution_mode === "provider" && lnk.payable
                              ? lnk.external_checkout_url
                              : null;
                          return (
                            <li key={lnk.id} className="flex flex-wrap items-center justify-between gap-2" data-testid={`payment-link-${lnk.id}`}>
                              <span className="min-w-0">
                                <span className="block truncate">
                                  {formatMoney(lnk.requested_amount, lnk.currency)} · {lnk.status}
                                </span>
                                {!payableUrl && (
                                  <span className="block text-[11px] font-semibold text-amber-700" data-testid="payment-link-local-only">
                                    {t("page.form.localOnlyLink")}
                                  </span>
                                )}
                              </span>
                              <span className="flex shrink-0 gap-2">
                                {payableUrl && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigator.clipboard?.writeText(payableUrl);
                                      showToast("success", t("page.messages.linkCopied"));
                                    }}
                                    className="rounded-lg border border-slate-200 px-2 py-1 font-semibold text-slate-700 hover:bg-white"
                                  >
                                    {t("page.form.copyLink")}
                                  </button>
                                )}
                                {lnk.status === "pending" && lnk.execution_mode === "local_only" && (
                                  <button
                                    type="button"
                                    onClick={() => void handleCancelPaymentLink(lnk.id)}
                                    disabled={paymentLinkCancel.isPending}
                                    className="rounded-lg border border-slate-200 px-2 py-1 font-semibold text-slate-600 hover:bg-white disabled:opacity-60"
                                  >
                                    {t("page.form.cancelLinkRequest")}
                                  </button>
                                )}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="mt-1 text-slate-500">{t("page.form.noLinkRequests")}</p>
                    )}
                  </div>

                  {paymentSummary?.transactions?.length ? (
                    <div className="mt-3 rounded-lg border border-emerald-100 bg-white/60 px-3 py-2 text-xs text-slate-700">
                      <p className="font-semibold text-slate-800">{t("page.form.movementsTitle")}</p>
                      <ul className="mt-1 space-y-1">
                        {paymentSummary.transactions.map((tx) => (
                          <li key={tx.id} className="flex items-center justify-between">
                            <span>
                              {tx.type} · {tx.method}
                              {tx.collected_before ? (
                                <span className="block text-amber-800">
                                  {t("page.form.priorReceiptRecorded", {
                                    date: tx.collected_on ?? "",
                                    reason: tx.prior_receipt_note ?? ""
                                  })}
                                </span>
                              ) : null}
                              {tx.manual_reference ? <span className="block text-slate-500">{t("page.form.manualPaymentReferenceRecorded", { reference: tx.manual_reference })}</span> : null}
                              {tx.fee_amount && tx.fee_amount > 0 ? (
                                <span className="text-amber-700">{t("page.form.feeSuffix", { amount: formatMoney(tx.fee_amount, tx.currency) })}</span>
                              ) : null}
                              {tx.applied_currency && tx.applied_currency !== tx.currency && tx.applied_amount !== null && tx.applied_amount !== undefined ? (
                                <span className="block text-sky-800">
                                  Aplica {formatMoney(tx.applied_amount, tx.applied_currency)} al saldo · 1 {tx.applied_currency} = {Number(tx.fx_rate_snapshot ?? 0).toLocaleString("es-AR", { maximumFractionDigits: 6 })} {tx.currency}
                                </span>
                              ) : null}
                            </span>
                            <span className="font-semibold">
                              {formatMoney(tx.gross_amount ?? tx.amount, tx.currency)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-600">{t("page.form.noPayments")}</p>
                  )}
                </div>
              )}
              {editing && isDeferredCompanyReservation(editing) ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                  {t("page.form.deferredCompanyBilling")}
                </p>
              ) : null}

              </fieldset>
              {formError && (
                <div
                  className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800"
                  data-testid="reservation-submit-error"
                  role="alert"
                >
                  {formError}
                </div>
              )}
              {reservationSavePending && (
                <p className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900" data-testid="reservation-save-status" role="status" aria-live="polite">
                  {t("page.form.savingReservation")}
                </p>
              )}
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={formBusy}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {t("page.form.cancel")}
                </button>
                <button
                  type="submit"
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  disabled={
                    createMutation.isPending ||
                    createGroupMutation.isPending ||
                    updateMutation.isPending ||
                    collaborativeReservation.isSaving ||
                    subscriptionBlocked ||
                    groupAvailabilityBlocked ||
                    Boolean(lastCreatedReservation) ||
                    (!editing &&
                      manualTotalAmountInput.trim() === "" &&
                      (quoteQuery.isFetching || !reservationQuote?.quoteToken))
                  }
                >
                  {reservationSavePending
                    ? t("page.form.savingReservation")
                    : editing
                    ? t("page.form.saveChanges")
                    : quoteQuery.isFetching && manualTotalAmountInput.trim() === ""
                      ? t("page.form.updating")
                      : Number(formValues.group_size) > 1
                        ? t("page.form.createGroup", { count: Number(formValues.group_size) })
                        : t("page.form.create")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ManualOtaReservationModal open={otaFormOpen} onClose={() => setOtaFormOpen(false)} />

      {restrictionOverridePrompt.phase !== "idle" ? (
        <RestrictionOverrideModal
          phase={restrictionOverridePrompt.phase}
          onSubmit={restrictionOverridePrompt.submit}
          onCancel={restrictionOverridePrompt.dismiss}
          isPending={createMutation.isPending || createGroupMutation.isPending || updateMutation.isPending || checkInMutation.isPending}
        />
      ) : null}

      {detailsReservation && (
        <div className="fixed inset-0 z-30 flex animate-fade-in items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-3xl max-h-[90vh] animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.eyebrow")}</p>
                <h3 className="text-lg font-semibold text-slate-900">{t("page.details.title", { code: detailsReservation.confirmation_code })}</h3>
                <p className="text-xs text-slate-500">
                  {t("page.details.subtitle", {
                    guest: reservationGuestLabel(t, detailsReservation),
                    category: detailsReservation.category_name ?? categoryNameById.get(detailsReservation.category_id) ?? t("page.common.informationUnavailable"),
                    room: detailsRoom
                      ? t("page.common.room", { number: detailsRoom.room_number })
                      : detailsReservation.room_number
                        ? t("page.common.room", { number: detailsReservation.room_number })
                        : t("page.common.unassigned")
                  })}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={exportVoucher}
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
                >
                  {t("page.details.exportVoucher")}
                </button>
                <button onClick={closeDetails} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                  {t("page.common.close")}
                </button>
              </div>
            </div>

            {detailsActionError?.reservationId === detailsReservation.id && (
              <div className="mt-4 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" data-testid="reservation-details-action-error" role="alert" aria-live="assertive">
                <p className="flex-1">{detailsActionError.message}</p>
                <button type="button" className="text-xs font-semibold hover:text-rose-950" onClick={() => setDetailsActionError(null)}>
                  {t("page.toast.close")}
                </button>
              </div>
            )}

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-sky-200 bg-sky-50 p-3 md:col-span-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-sky-700">{t("page.details.communicationEyebrow")}</p>
                    <p className="text-sm font-semibold text-slate-900">{t("page.details.communicationTitle")}</p>
                    <p className="text-xs text-slate-600">{t("page.details.communicationHint")}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="rounded-lg border border-sky-300 bg-white px-3 py-2 text-xs font-semibold text-sky-800 hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!hasPermission("reservation:update") || communicationMutation.isPending || !communicationRecipient.trim()}
                      onClick={() => void communicationMutation.mutateAsync({ kind: "confirmation", resend: false })}
                    >
                      {t("page.details.sendConfirmation")}
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-sky-300 bg-white px-3 py-2 text-xs font-semibold text-sky-800 hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!hasPermission("reservation:update") || communicationMutation.isPending || !communicationRecipient.trim()}
                      onClick={() => void communicationMutation.mutateAsync({ kind: "voucher", resend: false })}
                    >
                      {t("page.details.sendVoucher")}
                    </button>
                  </div>
                </div>
                <label className="block text-xs font-semibold text-slate-700" htmlFor="reservation-communication-recipient">
                  {t("page.details.communicationRecipient")}
                </label>
                <input
                  id="reservation-communication-recipient"
                  type="email"
                  value={communicationRecipient}
                  onChange={(event) => setCommunicationRecipient(event.target.value)}
                  placeholder={t("page.details.communicationRecipientPlaceholder")}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  autoComplete="email"
                />
                {communicationsQuery.isLoading ? (
                  <p className="text-xs text-slate-600">{t("page.details.communicationLoading")}</p>
                ) : communicationsQuery.isError ? (
                  <p className="text-xs text-rose-700">{t("page.details.communicationLoadError")}</p>
                ) : communicationsQuery.data?.length ? (
                  <ul className="space-y-1 text-xs text-slate-700">
                    {communicationsQuery.data.slice(0, 4).map((delivery) => (
                      <li key={delivery.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-white px-2 py-1.5">
                        <span>
                          {delivery.kind === "confirmation" ? t("page.details.communicationConfirmation") : t("page.details.communicationVoucher")}
                          {" · "}{delivery.recipient_email}
                        </span>
                        <span className="flex items-center gap-2">
                          <span className={delivery.status === "accepted" ? "font-semibold text-emerald-700" : delivery.status === "failed" ? "font-semibold text-rose-700" : "font-semibold text-amber-700"}>
                            {t(`page.details.communicationStatus.${delivery.status}`)}
                          </span>
                          {(delivery.status === "failed" || delivery.status === "unknown") && hasPermission("reservation:update") ? (
                            <button
                              type="button"
                              className="font-semibold text-sky-700 underline hover:text-sky-900 disabled:opacity-60"
                              disabled={communicationMutation.isPending}
                              onClick={() => {
                                setCommunicationRecipient(delivery.recipient_email);
                                void communicationMutation.mutateAsync({ kind: delivery.kind, resend: true, recipient: delivery.recipient_email });
                              }}
                            >
                              {t("page.details.communicationResend")}
                            </button>
                          ) : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-600">{t("page.details.communicationEmpty")}</p>
                )}
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.timelineTitle")}</p>
                <ul className="space-y-2 text-sm text-slate-800">
                  <li>
                    <span className="font-semibold">{t("page.details.timelineCheckIn")}</span> {detailsReservation.check_in_date}
                  </li>
                  <li>
                    <span className="font-semibold">{t("page.details.timelineCheckOut")}</span> {detailsReservation.check_out_date}
                  </li>
                  <li>
                    <span className="font-semibold">{t("page.details.timelineArrivalTime")}</span>{" "}
                    {detailsReservation.arrival_time_hint || "—"}
                  </li>
                  <li>
                    <span className="font-semibold">{t("page.details.timelineStatus")}</span> {statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}
                  </li>
                  {detailsReservation.manual_rate_reason ? (
                    <li className="rounded-md border border-brand-200 bg-brand-50 px-2 py-1.5">
                      <span className="font-semibold">{t("page.details.manualRateLabel")}</span>{" "}
                      {detailsReservation.manual_rate_reason}
                    </li>
                  ) : null}
                  {detailsSummary?.transactions?.length ? (
                    <li>
                      <span className="font-semibold">{t("page.details.timelineLastPayment")}</span>{" "}
                      {detailsSummary.transactions[detailsSummary.transactions.length - 1].created_at}
                    </li>
                  ) : null}
                </ul>
              </div>

              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 md:col-span-2">
                <p className="text-xs uppercase tracking-wide text-amber-700">{t("page.details.reservationComment")}</p>
                <p className="whitespace-pre-wrap text-sm text-amber-950">
                  {detailsReservation.reservation_comment || "—"}
                </p>
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.financeTitle")}</p>
                {detailsDeferredCompanyBilling ? (
                  <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950" data-testid="deferred-company-finance-note">
                    {t("page.details.deferredCompanyFinance")}
                  </p>
                ) : detailsFinancialsLoading ? (
                  <p className="rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-sm text-slate-600">
                    {t("page.details.financeLoading")}
                  </p>
                ) : detailsSummary ? (
                  <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeTotal")}</p>
                      <p className="font-semibold">{formatMoney(detailsReservation.total_amount ?? detailsSummary.total_amount, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeHotelReceived")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.hotel_received_amount ?? 0, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeOtaPrepaid")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.ota_prepaid_amount ?? 0, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeDeposit")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.deposit_required, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeBalance")}</p>
                      <p className="font-semibold">
                        {formatMoney(
                          detailsOperations?.financial_summary.operational_balance_due ?? detailsSummary.operational_balance_due ?? detailsSummary.balance_due,
                          detailsCurrencyCode
                        )}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert" data-testid="reservation-financial-summary-error">
                    <span>{t("page.details.financeLoadError")}</span>
                    <button
                      type="button"
                      onClick={() => void detailsSummaryQuery.refetch()}
                      disabled={detailsSummaryQuery.isFetching}
                      className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                    >
                      {t("page.details.operationRetry")}
                    </button>
                  </div>
                )}
                {!detailsDeferredCompanyBilling && detailsOperations?.financial_summary ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-slate-500">{t("page.details.financeOperationalTotal")}</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_total_amount ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">{t("page.details.financeOperationalBalance")}</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_balance_due ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">{t("page.details.financeCollection")}</p>
                        <p className="font-semibold">{enumLabel("collection", detailsOperations.payment_collection_model)}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">{t("page.details.financeSettlement")}</p>
                        <p className="font-semibold">{enumLabel("settlement", detailsOperations.settlement_status)}</p>
                      </div>
                    </div>
                    {detailsOperations.financial_summary.recommended_next_action ? (
                      <p className="mt-2 text-xs text-amber-700">
                        {t("page.details.financeNextAction", { action: enumLabel("nextAction", detailsOperations.financial_summary.recommended_next_action) })}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.operationEyebrow")}</p>
                  {detailsOperationsQuery.isFetching ? <span className="text-xs text-slate-500">{t("page.details.operationUpdating")}</span> : null}
                </div>
                {detailsOperationsQuery.isError ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert" data-testid="reservation-operations-summary-error">
                    <span>{t("page.details.operationLoadError")}</span>
                    <button
                      type="button"
                      onClick={() => void detailsOperationsQuery.refetch()}
                      disabled={detailsOperationsQuery.isFetching}
                      className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 font-semibold hover:bg-rose-100 disabled:opacity-60"
                    >
                      {t("page.details.operationRetry")}
                    </button>
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                  <div>
                    <p className="text-xs text-slate-500">{t("page.details.operationAllocation")}</p>
                    <p className="font-semibold">{translatedEnum("allocationStatus", detailsOperations?.allocation_status ?? detailsReservation.allocation_status)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{t("page.details.operationManualReview")}</p>
                    <p className="font-semibold">{detailsOperations?.requires_manual_review ? t("page.details.operationYes") : t("page.details.operationNo")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{t("page.details.operationPendingActions")}</p>
                    <p className="font-semibold">{detailsOperations?.pending_action_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{t("page.details.operationLastMove")}</p>
                    <p className="font-semibold">{detailsOperations?.latest_room_move?.move_type ?? "-"}</p>
                  </div>
                </div>
                {detailsOperations?.ota_link ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <p className="font-semibold text-slate-800">{t("page.details.externalChannelTitle")}</p>
                    <p>{t("page.details.externalChannelStatus", { status: detailsOperations.ota_link.provider_state })}</p>
                    <p>{t("page.details.externalChannelSync", { status: detailsOperations.ota_link.sync_status ?? "-" })}</p>
                    {detailsOperations.ota_link.error_message ? (
                      <p className="mt-1 text-amber-700">{detailsOperations.ota_link.error_message}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.actionsEyebrow")}</p>
                {detailsOperations?.pending_actions?.length ? (
                  <div className="space-y-2">
                    {detailsOperations.pending_actions.map((action) => {
                      const priorityClass = priorityClassName[action.priority];
                      const isResolveExternal =
                        action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
                      const isManualReview = action.code === "manual_review_required";

                      return (
                        <div key={`${action.reservation_id}:${action.action_key}`} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${priorityClass}`}>
                                  {t(`page.priority.${action.priority}`)}
                                </span>
                                <p className="text-sm font-semibold text-slate-900">{action.title}</p>
                              </div>
                              <p className="mt-1 text-xs text-slate-600">{action.detail}</p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {isManualReview ? (
                                <button
                                  type="button"
                                  onClick={() => handleClearManualReview(detailsReservation.id)}
                                  disabled={clearManualReviewMutation.isPending}
                                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {t("page.pendingActions.closeReview")}
                                </button>
                              ) : null}
                              {isResolveExternal ? (
                                <button
                                  type="button"
                                  onClick={() => handleResolveExternal(detailsReservation.id)}
                                  disabled={resolveExternalMutation.isPending}
                                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {t("page.pendingActions.markResolved")}
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">{t("page.details.noPendingActions")}</p>
                )}
              </div>
            </div>

            <section
              role="region"
              aria-labelledby="stay-operations-title"
              className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.stayOperationsEyebrow")}</p>
                  <h4 id="stay-operations-title" className="text-sm font-semibold text-slate-900">
                    {t("page.details.stayOperationsTitle")}
                  </h4>
                  <p className="text-xs text-slate-600">
                    {t("page.details.stayOperationsHint")}
                  </p>
                </div>
                {detailsReservation.version !== undefined ? (
                  <span className="text-xs text-slate-500">{t("page.details.version", { version: detailsReservation.version })}</span>
                ) : null}
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {canManageCompanyReservation(detailsReservation) ? (
                <form className="space-y-3 rounded-lg border border-slate-200 bg-white p-3" onSubmit={handleRoomMove}>
                  <p className="text-sm font-semibold text-slate-800">{t("page.details.changeRoomTitle")}</p>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("page.details.targetRoom")}</span>
                    <select
                      value={roomMoveForm.to_room_id}
                      onChange={(event) => setRoomMoveForm((current) => ({ ...current, to_room_id: event.target.value }))}
                      disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">{t("page.details.selectRoom")}</option>
                      {moveRoomOptions.map((room) => {
                        const blocked = moveBlockByRoomId.get(room.id) ?? null;
                        return (
                          <option key={room.id} value={room.id} disabled={blocked !== null}>
                            {t("page.details.roomOptionFloor", { number: room.room_number, floor: room.floor })}
                            {room.category_id !== detailsReservation.category_id
                              ? ` · ${categoryNameById.get(room.category_id) ?? t("page.details.otherCategoryFallback")}`
                              : ""}
                            {blocked ? ` — ${blocked}` : ""}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                  {moveCrossesCategory ? (
                    <label className="space-y-1 text-sm">
                      <span className="text-slate-600">{t("page.details.categoryPriceLabel")}</span>
                      <select
                        value={roomMoveForm.price_action}
                        onChange={(event) =>
                          setRoomMoveForm((current) => ({
                            ...current,
                            price_action: event.target.value as "keep" | "reprice"
                          }))
                        }
                        disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      >
                        <option value="keep">{t("page.details.keepCurrentPrice")}</option>
                        <option value="reprice">{t("page.details.repriceToNewCategory")}</option>
                      </select>
                      <span className="block text-xs text-slate-500">
                        {t("page.details.categoryPriceHint")}
                      </span>
                    </label>
                  ) : null}
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("page.details.changeReasonLabel")}</span>
                    <select
                      value={roomMoveForm.reason_code}
                      onChange={(event) => setRoomMoveForm((current) => ({ ...current, reason_code: event.target.value }))}
                      disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">{t("page.details.chooseReason")}</option>
                      {ROOM_MOVE_REASONS.map((reason) => (
                        <option key={reason.value} value={reason.value}>
                          {reason.label}
                        </option>
                      ))}
                    </select>
                    {roomMoveForm.reason_code === "guest_complaint" ? (
                      <span className="block text-xs text-amber-700">
                        {t("page.details.guestComplaintHint")}
                      </span>
                    ) : null}
                  </label>
                  {detailsReservation.status === "checked_in" ? (
                    <>
                      <label className="space-y-1 text-sm">
                        <span className="text-slate-600">Estado de la habitación origen</span>
                        <select
                          value={roomMoveForm.origin_room_disposition}
                          onChange={(event) => setRoomMoveForm((current) => ({ ...current, origin_room_disposition: event.target.value }))}
                          required
                          disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2"
                        >
                          <option value="">Elegí una opción</option>
                          <option value="cleaning">Pasar a limpieza</option>
                          <option value="available">Dejar libre</option>
                          <option value="maintenance">Enviar a mantenimiento</option>
                        </select>
                      </label>
                      {roomMoveForm.origin_room_disposition && roomMoveForm.origin_room_disposition !== "cleaning" ? (
                        <label className="space-y-1 text-sm">
                          <span className="text-slate-600">Justificación obligatoria</span>
                          <textarea
                            value={roomMoveForm.origin_room_disposition_note}
                            onChange={(event) => setRoomMoveForm((current) => ({ ...current, origin_room_disposition_note: event.target.value }))}
                            required
                            rows={2}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2"
                          />
                        </label>
                      ) : null}
                    </>
                  ) : null}
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("page.details.changeNotesLabel")}</span>
                    <textarea
                      value={roomMoveForm.notes}
                      onChange={(event) => setRoomMoveForm((current) => ({ ...current, notes: event.target.value }))}
                      disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                      rows={2}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending || moveRoomOptions.length === 0 || (detailsReservation.status === "checked_in" && (!roomMoveForm.origin_room_disposition || (roomMoveForm.origin_room_disposition !== "cleaning" && !roomMoveForm.origin_room_disposition_note.trim())))}
                    className="w-full rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {roomMoveMutation.isPending ? t("page.details.movingRoom") : t("page.details.moveRoom")}
                  </button>
                  {moveRoomOptions.length === 0 && canMoveRoom(detailsReservation.status) ? (
                    <p className="text-xs text-amber-700">{t("page.details.noOtherRoomAvailable")}</p>
                  ) : null}
                </form>
                ) : null}

                <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-slate-800">{t("page.details.noShowTitle")}</p>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">{t("page.details.noShowNotesLabel")}</span>
                    <textarea
                      aria-label={t("page.details.noShowNotesLabel")}
                      value={noShowNotes}
                      onChange={(event) => setNoShowNotes(event.target.value)}
                      disabled={!canNoShow(detailsReservation.status) || noShowMutation.isPending}
                      rows={4}
                      placeholder={t("page.details.noShowNotesPlaceholder")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={handleNoShow}
                    disabled={!canNoShow(detailsReservation.status) || noShowMutation.isPending}
                    className="w-full rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {noShowMutation.isPending ? t("page.details.registeringNoShow") : t("page.details.markNoShow")}
                  </button>
                  {!canNoShow(detailsReservation.status) ? (
                    <p className="text-xs text-slate-500">{t("page.details.noShowBlockedHint")}</p>
                  ) : null}
                </div>
              </div>
            </section>

            <section
              role="region"
              aria-labelledby="reservation-charges-title"
              className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.guestAccountEyebrow")}</p>
                  <h4 id="reservation-charges-title" className="text-sm font-semibold text-slate-900">
                    {t("page.details.chargesTitle")}
                  </h4>
                  <p className="text-xs text-slate-600">
                    {t("page.details.chargesHint")}
                  </p>
                </div>
                {!detailsDeferredCompanyBilling && detailsOperations?.financial_summary ? (
                  <span className="text-xs font-semibold text-slate-700">
                    {t("page.details.operationalBalanceLabel", {
                      amount: formatMoney(detailsOperations.financial_summary.operational_balance_due ?? 0, detailsOperations.financial_summary.currency_code)
                    })}
                  </span>
                ) : null}
              </div>

              {detailsOperations?.financial_summary?.billing_adjustments?.length ? (
                <ul className="mt-3 space-y-2" aria-label={t("page.details.chargesTitle")}>
                  {detailsOperations.financial_summary.billing_adjustments.map((charge) => (
                    <li key={charge.id} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
                      <div>
                        <p className="font-semibold text-slate-900">{charge.notes || t("page.details.additionalChargeFallback")}</p>
                        <p className="text-xs text-slate-500">{charge.type === "charge" ? t("page.details.chargeTypeConsumption") : charge.type}</p>
                      </div>
                      <span className="font-semibold text-slate-900">{formatMoney(charge.total_amount, charge.currency_code)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-slate-600">{t("page.details.noCharges")}</p>
              )}

              <form
                className="mt-3 grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[minmax(0,1fr)_10rem_auto] md:items-end"
                onSubmit={async (event) => {
                  event.preventDefault();
                  const amount = Number(chargeForm.amount);
                  if (!chargeForm.description.trim() || !Number.isFinite(amount) || amount <= 0) {
                    showToast("error", t("page.errors.chargeFieldsRequired"));
                    return;
                  }
                  try {
                    await chargeMutation.mutateAsync({
                      reservationId: detailsReservation.id,
                      payload: { description: chargeForm.description, amount, currency_code: detailsReservation.currency_code || "ARS" }
                    });
                  } catch (err: unknown) {
                    showToast("error", err instanceof Error ? err.message : t("page.errors.chargeFailed"));
                  }
                }}
              >
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">{t("page.details.chargeDetailLabel")}</span>
                  <input
                    value={chargeForm.description}
                    onChange={(event) => setChargeForm((current) => ({ ...current, description: event.target.value }))}
                    placeholder={t("page.details.chargeDetailPlaceholder")}
                    disabled={!canAddCharge(detailsReservation.status) || chargeMutation.isPending}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">{t("page.details.chargeAmountLabel")}</span>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={chargeForm.amount}
                    onChange={(event) => setChargeForm((current) => ({ ...current, amount: event.target.value }))}
                    placeholder={t("page.details.chargeAmountPlaceholder")}
                    disabled={!canAddCharge(detailsReservation.status) || chargeMutation.isPending}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <button
                  type="submit"
                  disabled={!canAddCharge(detailsReservation.status) || chargeMutation.isPending}
                  className="rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {chargeMutation.isPending ? t("page.details.loadingCharge") : t("page.details.submitCharge")}
                </button>
              </form>
              {!canAddCharge(detailsReservation.status) ? (
                <p className="mt-2 text-xs text-slate-500">
                  {hasPermission("reservation:charge")
                    ? t("page.details.chargesBlockedHint")
                    : t("page.details.chargePermissionRequired")}
                </p>
              ) : null}
            </section>

            {detailsOperations?.open_adjustments?.length ? (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.adjustmentsTitle")}</p>
                </div>
                <div className="divide-y divide-slate-200 p-3">
                  {detailsOperations.open_adjustments.map((adjustment) => (
                    <div key={adjustment.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                      <div>
                        <p className="font-semibold text-slate-900">{translatedEnum("adjustmentKind", adjustment.kind)}</p>
                        <p className="text-xs text-slate-600">
                          {t("page.details.adjustmentStatusLine", {
                            status: translatedEnum("adjustmentStatus", adjustment.status),
                            external: adjustment.external_resolution_status
                              ? translatedEnum("externalResolution", adjustment.external_resolution_status)
                              : "-"
                          })}
                        </p>
                        {adjustment.notes ? <p className="mt-1 text-xs text-slate-500">{adjustment.notes}</p> : null}
                      </div>
                      <div className="text-right text-xs text-slate-600">
                        <p>{adjustment.currency_code ?? "-"}</p>
                        <p className="font-semibold">{formatMoney(adjustment.amount_delta ?? 0, adjustment.currency_code)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-4 rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.paymentsTitle")}</p>
              </div>
              <div className="p-3 text-sm text-slate-800">
                {detailsSummary?.transactions?.length ? (
                  <ul className="divide-y divide-slate-200">
                    {detailsSummary.transactions.map((tx) => (
                      <li key={tx.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                        <div>
                          <p className="font-semibold">{formatMoney(tx.amount, tx.currency)}</p>
                          <p className="text-xs text-slate-500">
                            {t("page.details.transactionLine", {
                              type: translatedEnum("transactionType", tx.type),
                              method: t(`page.paymentMethods.${tx.method}`, { defaultValue: t("page.enums.unknownValue") }),
                              status: translatedEnum("transactionStatus", tx.status)
                            })}
                          </p>
                          {tx.manual_reference ? <p className="text-xs text-slate-500">{t("page.form.manualPaymentReferenceRecorded", { reference: tx.manual_reference })}</p> : null}
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className="text-xs text-slate-500">
                            {formatHotelDateTime(tx.created_at, hotelConfigQuery.data?.hotel_timezone, i18n.language === "en" ? "en-US" : "es-AR")}
                          </span>
                          {canPrintPaymentReceipt(tx.status, canOperateCash) ? (
                            <div className="flex flex-wrap items-center justify-end gap-2">
                              <button
                                type="button"
                                data-testid={"payment-receipt-download-" + tx.id}
                                aria-label={t("page.details.receipt.downloadAria", { id: tx.id })}
                                onClick={() => void printPaymentReceipt(tx)}
                                className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                              >
                                {t("page.details.receipt.download")}
                              </button>
                              {canEmailPaymentReceipt ? (
                                <button
                                  type="button"
                                  data-testid={`payment-receipt-email-${tx.id}`}
                                  aria-label={t("page.details.receipt.sendEmailAria", { id: tx.id })}
                                  onClick={(event) => openReceiptEmailDialog(tx.id, event.currentTarget)}
                                  className="rounded-md border border-brand-200 px-2 py-1 text-xs font-semibold text-brand-800 hover:border-brand-300 hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                                >
                                  {t("page.details.receipt.sendEmail")}
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600">{t("page.details.noTransactions")}</p>
                )}
              </div>
            </div>
            {hasPermission("operations:audit:view") ? (
              <div className="mt-4 rounded-lg border border-brand-100 bg-brand-50/30 p-3" data-testid="reservation-audit-activity">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-brand-700">{t("page.details.auditActivityTitle")}</p>
                  {detailsAuditQuery.isFetching ? <span className="text-xs text-slate-500">{t("page.details.auditActivityUpdating")}</span> : null}
                </div>
                {detailsAuditQuery.isError ? <p className="mt-2 text-sm text-rose-700">{t("page.details.auditActivityLoadError")}</p> : detailsAuditQuery.data?.items.length ? (
                  <ul className="mt-2 divide-y divide-brand-100">
                    {detailsAuditQuery.data.items.map((item) => (
                      <li key={`${item.source}-${item.source_id}`} className="py-2 text-sm">
                        <p className="font-semibold text-slate-900">{item.summary}</p>
                        <p className="text-xs text-slate-600">{item.action} · {item.actor_name} · {formatHotelDateTime(item.occurred_at, hotelConfigQuery.data?.hotel_timezone)}</p>
                        {auditMetadataLines(item.details, {
                          arrival: t("page.details.timelineArrivalTime"),
                          comment: t("page.details.reservationComment"),
                          empty: t("page.form.collab.emptyValue")
                        }).map((line) => <p key={line} className="text-xs text-amber-700">{line}</p>)}
                        {item.origin_room_disposition ? (
                          <p className="text-xs text-brand-700">
                            {t("page.details.auditOriginRoom", {
                              disposition: translatedEnum("roomDisposition", item.origin_room_disposition),
                              before: item.origin_room_status_before ? translatedEnum("roomStatus", item.origin_room_status_before) : "-",
                              after: item.origin_room_status_after ? translatedEnum("roomStatus", item.origin_room_status_after) : "-"
                            })}
                          </p>
                        ) : null}
                        {item.payment_method ? (
                          <p className="text-xs text-slate-500">
                            {t("page.details.auditPaymentMethod", {
                              method: t(`page.paymentMethods.${item.payment_method}`, { defaultValue: t("page.enums.unknownValue") })
                            })}{item.amount !== null && item.amount !== undefined ? ` · ${formatMoney(item.amount, item.currency_code)}` : ""}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-2 text-sm text-slate-600">{t("page.details.auditActivityEmpty")}</p>}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {payingGroup && (
        <div className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="group-payment-title"
            className="max-h-[90vh] w-full max-w-2xl animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl"
            data-testid="reservation-group-payment-dialog"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="group-payment-title" className="text-lg font-semibold text-slate-900">
                  {t("page.groups.paymentTitle", { guest: payingGroup.guest_name })}
                </h2>
                <p className="mt-1 text-xs text-slate-600">{t("page.groups.paymentHint")}</p>
              </div>
              <button
                type="button"
                disabled={groupPaymentMutation.isPending}
                onClick={() => { setPayingGroup(null); setGroupPaymentError(null); }}
                className="text-sm text-slate-600 hover:text-slate-900 disabled:opacity-50"
              >
                {t("page.common.close")}
              </button>
            </div>

            {groupPaymentError && (
              <div className="mt-4 flex items-start justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
                <p>{groupPaymentError}</p>
                <button type="button" onClick={() => setGroupPaymentError(null)} className="shrink-0 text-xs font-semibold underline">
                  {t("page.groups.paymentCloseError")}
                </button>
              </div>
            )}

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-semibold text-slate-700">
                {t("page.groups.paymentTotal")}
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={groupPaymentTotalInput}
                    onChange={(event) => setGroupPaymentTotalInput(event.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                    data-testid="group-payment-received-amount"
                  />
                  <span className="text-xs text-slate-500">{payingGroup.currency_code}</span>
                </div>
              </label>
              <label className="text-sm font-semibold text-slate-700">
                {t("page.groups.paymentMethod")}
                <select
                  value={groupPaymentMethod}
                  onChange={(event) => setGroupPaymentMethod(event.target.value as PaymentMethod)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                  data-testid="group-payment-method"
                >
                  {groupPaymentMethods.map((method) => (
                    <option key={method} value={method}>{t(`page.paymentMethods.${method}`)}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-lg border border-slate-200">
              <div className="grid grid-cols-[1fr_9rem] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
                <span>{t("page.groups.paymentAllocation")}</span>
                <span className="text-right">{payingGroup.currency_code}</span>
              </div>
              <div className="divide-y divide-slate-100">
                {payingGroup.reservations.map((child) => (
                  <label key={child.id} className="grid grid-cols-[1fr_9rem] items-center gap-3 px-3 py-2 text-sm">
                    <span className="min-w-0">
                      <span className="block font-medium text-slate-800">{child.confirmation_code}</span>
                      <span className="block text-xs text-slate-500">
                        {t("page.groups.balance")}: {formatMoney(child.balance_due, child.currency_code)}
                      </span>
                    </span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      max={child.balance_due ?? undefined}
                      disabled={child.company_billing_deferred || child.balance_due === null}
                      value={groupPaymentAllocations[child.id] ?? ""}
                      onChange={(event) => setGroupPaymentAllocations((current) => ({ ...current, [child.id]: event.target.value }))}
                      className="w-full rounded-lg border border-slate-200 px-2 py-2 text-right"
                      aria-label={`${t("page.groups.paymentAllocation")} ${child.confirmation_code}`}
                    />
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs">
                <span className="text-slate-600">{t("page.groups.paymentAllocated")}</span>
                <strong className={groupRequestedCents === groupAllocatedCents ? "text-emerald-700" : "text-rose-700"}>
                  {formatMoney(groupAllocatedCents / 100, payingGroup.currency_code)} / {formatMoney(groupPaymentTotalInput, payingGroup.currency_code)}
                </strong>
              </div>
            </div>

            {groupPaymentManualMethod && (
              <label className="mt-4 block text-sm font-semibold text-slate-700">
                {t("page.groups.paymentReference")}
                <input
                  value={groupPaymentReference}
                  onChange={(event) => setGroupPaymentReference(event.target.value)}
                  maxLength={120}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                  data-testid="group-payment-reference"
                />
              </label>
            )}
            <label className="mt-4 block text-sm font-semibold text-slate-700">
              {t("page.groups.paymentDescription")}
              <input
                value={groupPaymentDescription}
                onChange={(event) => setGroupPaymentDescription(event.target.value)}
                maxLength={300}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              />
            </label>
            <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
              {t("page.groups.paymentCashTotal")}: <strong>{formatMoney(groupPaymentGross, payingGroup.currency_code)}</strong>
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={groupPaymentMutation.isPending}
                onClick={() => { setPayingGroup(null); setGroupPaymentError(null); }}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
              >
                {t("page.common.close")}
              </button>
              <button
                type="button"
                onClick={() => void submitGroupPayment()}
                disabled={groupPaymentMutation.isPending || groupRequestedCents === 0 || groupRequestedCents !== groupAllocatedCents}
                className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
                data-testid="group-payment-submit"
              >
                {groupPaymentMutation.isPending ? t("common:saving") : t("page.groups.paymentSubmit")}
              </button>
            </div>
          </section>
        </div>
      )}

      {guestIdOpen && (
        <div className="fixed inset-0 z-30 flex animate-fade-in items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-2xl max-h-[90vh] animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.guestPanel.eyebrow")}</p>
                <h3 className="text-lg font-semibold text-slate-900">
                  {guestQuery.data ? `${guestQuery.data.first_name} ${guestQuery.data.last_name}` : t("page.guestPanel.nameFallback", { id: guestIdOpen })}
                </h3>
                <p className="text-xs text-slate-500">{t("page.guestPanel.subtitle")}</p>
              </div>
              <button onClick={closeGuest} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                {t("page.common.close")}
              </button>
            </div>

            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.guestPanel.contactTitle")}</p>
                <p className="mt-1">{guestQuery.data?.email ?? t("page.guestPanel.noEmail")}</p>
                <p>{guestQuery.data?.phone ?? t("page.guestPanel.noPhone")}</p>
                <p className="text-xs text-slate-500">
                  {t("page.guestPanel.documentLabel", { type: guestQuery.data?.document_type ?? "-", number: guestQuery.data?.document_number ?? "" })}
                </p>
                <p className="text-xs text-slate-500">
                  {guestQuery.data?.city ?? ""} {guestQuery.data?.country ?? ""}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.guestPanel.historyTitle")}</p>
                {guestHistory.length ? (
                  <ul className="mt-2 space-y-2">
                    {guestHistory.map((r) => (
                      <li key={r.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-2 py-1">
                        <span className="text-xs text-slate-600">
                          {r.check_in_date} → {r.check_out_date} · {statusConfig[r.status]?.label ?? r.status}
                        </span>
                        <button className="text-xs font-semibold text-brand-700 hover:underline" onClick={() => openDetails(r)} type="button">
                          {t("page.guestPanel.view")}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-600">{t("page.guestPanel.noHistory")}</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {receiptEmailAttempt && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-slate-950/50 px-4 py-6">
          <div
            ref={receiptEmailDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="payment-receipt-email-title"
            aria-describedby="payment-receipt-email-description"
            data-testid="payment-receipt-email-dialog"
            className="my-auto w-full max-w-lg rounded-xl border border-slate-200 bg-white p-5 shadow-2xl sm:p-6"
          >
            <h2
              ref={receiptEmailTitleRef}
              id="payment-receipt-email-title"
              tabIndex={-1}
              className="text-lg font-semibold text-slate-900"
            >
              {t("page.details.receipt.emailDialogTitle")}
            </h2>
            <p id="payment-receipt-email-description" className="mt-2 text-sm text-slate-600">
              {t("page.details.receipt.emailDialogDescription", { id: receiptEmailAttempt.transactionId })}
            </p>

            <div className="mt-4">
              <label htmlFor="payment-receipt-email-recipient" className="text-sm font-semibold text-slate-700">
                {t("page.details.receipt.recipientLabel")}
              </label>
              <input
                id="payment-receipt-email-recipient"
                type="email"
                readOnly
                aria-readonly="true"
                value={receiptEmailAttempt.recipientEmail}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800"
              />
            </div>

            {!receiptEmailAttempt.recipientEmail ? (
              <p className="mt-3 text-sm text-amber-800" role="alert">
                {t("page.details.receipt.missingEmail")}
              </p>
            ) : null}
            {receiptEmailAttempt.status === "sending" ? (
              <p className="mt-3 text-sm text-sky-800" role="status" aria-live="polite">
                {t("page.details.receipt.sending")}
              </p>
            ) : null}
            {receiptEmailAttempt.status === "sent" ? (
              <p className="mt-3 text-sm text-emerald-800" role="status" aria-live="polite">
                {t("page.details.receipt.sent")}
              </p>
            ) : null}
            {receiptEmailAttempt.status === "failed" && receiptEmailAttempt.recipientEmail ? (
              <p className="mt-3 text-sm text-rose-800" role="alert">
                {t("page.details.receipt.sendFailed")}
              </p>
            ) : null}
            {receiptEmailAttempt.status === "unknown" ? (
              <p className="mt-3 text-sm text-amber-900" role="alert" aria-live="assertive">
                {t("page.details.receipt.ambiguous")}
              </p>
            ) : null}

            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                ref={receiptEmailCloseRef}
                onClick={closeReceiptEmailDialog}
                disabled={receiptEmailAttempt.status === "sending"}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {receiptEmailAttempt.status === "sent" || receiptEmailAttempt.status === "unknown"
                  ? t("page.details.receipt.close")
                  : t("page.details.receipt.cancel")}
              </button>
              {(receiptEmailAttempt.status === "confirm" || receiptEmailAttempt.status === "failed") ? (
                <button
                  type="button"
                  data-testid="payment-receipt-email-confirm"
                  onClick={() => void sendReceiptEmail()}
                  disabled={!receiptEmailAttempt.recipientEmail}
                  className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {receiptEmailAttempt.status === "failed"
                    ? t("page.details.receipt.retrySend")
                    : t("page.details.receipt.confirmSend")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
