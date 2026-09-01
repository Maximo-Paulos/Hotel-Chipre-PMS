import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { type TFunction } from "i18next";

import {
  addReservationCharge,
  markReservationNoShow,
  moveReservationRoom,
  type Reservation,
  type ReservationChargePayload,
  type ReservationNoShowPayload,
  type ReservationPayload,
  type ReservationPendingAction,
  type ReservationRoomMovePayload,
  type ReservationRoomMoveResponse,
  type ReservationSource,
  type ReservationStatus,
  type ReservationUpdatePayload
} from "../../api/reservations";
import {
  listRoomMovementGroups,
  revertRoomMovementGroup,
  triggerAllocationRecalculation,
  type AllocationRunResponse,
  type RoomMovementGroup
} from "../../api/allocationRuns";
import { ApiError, hasValidSession } from "../../api/client";
import { getGuestProhibitedDetail, type RestrictionOverride } from "../../api/guestRestrictions";
import GuestQuickCreatePanel, {
  emptyQuickGuestForm,
  hasQuickGuestFormData,
  type QuickGuestFormValues
} from "../../components/GuestQuickCreatePanel";
import ManualOtaReservationModal from "../../components/ManualOtaReservationModal";
import { RestrictionOverrideModal } from "../../components/RestrictionOverrideModal";
import { useRestrictionOverridePrompt } from "../../hooks/useRestrictionOverridePrompt";
import { checkRoomAvailability, type RoomAvailabilityResponse } from "../../api/rooms";
import { type PaymentMethod } from "../../api/payments";
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
import { useReservationDrawer } from "../../hooks/useReservationDrawer";
import { type HotelConfig } from "../../api/config";
import { useRooms } from "../../hooks/useRooms";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";
import { formatMoney, normalizeCurrencyCode } from "../../utils/currency";
import { addDaysIso, formatLocalIsoDate, todayIso } from "../../utils/date";
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



type FormState = {
  guest_id: string;
  category_id: string;
  room_id: string;
  check_in_date: string;
  check_out_date: string;
  num_adults: string;
  num_children: string;
  notes: string;
  source: ReservationSource;
  status: ReservationStatus;
};

type PricingPaymentMethod = "base" | "cash" | "transfer" | "mercadopago" | "credit_card" | "paypal";

const paymentMethodValues: PaymentMethod[] = [
  "cash",
  "credit_card",
  "debit_card",
  "mercado_pago",
  "bank_transfer",
  "paypal"
];

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
  check_in_date: "",
  check_out_date: "",
  num_adults: "1",
  num_children: "0",
  notes: "",
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

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
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
  const { t } = useTranslation("reservations");
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | "all" | "">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reservation | null>(null);
  const [formValues, setFormValues] = useState<FormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [guestForm, setGuestForm] = useState<QuickGuestFormValues>(emptyQuickGuestForm);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmountInput, setPaymentAmountInput] = useState("");
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
  const [calendarRange, setCalendarRange] = useState<"week" | "month">("week");
  const [detailsReservationId, setDetailsReservationId] = useState<number | null>(null);
  const [roomMoveForm, setRoomMoveForm] = useState({
    to_room_id: "",
    reason_code: "",
    notes: "",
    price_action: "keep" as "keep" | "reprice"
  });
  const [chargeForm, setChargeForm] = useState({ description: "", amount: "" });
  const [noShowNotes, setNoShowNotes] = useState("");
  const [guestIdOpen, setGuestIdOpen] = useState<number | null>(null);
  const [allocationForm, setAllocationForm] = useState({
    apply: true,
    horizon_start: todayIso(),
    horizon_end: ""
  });
  const toastTimeout = useRef<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const { data: subscription } = useSubscriptionStatus();
  const writeBlocked = subscription?.can_write === false;
  const limitReached =
    subscription &&
    typeof subscription.room_limit === "number" &&
    subscription.room_limit > 0 &&
    subscription.rooms_in_use >= subscription.room_limit;
  const inactiveSubscription = subscription && subscription.status !== "active";
  const subscriptionBlocked = Boolean(subscription) && (inactiveSubscription || limitReached || writeBlocked);
  const subscriptionBlockReason = subscriptionBlocked
    ? writeBlocked
      ? t("page.subscription.readOnly")
      : inactiveSubscription
        ? t("page.subscription.inactive")
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
    limit: 200
  };

  const { data: reservations = [], isLoading, isFetching, error } = useReservations(filters);
  const pendingActionsQuery = usePendingReservationActions(12);
  const { roomsQuery } = useRooms();
  const { data: categoriesData = [] } = useCategories();
  const guestMutation = useGuestCreate();
  const guestQuery = useGuest(guestIdOpen ?? undefined);
  const paymentSummaryQuery = usePaymentSummary(editing?.id || undefined);
  const detailsReservationQuery = useReservation(detailsReservationId ?? undefined);
  const detailsReservation =
    detailsReservationQuery.data ?? reservations.find((item) => item.id === detailsReservationId) ?? null;
  const detailsRoom = useMemo(
    () => (roomsQuery.data ?? []).find((room) => room.id === detailsReservation?.room_id) ?? null,
    [detailsReservation?.room_id, roomsQuery.data]
  );
  const detailsSummaryQuery = usePaymentSummary(detailsReservationId || undefined);
  const detailsOperationsQuery = useReservationOperationsSummary(detailsReservationId || undefined);
  const paymentMutation = usePaymentMutation(editing?.id || undefined);
  const availabilityMutation = useGuardedMutation<RoomAvailabilityResponse, unknown, { category_id: number; check_in_date: string; check_out_date: string }>({
    mutationFn: (payload) => checkRoomAvailability(payload, session)
  });
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);
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
    onSuccess: async (result) => {
      await invalidateAllocationState();
      setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep" });
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

  const showToast = (type: "success" | "error" | "info", message: string) => {
    if (toastTimeout.current) {
      window.clearTimeout(toastTimeout.current);
    }
    setToast({ type, message });
    toastTimeout.current = window.setTimeout(() => setToast(null), 3800);
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

  const categoryNameById = useMemo(() => {
    const map = new Map<number, string>();
    categoriesData.forEach((cat) => map.set(cat.id, cat.name));
    return map;
  }, [categoriesData]);

  const selectedMoveRoom = useMemo(
    () => moveRoomOptions.find((room) => String(room.id) === roomMoveForm.to_room_id) ?? null,
    [moveRoomOptions, roomMoveForm.to_room_id]
  );
  const moveCrossesCategory = Boolean(
    selectedMoveRoom && detailsReservation && selectedMoveRoom.category_id !== detailsReservation.category_id
  );

  const categoryOptions = useMemo(
    () => categoriesData.map((cat) => ({ value: String(cat.id), label: `${cat.name} (#${cat.id})` })),
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

  const availableRooms = formValues.category_id ? roomsByCategory[formValues.category_id] ?? [] : roomsQuery.data ?? [];
  const selectedFormCategory = useMemo(
    () => categoriesData.find((category) => String(category.id) === formValues.category_id) ?? null,
    [categoriesData, formValues.category_id]
  );
  const quoteNights = diffNights(formValues.check_in_date, formValues.check_out_date);
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
          // Lets an operator find out a guest is restricted before filling
          // out the whole form -- the endpoint itself has no override, the
          // real override happens at reservation creation (see submitCreate).
          guest_id: Number.isFinite(quoteGuestId) && quoteGuestId > 0 ? quoteGuestId : null
        }
      : null
  );
  const reservationQuote = useMemo(() => {
    if (!quoteQuery.data || !selectedFormCategory || quoteNights <= 0) {
      return null;
    }
    return {
      nights: quoteQuery.data.nights,
      total: quoteQuery.data.total_amount,
      subtotal: quoteQuery.data.subtotal_amount,
      taxAmount: quoteQuery.data.tax_amount,
      feeAmount: quoteQuery.data.fee_amount,
      paymentMethod: quoteQuery.data.pricing_payment_method ?? null,
      defaultDeposit: quoteQuery.data.deposit_amount,
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
  const parsedDepositAmount = depositAmountInput.trim() === "" ? null : Number(depositAmountInput);
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

  const openCreate = () => {
    if (subscriptionBlocked) {
      setToast({ type: "error", message: subscriptionBlockReason || t("page.errors.blockedBySubscription") });
      return;
    }
    setEditing(null);
    setFormValues(defaultFormState());
    setFormError(null);
    setPricingPaymentMethod("base");
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setManualTargetCurrency("ARS");
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  // Quick-create shortcut (B1 global access) links here as /reservas?crear=1
  // instead of duplicating this ~600-line create form as a standalone
  // modal. Open it once on arrival and drop the flag so back/refresh
  // doesn't keep reopening it.
  const [searchParams, setSearchParams] = useSearchParams();
  const { openReservation } = useReservationDrawer();
  useEffect(() => {
    if (searchParams.get("crear") === "1") {
      openCreate();
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("crear");
          return next;
        },
        { replace: true }
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openEdit = (reservation: Reservation) => {
    setEditing(reservation);
    setFormValues({
      guest_id: String(reservation.guest_id),
      category_id: String(reservation.category_id),
      room_id: reservation.room_id ? String(reservation.room_id) : "",
      check_in_date: reservation.check_in_date,
      check_out_date: reservation.check_out_date,
      num_adults: String(reservation.num_adults),
      num_children: String(reservation.num_children),
      notes: reservation.notes || "",
      source: reservation.source,
      status: reservation.status
    });
    setFormError(null);
    setPricingPaymentMethod("base");
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setManualTargetCurrency("ARS");
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    if (
      collaborativeReservation.isSaving ||
      paymentMutation.isPending ||
      paymentProofMutations.submitMutation.isPending ||
      paymentProofMutations.approveMutation.isPending ||
      paymentProofMutations.rejectMutation.isPending ||
      paymentLinkCreate.isPending ||
      paymentLinkCancel.isPending
    ) {
      return;
    }
    setFormOpen(false);
    setEditing(null);
    setFormError(null);
    setDepositAmountInput("");
    setManualTotalAmountInput("");
    setLastCreatedReservation(null);
    setPaymentAmountInput("");
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
        notes: String(collaborativeReservation.draftValues.notes ?? "")
      }
    : formValues;

  const setReservationField = (
    field: "room_id" | "check_in_date" | "check_out_date" | "num_adults" | "num_children" | "notes",
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
          : value;
    collaborativeReservation.setField(field, normalizedValue);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
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
          document_number: guestForm.document_number.trim() || undefined,
          terms_accepted: true
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
    const manualTotalAmount =
      manualTotalAmountInput.trim() === "" ? null : Number(manualTotalAmountInput);
    if (!editing && manualTotalAmount !== null && (!Number.isFinite(manualTotalAmount) || manualTotalAmount < 0)) {
      setFormError(t("page.errors.invalidManualRate"));
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
      notes: currentFormValues.notes || undefined
    };

    if (editing) {
      // "status" y "category_id" no forman parte de ReservationUpdate en el
      // backend (ver app/schemas/reservation.py): se ignoran en silencio.
      // Los selectores correspondientes están deshabilitados en modo edición
      // para no sugerir un cambio que no persiste; los estados reales se
      // cambian con Check-in/Check-out/Cancelar/Marcar no-show.
      const { category_id, ...updatePayload } = commonPayload;
      void category_id;
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
      await submitUpdate(updatePayload);
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
        pricing_payment_method: pricingPaymentMethod === "base" ? null : pricingPaymentMethod,
        deposit_amount: parsedDepositAmount,
        ...(manualTotalAmount !== null
          ? { total_amount: manualTotalAmount, target_currency: manualTargetCurrency }
          : { quote_token: reservationQuote?.quoteToken })
      };
      const submitCreate = async (payload: ReservationPayload): Promise<void> => {
        try {
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
          const msg = err instanceof Error ? err.message : t("page.errors.createFailed");
          setFormError(msg);
          showToast("error", msg);
        }
      };
      await submitCreate(createPayload);
    }
  };

  const canCancel = canCancelReservation;
  const canCheckIn = canCheckInReservation;
  const isCheckInReady = (status: ReservationStatus) => ["fully_paid", "pre_check_in"].includes(status);
  const canCheckOut = canCheckOutReservation;
  const canNoShow = (status: ReservationStatus) => ["pending", "deposit_paid", "fully_paid"].includes(status);
  const canMoveRoom = (status: ReservationStatus) => !["cancelled", "checked_out", "no_show"].includes(status);
  const canAddCharge = (status: ReservationStatus) => !["cancelled", "checked_out", "no_show"].includes(status);

  const handleCancel = async (id: number) => {
    try {
      await cancelMutation.mutateAsync(id);
      showToast("success", t("page.messages.cancelled"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.cancelFailed"));
    }
  };

  const handleCheckIn = (reservation: Reservation) => {
    if (!isCheckInReady(reservation.status)) {
      const balance = reservation.balance_due ?? Math.max(0, reservation.total_amount - reservation.amount_paid);
      openEdit(reservation);
      showToast(
        "info",
        balance > 0.01
          ? t("page.messages.balancePendingCheckIn", { balance: formatMoney(balance, normalizeCurrencyCode(reservation.currency_code)) })
          : t("page.messages.paymentNotConfirmed")
      );
      return;
    }
    const submitCheckIn = async (restrictionOverride?: RestrictionOverride): Promise<void> => {
      try {
        await checkInMutation.mutateAsync(
          restrictionOverride ? { id: reservation.id, restriction_override: restrictionOverride } : reservation.id
        );
        showToast("success", t("page.messages.checkInDone"));
      } catch (err: unknown) {
        if (restrictionOverridePrompt.handleError(err, (override) => void submitCheckIn(override))) return;
        const msg = err instanceof Error ? err.message : t("page.errors.checkInFailed");
        // B3.3/B3.4: this quick action has no room to show the guest-data
        // capture form inline -- send the receptionist to the reservation
        // panel, which shows that form up front, instead of leaving them
        // stuck on a bare 400 with no way to fix it from here.
        if (msg.includes("missing required guest data")) {
          openReservation(reservation.id);
          showToast("info", t("page.messages.missingGuestDataForCheckIn"));
          return;
        }
        showToast("error", msg);
      }
    };
    void submitCheckIn();
  };

  const handleCheckOut = async (reservation: Reservation) => {
    // Cierra el loop cobro→estadía→egreso: si queda saldo, llevamos al operador a
    // cobrarlo (Pago total, que cae en la caja) en vez de fallar el check-out.
    // reservation.balance_due sólo cubre total_amount - amount_paid: no ve los
    // consumos cargados después del pago (BillingAdjustment), así que ese saldo
    // "operativo" recién lo conoce el backend al intentar el check-out.
    const balance = reservation.balance_due ?? 0;
    if (balance > 0.01) {
      openEdit(reservation);
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
        openEdit(reservation);
        showToast("info", `${message}${t("page.messages.checkOutBalanceHint")}`);
        return;
      }
      showToast("error", message);
    }
  };

  const handleCheckAvailability = async () => {
    if (!availabilityForm.category_id || !availabilityForm.check_in_date || !availabilityForm.check_out_date) {
      showToast("error", t("page.errors.availabilityFieldsRequired"));
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
      showToast("error", err instanceof Error ? err.message : t("page.errors.availabilityFailed"));
    }
  };

  const handleAllocationRun = async () => {
    if (subscriptionBlocked) {
      showToast("error", subscriptionBlockReason || t("page.errors.blockedBySubscriptionAllocation"));
      return;
    }
    if (
      allocationForm.horizon_start &&
      allocationForm.horizon_end &&
      new Date(allocationForm.horizon_end) < new Date(allocationForm.horizon_start)
    ) {
      showToast("error", t("page.errors.horizonInvalid"));
      return;
    }

    try {
      const run = await allocationRunMutation.mutateAsync(allocationForm);
      showToast("success", t("page.messages.allocationRecalculated", { created: run.assignments_created, moved: run.moved_count }));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.allocationFailed"));
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
      await revertMovementGroupMutation.mutateAsync(group.id);
      showToast("success", t("page.messages.groupReverted", { id: group.id }));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.revertGroupFailed"));
    }
  };

  const paymentSummary = paymentSummaryQuery.data;
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
  const cashSessionsQuery = useCashSessions();
  const hasOpenCashSession = useMemo(
    () => (cashSessionsQuery.data ?? []).some((s) => s.status === "open"),
    [cashSessionsQuery.data]
  );
  const surchargesQuery = usePaymentSurcharges();
  const activeSurcharge = useMemo(
    () => (surchargesQuery.data ?? []).find((s) => s.payment_method === paymentMethod && s.is_active) ?? null,
    [surchargesQuery.data, paymentMethod]
  );
  const editingGuest = useGuest(editing?.guest_id || undefined).data;
  const paymentLinksQuery = usePaymentLinks(editing?.id || undefined);
  const paymentLinkCreate = usePaymentLinkCreate(editing?.id || undefined);
  const paymentLinkCancel = usePaymentLinkCancel(editing?.id || undefined);
  const paymentProofsQuery = usePaymentProofs(editing?.id || undefined);
  const paymentProofMutations = usePaymentProofMutations(editing?.id || undefined);
  const detailsSummary = detailsSummaryQuery.data;
  const detailsOperations = detailsOperationsQuery.data;
  const detailsFinancialsLoading = detailsSummaryQuery.isLoading;
  const detailsGuest = useGuest(detailsReservation?.guest_id || undefined).data;
  const editingCurrencyCode = normalizeCurrencyCode(paymentSummary?.currency_code ?? editing?.currency_code);
  const canApprovePaymentProof = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  // Security fix: reads baseRole -- not the "Cambiar vista" preview role --
  // so this only hides the manual tarifa override for the real authenticated
  // role. The backend (POST /api/reservations) enforces this independently
  // via reservation:manual_rate; this is UX only, not the real gate.
  const canSetManualRate = ["owner", "co_owner"].includes(session.baseRole ?? "");
  const detailsCurrencyCode = normalizeCurrencyCode(
    detailsSummary?.currency_code ??
      detailsOperations?.financial_summary.currency_code ??
      detailsReservation?.currency_code
  );

  const handlePayDeposit = async () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const due = Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0);
    if (due <= 0.01) {
      showToast("info", t("page.messages.depositAlreadyCovered"));
      return;
    }
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "deposit",
        currency: editingCurrencyCode
      });
      showToast("success", t("page.messages.depositRegistered"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handlePayFull = async () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const due = paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0;
    if (due <= 0.01) {
      showToast("info", t("page.messages.noBalanceDue"));
      return;
    }
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "full_payment",
        currency: editingCurrencyCode
      });
      showToast("success", t("page.messages.fullPaymentDone"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handlePayPartial = async () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? t("page.messages.bankTransferHint")
          : t("page.messages.otherMethodHint")
      );
      return;
    }
    const amount = Number(paymentAmountInput);
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > balance + 0.01) {
      showToast("error", t("page.errors.invalidPartialAmount"));
      return;
    }
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "partial_payment",
        currency: editingCurrencyCode
      });
      setPaymentAmountInput("");
      showToast("success", t("page.messages.partialPaymentDone"));
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : t("page.errors.paymentFailed"));
    }
  };

  const handleRefund = async () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast("info", t("page.messages.refundCashOnly"));
      return;
    }
    const amount = Number(paymentAmountInput);
    const amountPaid = Number(paymentSummary.amount_paid ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > amountPaid + 0.01) {
      showToast("error", t("page.errors.invalidRefundAmount"));
      return;
    }
    if (!window.confirm(t("page.confirm.refund", { amount: formatMoney(amount, editingCurrencyCode) }))) return;
    try {
      await paymentMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "refund",
        currency: editingCurrencyCode,
        description: t("page.messages.refundManualDescription")
      });
      setPaymentAmountInput("");
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
      Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0) ||
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
    setDetailsReservationId(reservation.id);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openDetailsById = (reservationId: number) => {
    setDetailsReservationId(reservationId);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const closeDetails = () => {
    setDetailsReservationId(null);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "", price_action: "keep" });
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
    if (!detailsReservation || !roomMoveForm.to_room_id || !roomMoveForm.reason_code.trim()) {
      showToast("error", t("page.errors.roomMoveFieldsRequired"));
      return;
    }
    try {
      await roomMoveMutation.mutateAsync({
        reservationId: detailsReservation.id,
        payload: {
          to_room_id: Number(roomMoveForm.to_room_id),
          reason_code: roomMoveForm.reason_code.trim(),
          notes: roomMoveForm.notes.trim() || null,
          price_action: roomMoveForm.price_action
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
    if (detailsFinancialsLoading) {
      showToast("info", t("page.messages.waitForFinancialSummary"));
      return;
    }
    const summary = detailsSummary;
    const guest = detailsGuest;
    const win = window.open("", "_blank");
    if (!win) return;
    const html = `
      <html>
        <head>
          <title>${t("page.voucher.title", { code: detailsReservation.confirmation_code })}</title>
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
          <h1>${t("page.voucher.heading")}</h1>
          <p class="muted">${t("page.voucher.code", { code: detailsReservation.confirmation_code })}</p>
          <div class="grid">
            <div class="card">
              <p class="label">${t("page.voucher.reservationLabel")}</p>
              <p>${t("page.voucher.checkIn")} <strong>${detailsReservation.check_in_date}</strong></p>
              <p>${t("page.voucher.checkOut")} <strong>${detailsReservation.check_out_date}</strong></p>
              <p>${t("page.voucher.roomCat")} <strong>${detailsReservation.room_id ?? t("page.voucher.unassigned")} / ${detailsReservation.category_id}</strong></p>
              <p>${t("page.voucher.status")} <strong>${statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}</strong></p>
            </div>
            <div class="card">
              <p class="label">${t("page.voucher.guestLabel")}</p>
              <p>${guest ? `${guest.first_name} ${guest.last_name}` : t("page.voucher.guestIdFallback", { id: detailsReservation.guest_id })}</p>
              <p>${t("page.voucher.email")} ${guest?.email ?? "-"}</p>
              <p>${t("page.voucher.phone")} ${guest?.phone ?? "-"}</p>
            </div>
          </div>
          <div class="card" style="margin-top:12px;">
            <p class="label">${t("page.voucher.financeLabel")}</p>
            <p>${t("page.voucher.total")} <strong>${formatMoney(summary?.total_amount ?? detailsReservation.total_amount ?? 0, detailsCurrencyCode)}</strong></p>
            <p>${t("page.voucher.paid")} <strong>${formatMoney(summary?.amount_paid ?? detailsReservation.amount_paid ?? 0, detailsCurrencyCode)}</strong></p>
            <p>${t("page.voucher.balance")} <strong>${formatMoney(summary?.balance_due ?? detailsReservation.balance_due ?? 0, detailsCurrencyCode)}</strong></p>
          </div>
        </body>
      </html>`;
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
    win.close();
  };

  const guestHistory = useMemo(
    () => (guestIdOpen ? reservations.filter((r) => r.guest_id === guestIdOpen) : []),
    [guestIdOpen, reservations]
  );

  const reservationsByRoom = useMemo(() => {
    const map: Record<number, Reservation[]> = {};
    reservations.forEach((r) => {
      if (!r.room_id) return;
      if (!map[r.room_id]) map[r.room_id] = [];
      map[r.room_id].push(r);
    });
    return map;
  }, [reservations]);
  const recentMovementGroups = movementGroupsQuery.data ?? [];

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed right-6 top-20 z-40 flex w-80 items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
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
          <h1 className="text-2xl font-semibold text-slate-900">{t("page.header.title")}</h1>
          <p className="text-sm text-slate-600">{t("page.header.subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:opacity-60"
            onClick={openCreate}
            type="button"
            disabled={subscriptionBlocked}
          >
            {t("page.header.createButton")}
          </button>
          <button
            className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-semibold text-violet-700 hover:border-violet-300 hover:bg-violet-100 disabled:opacity-60"
            onClick={() => {
              if (subscriptionBlocked) {
                setToast({ type: "error", message: subscriptionBlockReason || t("page.errors.blockedBySubscription") });
                return;
              }
              setOtaFormOpen(true);
            }}
            type="button"
            disabled={subscriptionBlocked}
          >
            {t("page.header.otaButton")}
          </button>
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            {t("page.header.dashboardLink")}
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <ReservationStatCard label={t("page.stats.activeLabel")} value={totals.active} helper={t("page.stats.activeHelper")} />
        <ReservationStatCard label={t("page.stats.checkInsTodayLabel")} value={totals.checkInsToday} helper={today} />
        <ReservationStatCard label={t("page.stats.checkOutsTodayLabel")} value={totals.checkOutsToday} helper={today} />
        <ReservationStatCard label={t("page.stats.cancelledLabel")} value={totals.cancelled} helper={t("page.stats.cancelledHelper")} />
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
              {t("page.pendingActions.openCount", { count: pendingActions.length })}
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
            <p className="text-sm text-slate-500">{t("page.pendingActions.loading")}</p>
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

              return (
                <div key={action.action_key} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
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
                        <span>{t("page.pendingActions.statusPrefix", { status: action.reservation_status })}</span>
                        <span>{t("page.pendingActions.sourcePrefix", { source: action.source_provider_code || action.source })}</span>
                        {action.payment_collection_model ? (
                          <span>{t("page.pendingActions.collectionPrefix", { model: action.payment_collection_model })}</span>
                        ) : null}
                        {action.settlement_status ? (
                          <span>{t("page.pendingActions.settlementPrefix", { status: action.settlement_status })}</span>
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
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              {t("page.common.from")}
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              {t("page.common.to")}
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
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
            <button
              type="button"
              onClick={() => {
                setFromDate("");
                setToDate("");
                setStatusFilter("");
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
            {availabilityMutation.isPending && <span className="text-slate-600">{t("page.availability.querying")}</span>}
            {availabilityMutation.isError && <span className="text-rose-600">{t("page.availability.queryError")}</span>}
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
          <label className="text-xs font-semibold text-slate-600">
            {t("page.availability.checkIn")}
            <input
              type="date"
              value={availabilityForm.check_in_date}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, check_in_date: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-600">
            {t("page.availability.checkOut")}
            <input
              type="date"
              value={availabilityForm.check_out_date}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, check_out_date: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
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
            {allocationRunMutation.isPending ? <span>Recalculando...</span> : null}
            {movementGroupsQuery.isFetching ? <span>Actualizando grupos...</span> : null}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-5">
          <label className="text-xs font-semibold text-slate-600">
            {t("page.common.from")}
            <input
              type="date"
              value={allocationForm.horizon_start}
              onChange={(e) => setAllocationForm((prev) => ({ ...prev, horizon_start: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-600">
            {t("page.common.to")}
            <input
              type="date"
              value={allocationForm.horizon_end}
              onChange={(e) => setAllocationForm((prev) => ({ ...prev, horizon_end: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
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
                        <span className="text-xs text-slate-500">{formatDateTime(group.created_at)}</span>
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
                    <button
                      type="button"
                      onClick={() => handleRevertMovementGroup(group)}
                      disabled={group.is_reverted || revertMovementGroupMutation.isPending || subscriptionBlocked}
                      className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t("page.allocation.revert")}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.matrix.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.matrix.title")}</h2>
            <p className="text-xs text-slate-500">{t("page.matrix.hint")}</p>
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white px-2 py-1 text-left font-semibold text-slate-600">{t("page.matrix.roomColumn")}</th>
                {calendarDays.map((d) => (
                  <th key={d.iso} className="px-2 py-1 text-center font-semibold text-slate-500">
                    {d.label.split(" ").slice(0, 2).join(" ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(roomsQuery.data ?? []).map((room) => {
                const roomRes = reservationsByRoom[room.id] ?? [];
                return (
                  <tr key={room.id} className="border-t border-slate-100">
                    <td className="sticky left-0 z-10 bg-white px-2 py-1 text-left font-semibold text-slate-800">
                      {t("page.common.room", { number: room.room_number || room.id })}
                    </td>
                    {calendarDays.map((day) => {
                      const target = new Date(day.iso);
                      const res = roomRes.find(
                        (r) => new Date(r.check_in_date) <= target && new Date(r.check_out_date) > target
                      );
                      const isArrival = res?.check_in_date === day.iso;
                      const isDeparture = res?.check_out_date === day.iso;
                      return (
                        <td key={day.iso} className="px-1 py-1 text-center align-middle">
                          {res ? (
                            <div className="flex flex-col items-center gap-1">
                              <span className="h-1 w-full rounded-full bg-brand-300" />
                              <span className="text-[10px] text-slate-600">{res.confirmation_code}</span>
                              <div className="flex gap-1">
                                {isArrival && <span className="rounded-full bg-emerald-100 px-1 text-[10px] text-emerald-700">I</span>}
                                {isDeparture && <span className="rounded-full bg-sky-100 px-1 text-[10px] text-sky-700">O</span>}
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-300">·</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.list.eyebrow")}</p>
            <h2 className="text-lg font-semibold text-slate-900">{t("page.list.title")}</h2>
            {isFetching && <p className="text-xs text-slate-500">{t("page.list.updating")}</p>}
            {error && <p className="text-xs text-rose-700">{t("page.list.loadError", { message: (error as Error).message })}</p>}
          </div>
          <span className="text-xs text-slate-500">{t("page.list.total", { count: reservations.length })}</span>
        </div>
        {/* Dense table needs real column width -- desktop/tablet only. */}
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">{t("page.list.columns.code")}</th>
                <th className="px-4 py-2">{t("page.list.columns.guest")}</th>
                <th className="px-4 py-2">{t("page.list.columns.roomCat")}</th>
                <th className="px-4 py-2">{t("page.list.columns.checkIn")}</th>
                <th className="px-4 py-2">{t("page.list.columns.checkOut")}</th>
                <th className="px-4 py-2">{t("page.list.columns.status")}</th>
                <th className="px-4 py-2 text-right">{t("page.list.columns.amount")}</th>
                <th className="px-4 py-2 text-right">{t("page.list.columns.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {!isLoading && reservations.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-sm text-slate-500" colSpan={8}>
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
                      {t("page.list.roomCat", {
                        room: reservation.room_id ? t("page.common.room", { number: reservation.room_id }) : t("page.common.unassigned"),
                        category: reservation.category_id
                      })}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_in_date}</td>
                    <td className="px-4 py-2 text-slate-600">{reservation.check_out_date}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${cfg?.className ?? "bg-slate-100 text-slate-800"}`}>
                        {cfg?.label ?? reservation.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">
                      {formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-700">
                      <div className="flex flex-wrap justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300 disabled:opacity-50"
                          disabled={subscriptionBlocked}
                        >
                          {t("page.list.edit")}
                        </button>
                        <button
                          type="button"
                          onClick={() => openDetails(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300"
                        >
                          {t("page.list.file")}
                        </button>
                        <button
                          type="button"
                          disabled={!canCancel(reservation.status) || cancelMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCancel(reservation.id)}
                          className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {t("page.list.cancel")}
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCheckIn(reservation)}
                          title={
                            isCheckInReady(reservation.status)
                              ? t("page.list.checkInTooltipReady")
                              : t("page.list.checkInTooltipBlocked")
                          }
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
                    room: reservation.room_id ? t("page.common.room", { number: reservation.room_id }) : t("page.common.unassigned"),
                    category: reservation.category_id
                  })}
                </p>
                <p className="text-xs text-slate-600">
                  {reservation.check_in_date} → {reservation.check_out_date}
                </p>
                <p className="text-sm font-semibold text-slate-900">
                  {formatMoney(reservation.total_amount ?? 0, reservation.currency_code)}
                </p>
                <div className="flex flex-wrap gap-2 pt-1 text-xs text-slate-700">
                  <button
                    type="button"
                    onClick={() => openEdit(reservation)}
                    className="min-h-11 rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300 disabled:opacity-50"
                    disabled={subscriptionBlocked}
                  >
                    {t("page.list.edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => openDetails(reservation)}
                    className="min-h-11 rounded-lg border border-slate-200 px-3 py-2 hover:border-slate-300"
                  >
                    {t("page.list.file")}
                  </button>
                  <button
                    type="button"
                    disabled={!canCancel(reservation.status) || cancelMutation.isPending || subscriptionBlocked}
                    onClick={() => handleCancel(reservation.id)}
                    className="min-h-11 rounded-lg border border-rose-200 px-3 py-2 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("page.list.cancel")}
                  </button>
                  <button
                    type="button"
                    disabled={!canCheckIn(reservation.status) || checkInMutation.isPending || subscriptionBlocked}
                    onClick={() => handleCheckIn(reservation)}
                    title={
                      isCheckInReady(reservation.status)
                        ? t("page.list.checkInTooltipReady")
                        : t("page.list.checkInTooltipBlocked")
                    }
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
              <button onClick={closeForm} type="button" className="text-sm text-slate-500 hover:text-slate-800">
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
            {formError && <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</div>}

            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
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
                  onError={(msg) => showToast("error", msg)}
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
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.room")}
                  <select
                    value={collaborativeFormValues.room_id}
                    onChange={(e) => setReservationField("room_id", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("room_id")}
                    onBlur={() => editing && collaborativeReservation.blurField("room_id")}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  >
                    <option value="">{t("page.common.unassigned")}</option>
                    {availableRooms.map((room) => (
                      <option key={room.id} value={room.id}>
                        {t("page.form.roomOption", { number: room.room_number || room.id, category: room.category_id })}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.source")}
                  <select
                    value={formValues.source}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, source: e.target.value as ReservationSource }))}
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
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.checkIn")}
                  <input
                    type="date"
                    value={collaborativeFormValues.check_in_date}
                    onChange={(e) => setReservationField("check_in_date", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("check_in_date")}
                    onBlur={() => editing && collaborativeReservation.blurField("check_in_date")}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  {t("page.form.checkOut")}
                  <input
                    type="date"
                    value={collaborativeFormValues.check_out_date}
                    onChange={(e) => setReservationField("check_out_date", e.target.value)}
                    onFocus={() => editing && collaborativeReservation.focusField("check_out_date")}
                    onBlur={() => editing && collaborativeReservation.blurField("check_out_date")}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
              </div>

              {!editing && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
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

                  {canSetManualRate && (
                    <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50/60 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-violet-700">{t("page.form.manualRateTitle")}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("page.form.manualRateHint")}
                      </p>
                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <label className="text-xs font-semibold text-slate-600">
                          {t("page.form.manualAmount")}
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={manualTotalAmountInput}
                            onChange={(e) => setManualTotalAmountInput(e.target.value)}
                            placeholder={t("page.form.manualAmountPlaceholder")}
                            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                          />
                        </label>
                        <label className="text-xs font-semibold text-slate-600">
                          {t("page.form.currency")}
                          <select
                            value={manualTargetCurrency}
                            onChange={(e) => setManualTargetCurrency(e.target.value as "ARS" | "USD")}
                            disabled={manualTotalAmountInput.trim() === ""}
                            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                          >
                            <option value="ARS">ARS</option>
                            <option value="USD">USD</option>
                          </select>
                        </label>
                      </div>
                    </div>
                  )}

                  {manualTotalAmountInput.trim() !== "" ? (
                    <div className="mt-3 rounded-lg border border-violet-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      {t("page.form.manualTotalPreview", { amount: formatMoney(Number(manualTotalAmountInput) || 0, manualTargetCurrency) })}
                    </div>
                  ) : (
                    <>
                      <div className="mt-3 grid gap-2 sm:grid-cols-4">
                        <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteNights")}</p>
                          <p className="font-semibold">{reservationQuote?.nights ?? quoteNights}</p>
                        </div>
                        <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteTotalFinal")}</p>
                          <p className="font-semibold">
                            {quoteQuery.isFetching
                              ? t("page.form.quoteUpdating")
                              : quoteQuery.isError
                                ? t("page.form.quoteUnavailable")
                              : formatMoney(reservationQuote?.total ?? 0, reservationQuote?.currencyCode ?? "ARS")}
                          </p>
                        </div>
                        <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                          <p className="text-xs text-slate-500">{t("page.form.quoteDeposit")}</p>
                          <p className="font-semibold">
                            {quoteQuery.isError
                              ? t("page.form.quoteDepositUnavailable")
                              : depositPreview !== null
                              ? formatMoney(depositPreview, reservationQuote?.currencyCode ?? "ARS")
                              : t("page.form.quoteDepositPending")}
                          </p>
                        </div>
                        <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
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
                        <div className="mt-3 overflow-x-auto rounded-lg border border-blue-100 bg-white/70">
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
                                <tr key={row.date} className="border-t border-blue-100">
                                  <td className="px-3 py-2 text-slate-700">{row.date}</td>
                                  <td className="px-3 py-2 text-slate-500">{row.source}</td>
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
                            <p className="border-t border-blue-100 px-3 py-2 text-xs text-slate-500">
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
                </div>
              )}

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
                    className="mt-2 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
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
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
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
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
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
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  rows={3}
                />
              </label>

              {editing && (
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

                  <div className="mt-3 grid gap-2 sm:grid-cols-6 sm:items-end">
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                      {t("page.form.paymentMethod")}
                      <select
                        value={paymentMethod}
                        onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
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
                      {t("page.form.amountToCharge")}
                      <input
                        aria-label={t("page.form.amountToChargeAria")}
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={paymentAmountInput}
                        onChange={(event) => setPaymentAmountInput(event.target.value)}
                        placeholder={t("page.form.amountToChargePlaceholder")}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={handlePayPartial}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-sky-200 bg-sky-100 px-3 py-2 text-sm font-semibold text-sky-800 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Cobro parcial
                    </button>
                    <button
                      type="button"
                      onClick={handlePayDeposit}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-amber-200 bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {t("page.form.registerDeposit")}
                    </button>
                    <button
                      type="button"
                      onClick={handlePayFull}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-emerald-200 bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-800 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {t("page.form.fullPayment")}
                    </button>
                    <button
                      type="button"
                      onClick={handleRefund}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-violet-200 bg-violet-100 px-3 py-2 text-sm font-semibold text-violet-800 hover:border-violet-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {t("page.form.registerRefund")}
                    </button>
                    {paymentMutation.isError && (
                      <p className="text-xs text-rose-600">{t("page.form.paymentError")}</p>
                    )}
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
                        disabled={paymentProofMutations.submitMutation.isPending || paymentSummaryQuery.isLoading}
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
                              {tx.fee_amount && tx.fee_amount > 0 ? (
                                <span className="text-amber-700">{t("page.form.feeSuffix", { amount: formatMoney(tx.fee_amount, tx.currency) })}</span>
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

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={closeForm}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
                >
                  {t("page.form.cancel")}
                </button>
                <button
                  type="submit"
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  disabled={
                    createMutation.isPending ||
                    updateMutation.isPending ||
                    collaborativeReservation.isSaving ||
                    subscriptionBlocked ||
                    Boolean(lastCreatedReservation) ||
                    (!editing &&
                      manualTotalAmountInput.trim() === "" &&
                      (quoteQuery.isFetching || !reservationQuote?.quoteToken))
                  }
                >
                  {editing ? t("page.form.saveChanges") : quoteQuery.isFetching && manualTotalAmountInput.trim() === "" ? t("page.form.updating") : t("page.form.create")}
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
          isPending={createMutation.isPending || updateMutation.isPending || checkInMutation.isPending}
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
                    category: detailsReservation.category_id,
                    room: detailsRoom
                      ? t("page.common.room", { number: detailsRoom.room_number })
                      : detailsReservation.room_id
                        ? t("page.common.roomHash", { id: detailsReservation.room_id })
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

            <div className="mt-4 grid gap-4 md:grid-cols-2">
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
                    <span className="font-semibold">{t("page.details.timelineStatus")}</span> {statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}
                  </li>
                  {detailsSummary?.transactions?.length ? (
                    <li>
                      <span className="font-semibold">{t("page.details.timelineLastPayment")}</span>{" "}
                      {detailsSummary.transactions[detailsSummary.transactions.length - 1].created_at}
                    </li>
                  ) : null}
                </ul>
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("page.details.financeTitle")}</p>
                {detailsFinancialsLoading ? (
                  <p className="rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-sm text-slate-600">
                    {t("page.details.financeLoading")}
                  </p>
                ) : detailsSummary ? (
                  <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeTotal")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.total_amount, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financePaid")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.amount_paid, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeDeposit")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.deposit_required, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("page.details.financeBalance")}</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.balance_due, detailsCurrencyCode)}</p>
                    </div>
                  </div>
                ) : (
                  <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {t("page.details.financeLoadError")}
                  </p>
                )}
                {detailsOperations?.financial_summary ? (
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
                        <p className="font-semibold">{detailsOperations.payment_collection_model}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">{t("page.details.financeSettlement")}</p>
                        <p className="font-semibold">{detailsOperations.settlement_status}</p>
                      </div>
                    </div>
                    {detailsOperations.financial_summary.recommended_next_action ? (
                      <p className="mt-2 text-xs text-amber-700">
                        {t("page.details.financeNextAction", { action: detailsOperations.financial_summary.recommended_next_action })}
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
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                  <div>
                    <p className="text-xs text-slate-500">{t("page.details.operationAllocation")}</p>
                    <p className="font-semibold">{detailsOperations?.allocation_status ?? detailsReservation.allocation_status ?? "-"}</p>
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
                        <div key={action.action_key} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
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
                    disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending || moveRoomOptions.length === 0}
                    className="w-full rounded-lg border border-brand-200 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {roomMoveMutation.isPending ? t("page.details.movingRoom") : t("page.details.moveRoom")}
                  </button>
                  {moveRoomOptions.length === 0 && canMoveRoom(detailsReservation.status) ? (
                    <p className="text-xs text-amber-700">{t("page.details.noOtherRoomAvailable")}</p>
                  ) : null}
                </form>

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
                    className="w-full rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-800 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-60"
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
                {detailsOperations?.financial_summary ? (
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
                <p className="mt-2 text-xs text-slate-500">{t("page.details.chargesBlockedHint")}</p>
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
                        <p className="font-semibold text-slate-900">{adjustment.kind}</p>
                        <p className="text-xs text-slate-600">
                          {t("page.details.adjustmentStatusLine", {
                            status: adjustment.status,
                            external: adjustment.external_resolution_status ?? "-"
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
                      <li key={tx.id} className="flex items-center justify-between py-2">
                        <div>
                          <p className="font-semibold">{formatMoney(tx.amount, tx.currency)}</p>
                          <p className="text-xs text-slate-500">
                            {t("page.details.transactionLine", { type: tx.type, method: tx.method, status: tx.status })}
                          </p>
                        </div>
                        <span className="text-xs text-slate-500">{tx.created_at}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600">{t("page.details.noTransactions")}</p>
                )}
              </div>
            </div>
          </div>
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
    </div>
  );
}
