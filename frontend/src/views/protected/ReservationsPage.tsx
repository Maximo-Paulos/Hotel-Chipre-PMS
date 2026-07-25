import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addReservationCharge,
  markReservationNoShow,
  moveReservationRoom,
  type Reservation,
  type ReservationChargePayload,
  type ReservationNoShowPayload,
  type ReservationPendingAction,
  type ReservationRoomMovePayload,
  type ReservationSource,
  type ReservationStatus
} from "../../api/reservations";
import {
  listRoomMovementGroups,
  revertRoomMovementGroup,
  triggerAllocationRecalculation,
  type AllocationRunResponse,
  type RoomMovementGroup
} from "../../api/allocationRuns";
import { ApiError, hasValidSession } from "../../api/client";
import { type Guest, type GuestPayload } from "../../api/guests";
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
import { usePaymentLinks, usePaymentLinkCreate } from "../../hooks/usePaymentLinks";
import { usePaymentProofMutations, usePaymentProofs } from "../../hooks/usePaymentProofs";
import { fetchPaymentProofImage } from "../../api/paymentProofs";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { type HotelConfig } from "../../api/config";
import { useRooms } from "../../hooks/useRooms";
import { useSubscriptionStatus } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";
import { formatMoney, normalizeCurrencyCode } from "../../utils/currency";
import {
  canCancelReservation,
  canCheckInReservation,
  canCheckOutReservation,
  reservationStatusConfig
} from "../../utils/reservationStatus";
import ReservationStatCard from "../../components/StatCard";

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

const paymentMethodOptions: { value: PaymentMethod; label: string }[] = [
  { value: "cash", label: "Efectivo" },
  { value: "credit_card", label: "Crédito" },
  { value: "debit_card", label: "Débito" },
  { value: "mercado_pago", label: "MercadoPago" },
  { value: "bank_transfer", label: "Transferencia" },
  { value: "paypal", label: "PayPal" }
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
    ? paymentMethodOptions.filter((opt) => config[paymentMethodEnabledFlag[opt.value]] === true)
    : paymentMethodOptions;

const pricingPaymentMethodOptions: { value: PricingPaymentMethod; label: string }[] = [
  { value: "base", label: "Tarifa base" },
  { value: "cash", label: "Efectivo" },
  { value: "transfer", label: "Transferencia" },
  { value: "mercadopago", label: "Mercado Pago" },
  { value: "credit_card", label: "Tarjeta de credito" },
  { value: "paypal", label: "PayPal" }
];

const statusConfig = reservationStatusConfig;

const priorityConfig: Record<ReservationPendingAction["priority"], { label: string; className: string }> = {
  critical: { label: "Crítica", className: "bg-rose-100 text-rose-800" },
  high: { label: "Alta", className: "bg-amber-100 text-amber-800" },
  medium: { label: "Media", className: "bg-sky-100 text-sky-800" },
  low: { label: "Baja", className: "bg-slate-100 text-slate-700" }
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

type QuickGuestForm = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  document_type: NonNullable<GuestPayload["document_type"]>;
  document_number: string;
};

const emptyQuickGuest = (): QuickGuestForm => ({
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  document_type: "DNI",
  document_number: ""
});

const todayIso = () => new Date().toISOString().slice(0, 10);
const reservationGuestLabel = (reservation: {
  guest?: { first_name: string; last_name: string } | null;
  guest_id: number;
}) => (reservation.guest ? `${reservation.guest.first_name} ${reservation.guest.last_name}`.trim() : `Huesped #${reservation.guest_id}`);

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

const readFileAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("No se pudo leer el comprobante."));
    reader.readAsDataURL(file);
  });

export function ReservationsPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | "all" | "">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Reservation | null>(null);
  const [formValues, setFormValues] = useState<FormState>(defaultFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [guestForm, setGuestForm] = useState(emptyQuickGuest);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmountInput, setPaymentAmountInput] = useState("");
  const [paymentProofFile, setPaymentProofFile] = useState<File | null>(null);
  const [paymentProofPreview, setPaymentProofPreview] = useState<{ proofId: number; url: string } | null>(null);
  const [viewingPaymentProofId, setViewingPaymentProofId] = useState<number | null>(null);
  const [rejectingPaymentProofId, setRejectingPaymentProofId] = useState<number | null>(null);
  const [paymentProofRejectReason, setPaymentProofRejectReason] = useState("");
  const [pricingPaymentMethod, setPricingPaymentMethod] = useState<PricingPaymentMethod>("base");
  const [depositAmountInput, setDepositAmountInput] = useState("");
  const [availabilityForm, setAvailabilityForm] = useState<{
    category_id: string;
    check_in_date: string;
    check_out_date: string;
  }>({
    category_id: "",
    check_in_date: todayIso(),
    check_out_date: (() => {
      const d = new Date();
      d.setDate(d.getDate() + 1);
      return d.toISOString().slice(0, 10);
    })()
  });
  const [calendarRange, setCalendarRange] = useState<"week" | "month">("week");
  const [detailsReservationId, setDetailsReservationId] = useState<number | null>(null);
  const [roomMoveForm, setRoomMoveForm] = useState({ to_room_id: "", reason_code: "", notes: "" });
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
      ? "Suscripción en modo solo lectura: reactivá el plan para habilitar acciones de reserva."
      : inactiveSubscription
        ? "Suscripción inactiva: reactivá tu plan para operar reservas."
        : `Alcanzaste tu cupo de habitaciones (${subscription?.rooms_in_use}/${subscription?.room_limit}).`
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
  const availabilityMutation = useMutation<RoomAvailabilityResponse, unknown, { category_id: number; check_in_date: string; check_out_date: string }>({
    mutationFn: (payload) => checkRoomAvailability(payload, session)
  });
  const { createMutation, updateMutation, cancelMutation, checkInMutation, checkOutMutation } = useReservationMutations(filters);
  const { resolveExternalMutation, clearManualReviewMutation } = useReservationActionMutations(filters);
  const movementGroupsQuery = useQuery<RoomMovementGroup[]>({
    queryKey: ["room-movement-groups", session.hotelId, 6],
    queryFn: () => listRoomMovementGroups(6, session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });

  const invalidateAllocationState = () => {
    queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["reservation", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["reservation-operations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["reservation-pending-actions", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["room-movement-groups", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["payment-summary", session.hotelId] });
  };

  const roomMoveMutation = useMutation<Reservation, unknown, { reservationId: number; payload: ReservationRoomMovePayload }>({
    mutationFn: ({ reservationId, payload }) => moveReservationRoom(reservationId, payload, session),
    onSuccess: () => {
      invalidateAllocationState();
      setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "" });
      showToast("success", "Habitación cambiada.");
    }
  });

  const noShowMutation = useMutation<Reservation, unknown, { reservationId: number; payload: ReservationNoShowPayload }>({
    mutationFn: ({ reservationId, payload }) => markReservationNoShow(reservationId, payload, session),
    onSuccess: () => {
      invalidateAllocationState();
      setNoShowNotes("");
      showToast("success", "No-show registrado.");
    }
  });

  const chargeMutation = useMutation<unknown, unknown, { reservationId: number; payload: ReservationChargePayload }>({
    mutationFn: ({ reservationId, payload }) => addReservationCharge(reservationId, payload, session),
    onSuccess: () => {
      invalidateAllocationState();
      setChargeForm({ description: "", amount: "" });
      showToast("success", "Consumo cargado a la reserva.");
    },
    onError: (err: unknown) => {
      showToast("error", err instanceof Error ? err.message : "No se pudo cargar el consumo.");
    }
  });

  const allocationRunMutation = useMutation<AllocationRunResponse, unknown, typeof allocationForm>({
    mutationFn: (payload) =>
      triggerAllocationRecalculation(
        {
          apply: payload.apply,
          horizon_start: payload.horizon_start || null,
          horizon_end: payload.horizon_end || null
        },
        session
      ),
    onSuccess: invalidateAllocationState
  });

  const revertMovementGroupMutation = useMutation<RoomMovementGroup, unknown, number>({
    mutationFn: (groupId) => revertRoomMovementGroup(groupId, session),
    onSuccess: invalidateAllocationState
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
    return (roomsQuery.data ?? []).filter(
      (room) =>
        room.is_active &&
        room.category_id === detailsReservation.category_id &&
        room.id !== detailsReservation.room_id &&
        room.status !== "maintenance" &&
        room.status !== "blocked"
    );
  }, [detailsReservation, roomsQuery.data]);

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
  const quoteQuery = useReservationQuote(
    quoteCategoryId && formValues.check_in_date && formValues.check_out_date
      ? {
          category_id: quoteCategoryId,
          check_in_date: formValues.check_in_date,
          check_out_date: formValues.check_out_date,
          pricing_payment_method: pricingPaymentMethod === "base" ? null : pricingPaymentMethod,
          occupancy: (Number(formValues.num_adults) || 1) + (Number(formValues.num_children) || 0)
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
      defaultDeposit: quoteQuery.data.deposit_amount,
      currencyCode: quoteQuery.data.currency_code,
      quoteToken: quoteQuery.data.quote_token,
      rows: quoteQuery.data.breakdown.map((row) => ({
        date: row.date,
        amount: row.price,
        source: row.source ?? "backend_quote"
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
      const iso = date.toISOString().slice(0, 10);
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
      setToast({ type: "error", message: subscriptionBlockReason || "Acción bloqueada por suscripción." });
      return;
    }
    setEditing(null);
    setFormValues(defaultFormState());
    setFormError(null);
    setPricingPaymentMethod("base");
    setDepositAmountInput("");
    setPaymentAmountInput("");
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  // "Reserva rápida" (B1 global access) links here as /reservas?crear=1
  // instead of duplicating this ~600-line create form as a standalone
  // modal. Open it once on arrival and drop the flag so back/refresh
  // doesn't keep reopening it.
  const [searchParams, setSearchParams] = useSearchParams();
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
    setPaymentAmountInput("");
    setPaymentProofFile(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditing(null);
    setFormError(null);
    setDepositAmountInput("");
    setPaymentAmountInput("");
    setPaymentProofFile(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (subscriptionBlocked) {
      setFormError(subscriptionBlockReason || "Suscripción inactiva.");
      return;
    }

    const categoryIdNum = Number(formValues.category_id);
    let guestIdNum = Number(formValues.guest_id);
    if (!editing && (!guestIdNum || Number.isNaN(guestIdNum))) {
      const hasGuestData =
        guestForm.first_name.trim() !== "" ||
        guestForm.last_name.trim() !== "" ||
        guestForm.email.trim() !== "" ||
        guestForm.phone.trim() !== "" ||
        guestForm.document_number.trim() !== "";

      if (!hasGuestData) {
        setFormError("Ingresá el ID del huésped o completá los datos para crearlo automáticamente.");
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
        setGuestForm(emptyQuickGuest());
        showToast("success", "Huésped creado y asignado automáticamente");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "No se pudo crear el huésped";
        setFormError(msg);
        showToast("error", msg);
        return;
      }
    }    if (!categoryIdNum || Number.isNaN(categoryIdNum)) {
      setFormError("Seleccioná una Categoría (ID numérico).");
      return;
    }
    if (!formValues.check_in_date || !formValues.check_out_date) {
      setFormError("Elegí fechas de ingreso y salida.");
      return;
    }

    const baseDatesValid = new Date(formValues.check_out_date) > new Date(formValues.check_in_date);
    if (!baseDatesValid) {
      setFormError("La fecha de salida debe ser posterior al ingreso.");
      return;
    }
    if (!editing && parsedDepositAmount !== null) {
      if (!Number.isFinite(parsedDepositAmount) || parsedDepositAmount < 0) {
        setFormError("Ingresá una seña válida o dejá el campo vacío.");
        return;
      }
      if (reservationQuote && parsedDepositAmount > reservationQuote.total) {
        setFormError("La seña no puede ser mayor al total final de la reserva.");
        return;
      }
    }

    const commonPayload = {
      category_id: categoryIdNum,
      room_id: formValues.room_id ? Number(formValues.room_id) : null,
      check_in_date: formValues.check_in_date,
      check_out_date: formValues.check_out_date,
      num_adults: Number(formValues.num_adults) || 1,
      num_children: Number(formValues.num_children) || 0,
      notes: formValues.notes || undefined
    };

    if (editing) {
      // "status" y "category_id" no forman parte de ReservationUpdate en el
      // backend (ver app/schemas/reservation.py): se ignoran en silencio.
      // Los selectores correspondientes están deshabilitados en modo edición
      // para no sugerir un cambio que no persiste; los estados reales se
      // cambian con Check-in/Check-out/Cancelar/Marcar no-show.
      const { category_id, ...updatePayload } = commonPayload;
      void category_id;
      updateMutation.mutate(
        { id: editing.id, payload: updatePayload },
        {
          onSuccess: () => {
            showToast("success", "Reserva actualizada");
            closeForm();
          },
          onError: (err: unknown) => {
            const msg = err instanceof Error ? err.message : "No se pudo guardar la reserva";
            setFormError(msg);
            showToast("error", msg);
          }
        }
      );
    } else {
      if (!reservationQuote?.quoteToken || quoteQuery.isFetching) {
        setFormError("Esperá a que se actualice la cotización vigente antes de crear la reserva.");
        return;
      }
      const createPayload = {
        ...commonPayload,
        guest_id: guestIdNum,
        source: formValues.source,
        pricing_payment_method: pricingPaymentMethod === "base" ? null : pricingPaymentMethod,
        deposit_amount: parsedDepositAmount,
        quote_token: reservationQuote.quoteToken
      };
      createMutation.mutate(createPayload, {
        onSuccess: () => {
          showToast("success", "Reserva creada");
          closeForm();
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : "No se pudo crear la reserva";
          setFormError(msg);
          showToast("error", msg);
        }
      });
    }
  };

  const canCancel = canCancelReservation;
  const canCheckIn = canCheckInReservation;
  const isCheckInReady = (status: ReservationStatus) => ["fully_paid", "pre_check_in"].includes(status);
  const canCheckOut = canCheckOutReservation;
  const canNoShow = (status: ReservationStatus) => ["pending", "deposit_paid", "fully_paid"].includes(status);
  const canMoveRoom = (status: ReservationStatus) => !["cancelled", "checked_out", "no_show"].includes(status);
  const canAddCharge = (status: ReservationStatus) => !["cancelled", "checked_out", "no_show"].includes(status);

  const handleCancel = (id: number) =>
    cancelMutation.mutate(id, {
      onSuccess: () => showToast("success", "Reserva cancelada"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo cancelar")
    });

  const handleCheckIn = (reservation: Reservation) => {
    if (!isCheckInReady(reservation.status)) {
      const balance = reservation.balance_due ?? Math.max(0, reservation.total_amount - reservation.amount_paid);
      openEdit(reservation);
      showToast(
        "info",
        balance > 0.01
          ? `Saldo pendiente de ${formatMoney(balance, normalizeCurrencyCode(reservation.currency_code))}. Cobralo con "Pago total" (queda en la caja) y luego hacé el check-in.`
          : "El pago todavía no se confirmó. Revisá los pagos antes de hacer el check-in."
      );
      return;
    }
    checkInMutation.mutate(reservation.id, {
      onSuccess: () => showToast("success", "Check-in registrado"),
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo hacer check-in")
    });
  };

  const handleCheckOut = (reservation: Reservation) => {
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
        `Saldo pendiente de ${formatMoney(balance, normalizeCurrencyCode(reservation.currency_code))}. Cobralo con "Pago total" (queda en la caja) y luego hacé el check-out.`
      );
      return;
    }
    checkOutMutation.mutate(reservation.id, {
      onSuccess: () => showToast("success", "Check-out registrado"),
      onError: (err: unknown) => {
        const message = err instanceof Error ? err.message : "No se pudo hacer check-out";
        if (/saldo pendiente/i.test(message)) {
          openEdit(reservation);
          showToast("info", `${message} Cobralo con "Pago total" (queda en la caja) y luego hacé el check-out.`);
          return;
        }
        showToast("error", message);
      }
    });
  };

  const handleCheckAvailability = () => {
    if (!availabilityForm.category_id || !availabilityForm.check_in_date || !availabilityForm.check_out_date) {
      showToast("error", "Completá Categoría y fechas para consultar disponibilidad.");
      return;
    }
    const payload = {
      category_id: Number(availabilityForm.category_id),
      check_in_date: availabilityForm.check_in_date,
      check_out_date: availabilityForm.check_out_date
    };
    availabilityMutation.mutate(payload, {
      onSuccess: (data) => {
        if (data.status === "ok") {
          showToast("success", `Disponibles: ${data.count} habitaciones`);
        } else {
          showToast("info", data.message);
        }
      },
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo consultar disponibilidad")
    });
  };

  const handleAllocationRun = () => {
    if (subscriptionBlocked) {
      showToast("error", subscriptionBlockReason || "Accion bloqueada por suscripcion.");
      return;
    }
    if (
      allocationForm.horizon_start &&
      allocationForm.horizon_end &&
      new Date(allocationForm.horizon_end) < new Date(allocationForm.horizon_start)
    ) {
      showToast("error", "El horizonte hasta no puede ser anterior al desde.");
      return;
    }

    allocationRunMutation.mutate(allocationForm, {
      onSuccess: (run) => {
        showToast(
          "success",
          `Asignacion recalculada: ${run.assignments_created} asignadas, ${run.moved_count} movimientos.`
        );
      },
      onError: (err: unknown) =>
        showToast("error", err instanceof Error ? err.message : "No se pudo recalcular la asignacion")
    });
  };

  const handleRevertMovementGroup = (group: RoomMovementGroup) => {
    const moves = group.move_events.length;
    const confirmed = window.confirm(
      `Revertir el grupo #${group.id}? Se intentaran deshacer ${moves} movimiento${moves === 1 ? "" : "s"} de habitacion.`
    );
    if (!confirmed) return;

    revertMovementGroupMutation.mutate(group.id, {
      onSuccess: () => showToast("success", `Grupo #${group.id} revertido`),
      onError: (err: unknown) =>
        showToast("error", err instanceof Error ? err.message : "No se pudo revertir el grupo")
    });
  };

  const handleCreateGuest = () => {
    guestMutation.mutate(
      {
        ...guestForm,
        document_number: guestForm.document_number.trim() || undefined,
        terms_accepted: true
      },
      {
      onSuccess: (guest: Guest) => {
        setFormValues((prev) => ({ ...prev, guest_id: String(guest.id) }));
        setGuestForm(emptyQuickGuest());
        showToast("success", "Huésped creado y asignado");
      },
      onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo crear el Huésped")
      }
    );
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
    if (!availablePaymentMethods.some((opt) => opt.value === paymentMethod)) {
      setPaymentMethod(availablePaymentMethods[0].value);
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
  const paymentProofsQuery = usePaymentProofs(editing?.id || undefined);
  const paymentProofMutations = usePaymentProofMutations(editing?.id || undefined);
  const detailsSummary = detailsSummaryQuery.data;
  const detailsOperations = detailsOperationsQuery.data;
  const detailsFinancialsLoading = detailsSummaryQuery.isLoading;
  const detailsGuest = useGuest(detailsReservation?.guest_id || undefined).data;
  const editingCurrencyCode = normalizeCurrencyCode(paymentSummary?.currency_code ?? editing?.currency_code);
  const canApprovePaymentProof = ["owner", "co_owner", "manager"].includes(session.baseRole ?? "");
  const detailsCurrencyCode = normalizeCurrencyCode(
    detailsSummary?.currency_code ??
      detailsOperations?.financial_summary.currency_code ??
      detailsReservation?.currency_code
  );

  const handlePayDeposit = () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? "Para transferencia cargá el comprobante y esperá la aprobación."
          : "Para este medio generá un link o confirmá el pago desde su integración."
      );
      return;
    }
    const due = Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0);
    if (due <= 0.01) {
      showToast("info", "La Seña ya está cubierta.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "deposit",
        currency: editingCurrencyCode
      },
      {
        onSuccess: () => showToast("success", "Se registró la Seña"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const handlePayFull = () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? "Para transferencia cargá el comprobante y esperá la aprobación."
          : "Para este medio generá un link o confirmá el pago desde su integración."
      );
      return;
    }
    const due = paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0;
    if (due <= 0.01) {
      showToast("info", "No hay saldo pendiente.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(due.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "full_payment",
        currency: editingCurrencyCode
      },
      {
        onSuccess: () => showToast("success", "Pago completo registrado"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const handlePayPartial = () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast(
        "info",
        paymentMethod === "bank_transfer"
          ? "Para transferencia cargá el comprobante y esperá la aprobación."
          : "Para este medio generá un link o confirmá el pago desde su integración."
      );
      return;
    }
    const amount = Number(paymentAmountInput);
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > balance + 0.01) {
      showToast("error", "Ingresá un importe positivo que no supere el saldo pendiente.");
      return;
    }
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "partial_payment",
        currency: editingCurrencyCode
      },
      {
        onSuccess: () => {
          setPaymentAmountInput("");
          showToast("success", "Cobro parcial registrado");
        },
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el pago")
      }
    );
  };

  const handleRefund = () => {
    if (!editing || !paymentSummary) return;
    if (paymentMethod !== "cash") {
      showToast("info", "La devolución manual se registra en efectivo desde la caja abierta.");
      return;
    }
    const amount = Number(paymentAmountInput);
    const amountPaid = Number(paymentSummary.amount_paid ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > amountPaid + 0.01) {
      showToast("error", "Ingresá un importe positivo que no supere el total pagado.");
      return;
    }
    if (!window.confirm(`¿Confirmar devolución en efectivo de ${formatMoney(amount, editingCurrencyCode)}?`)) return;
    paymentMutation.mutate(
      {
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        payment_method: paymentMethod,
        transaction_type: "refund",
        currency: editingCurrencyCode,
        description: "Devolución manual en efectivo"
      },
      {
        onSuccess: () => {
          setPaymentAmountInput("");
          showToast("success", "Devolución registrada");
        },
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar la devolución")
      }
    );
  };

  const handleSubmitTransferProof = async () => {
    if (!editing || !paymentSummary) return;
    if (!paymentProofFile) {
      showToast("error", "Adjuntá una imagen del comprobante.");
      return;
    }
    const amount = Number(paymentAmountInput);
    const balance = Number(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > balance + 0.01) {
      showToast("error", "Ingresá un importe positivo que no supere el saldo pendiente.");
      return;
    }
    try {
      await paymentProofMutations.submitMutation.mutateAsync({
        reservation_id: editing.id,
        amount: Number(amount.toFixed(2)),
        image_base64: await readFileAsDataUrl(paymentProofFile),
        original_filename: paymentProofFile.name
      });
      setPaymentAmountInput("");
      setPaymentProofFile(null);
      showToast("success", "Comprobante enviado para aprobación");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "No se pudo enviar el comprobante");
    }
  };

  const handleViewPaymentProof = async (proofId: number) => {
    setViewingPaymentProofId(proofId);
    try {
      const blob = await fetchPaymentProofImage(proofId, session);
      if (paymentProofPreview) URL.revokeObjectURL(paymentProofPreview.url);
      setPaymentProofPreview({ proofId, url: URL.createObjectURL(blob) });
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "No se pudo abrir el comprobante");
    } finally {
      setViewingPaymentProofId(null);
    }
  };

  const closePaymentProofPreview = () => {
    if (paymentProofPreview) URL.revokeObjectURL(paymentProofPreview.url);
    setPaymentProofPreview(null);
  };

  const handleRejectPaymentProof = (proofId: number) => {
    const reason = paymentProofRejectReason.trim();
    if (!reason) {
      showToast("error", "Escribí el motivo del rechazo.");
      return;
    }
    paymentProofMutations.rejectMutation.mutate(
      { proofId, reason },
      {
        onSuccess: () => {
          setRejectingPaymentProofId(null);
          setPaymentProofRejectReason("");
          showToast("success", "Comprobante rechazado");
        },
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo rechazar el comprobante")
      }
    );
  };

  const handleGenerateDepositLink = () => {
    if (!editing || !paymentSummary) return;
    const due =
      Math.max(paymentSummary.deposit_required - paymentSummary.amount_paid, 0) ||
      (paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0);
    if (due <= 0.01) {
      showToast("info", "No hay un monto pendiente para generar el link.");
      return;
    }
    const email = editingGuest?.email?.trim();
    if (!email) {
      showToast("error", "El huésped no tiene email; agregá un email para enviar el link de seña.");
      return;
    }
    paymentLinkCreate.mutate(
      {
        reservation_id: editing.id,
        requested_amount: Number(due.toFixed(2)),
        recipient_email: email,
        recipient_name: editingGuest ? `${editingGuest.first_name} ${editingGuest.last_name}`.trim() : undefined,
        recipient_phone: editingGuest?.phone || undefined,
        currency: editingCurrencyCode,
        title: `Seña reserva ${editing.confirmation_code}`
      },
      {
        onSuccess: () => showToast("success", "Link de seña generado"),
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo generar el link")
      }
    );
  };

  const openDetails = (reservation: Reservation) => {
    setDetailsReservationId(reservation.id);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openDetailsById = (reservationId: number) => {
    setDetailsReservationId(reservationId);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const closeDetails = () => {
    setDetailsReservationId(null);
    setRoomMoveForm({ to_room_id: "", reason_code: "", notes: "" });
    setNoShowNotes("");
    setChargeForm({ description: "", amount: "" });
  };
  const openGuest = (guestId: number) => setGuestIdOpen(guestId);
  const closeGuest = () => setGuestIdOpen(null);

  const handleResolveExternal = (reservationId: number) =>
    resolveExternalMutation.mutate(
      { reservationId, payload: { notes: "Cierre manual desde la bandeja operativa." } },
      {
        onSuccess: () => showToast("success", "Follow-up externo marcado como resuelto"),
        onError: (err: unknown) =>
          showToast("error", err instanceof Error ? err.message : "No se pudo cerrar la acción externa")
      }
    );

  const handleClearManualReview = (reservationId: number) =>
    clearManualReviewMutation.mutate(
      { reservationId, payload: { notes: "Revisión manual cerrada desde la bandeja operativa." } },
      {
        onSuccess: () => showToast("success", "Revisión manual cerrada"),
        onError: (err: unknown) =>
          showToast("error", err instanceof Error ? err.message : "No se pudo cerrar la revisión manual")
      }
    );

  const handleRoomMove = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!detailsReservation || !roomMoveForm.to_room_id || !roomMoveForm.reason_code.trim()) {
      showToast("error", "Elegí una habitación destino e indicá el motivo del cambio.");
      return;
    }
    roomMoveMutation.mutate(
      {
        reservationId: detailsReservation.id,
        payload: {
          to_room_id: Number(roomMoveForm.to_room_id),
          reason_code: roomMoveForm.reason_code.trim(),
          notes: roomMoveForm.notes.trim() || null
        }
      },
      {
        onError: (err: unknown) =>
          showToast("error", err instanceof Error ? err.message : "No se pudo cambiar la habitación")
      }
    );
  };

  const handleNoShow = () => {
    if (!detailsReservation || !canNoShow(detailsReservation.status)) return;
    if (!window.confirm("¿Marcar esta reserva como no-show? No genera un cargo automático.")) return;
    noShowMutation.mutate(
      {
        reservationId: detailsReservation.id,
        payload: { client_version: detailsReservation.version ?? 0, notes: noShowNotes.trim() || null }
      },
      {
        onError: (err: unknown) => showToast("error", err instanceof Error ? err.message : "No se pudo registrar el no-show")
      }
    );
  };

  const exportVoucher = () => {
    if (!detailsReservation) return;
    if (detailsFinancialsLoading) {
      showToast("info", "Esperá a que cargue el resumen financiero antes de exportar el voucher.");
      return;
    }
    const summary = detailsSummary;
    const guest = detailsGuest;
    const win = window.open("", "_blank");
    if (!win) return;
    const html = `
      <html>
        <head>
          <title>Voucher ${detailsReservation.confirmation_code}</title>
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
          <h1>Voucher / Confirmación</h1>
          <p class="muted">Código ${detailsReservation.confirmation_code}</p>
          <div class="grid">
            <div class="card">
              <p class="label">Reserva</p>
              <p>Ingreso: <strong>${detailsReservation.check_in_date}</strong></p>
              <p>Salida: <strong>${detailsReservation.check_out_date}</strong></p>
              <p>Hab/Cat: <strong>${detailsReservation.room_id ?? "Sin asignar"} / ${detailsReservation.category_id}</strong></p>
              <p>Estado: <strong>${statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}</strong></p>
            </div>
            <div class="card">
              <p class="label">Huésped</p>
              <p>${guest ? `${guest.first_name} ${guest.last_name}` : `ID ${detailsReservation.guest_id}`}</p>
              <p>Email: ${guest?.email ?? "-"}</p>
              <p>Tel: ${guest?.phone ?? "-"}</p>
            </div>
          </div>
          <div class="card" style="margin-top:12px;">
            <p class="label">Finanzas</p>
            <p>Total: <strong>${formatMoney(summary?.total_amount ?? detailsReservation.total_amount ?? 0, detailsCurrencyCode)}</strong></p>
            <p>Pagado: <strong>${formatMoney(summary?.amount_paid ?? detailsReservation.amount_paid ?? 0, detailsCurrencyCode)}</strong></p>
            <p>Saldo: <strong>${formatMoney(summary?.balance_due ?? detailsReservation.balance_due ?? 0, detailsCurrencyCode)}</strong></p>
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
              {toast.type === "success" ? "Listo" : toast.type === "error" ? "Error" : "Aviso"}
            </p>
            <p className="text-sm text-slate-700">{toast.message}</p>
          </div>
          <button className="ml-auto text-xs text-slate-500 hover:text-slate-800" onClick={() => setToast(null)} type="button">
            Cerrar
          </button>
        </div>
      )}
      {subscriptionBlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {subscriptionBlockReason} Ajustá el plan en{" "}
          <Link to="/settings/subscription" className="font-semibold underline">
            Configuración &gt; Suscripción
          </Link>
          .
        </div>
      )}

      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
          <h1 className="text-2xl font-semibold text-slate-900">Reservas</h1>
          <p className="text-sm text-slate-600">Listado en vivo contra el backend con acciones rápidas.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:opacity-60"
            onClick={openCreate}
            type="button"
            disabled={subscriptionBlocked}
          >
            Crear reserva
          </button>
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Dashboard
          </Link>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <ReservationStatCard label="Activas" value={totals.active} helper="Pendientes + check-in" />
        <ReservationStatCard label="Check-ins hoy" value={totals.checkInsToday} helper={today} />
        <ReservationStatCard label="Checkouts hoy" value={totals.checkOutsToday} helper={today} />
        <ReservationStatCard label="Canceladas" value={totals.cancelled} helper="Últimos 7 días" />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
            <h2 className="text-lg font-semibold text-slate-900">Acciones pendientes</h2>
            <p className="text-sm text-slate-600">
              Seguimiento operativo de revisiones manuales, conciliación OTA y cobros pendientes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
              {pendingActions.length} abiertas
            </span>
            {criticalPendingActions > 0 ? (
              <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700">
                {criticalPendingActions} críticas
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {pendingActionsQuery.isLoading ? (
            <p className="text-sm text-slate-500">Cargando bandeja operativa...</p>
          ) : pendingActions.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              No hay acciones operativas pendientes en este hotel.
            </div>
          ) : (
            pendingActions.map((action) => {
              const priority = priorityConfig[action.priority];
              const isResolveExternal =
                action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
              const isManualReview = action.code === "manual_review_required";

              return (
                <div key={action.action_key} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${priority.className}`}>
                          {priority.label}
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
                        <span>Estado: {action.reservation_status}</span>
                        <span>Origen: {action.source_provider_code || action.source}</span>
                        {action.payment_collection_model ? <span>Cobro: {action.payment_collection_model}</span> : null}
                        {action.settlement_status ? <span>Settlement: {action.settlement_status}</span> : null}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openDetailsById(action.reservation_id)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300"
                      >
                        Ver ficha
                      </button>
                      {isManualReview ? (
                        <button
                          type="button"
                          onClick={() => handleClearManualReview(action.reservation_id)}
                          disabled={clearManualReviewMutation.isPending}
                          className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Cerrar revisión
                        </button>
                      ) : null}
                      {isResolveExternal ? (
                        <button
                          type="button"
                          onClick={() => handleResolveExternal(action.reservation_id)}
                          disabled={resolveExternalMutation.isPending}
                          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Marcar resuelto
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
            <p className="text-xs uppercase tracking-wide text-slate-500">Agenda</p>
            <h2 className="text-lg font-semibold text-slate-900">Ocupación {calendarRange === "week" ? "semanal" : "mensual"}</h2>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCalendarRange("week")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "week" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              Semana
            </button>
            <button
              type="button"
              onClick={() => setCalendarRange("month")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${calendarRange === "month" ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-700"}`}
            >
              Mes
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
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">+{day.arrivals} lleg.</span>
                <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">{day.departures} sal.</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Filtros</p>
            <h2 className="text-lg font-semibold text-slate-900">Fecha y estado</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Desde
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Hasta
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              />
            </label>
            <label className="flex flex-col text-xs font-semibold text-slate-600">
              Estado
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ReservationStatus | "all" | "")}
                className="mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none"
              >
                <option value="">Todos</option>
                <option value="pending">Pendiente</option>
                <option value="deposit_paid">Seña</option>
                <option value="fully_paid">Pago completo</option>
                <option value="pre_check_in">Pre check-in</option>
                <option value="checked_in">Check-in</option>
                <option value="checked_out">Check-out</option>
                <option value="cancelled">Cancelada</option>
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
              Limpiar
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Disponibilidad</p>
            <h2 className="text-lg font-semibold text-slate-900">Consulta rápida por Categoría</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {availabilityMutation.isPending && <span className="text-slate-600">Consultando...</span>}
            {availabilityMutation.isError && <span className="text-rose-600">Error al consultar</span>}
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="text-xs font-semibold text-slate-600">
            Categoría
            <select
              value={availabilityForm.category_id}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, category_id: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            >
              <option value="">Elegí</option>
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Check-in
            <input
              type="date"
              value={availabilityForm.check_in_date}
              onChange={(e) => setAvailabilityForm((prev) => ({ ...prev, check_in_date: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Check-out
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
              Consultar
            </button>
          </div>
        </div>
        {availabilityMutation.data && (
          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {availabilityMutation.data.status === "ok" ? (
              <div className="space-y-1">
                <p>
                  Disponibles: <span className="font-semibold">{availabilityMutation.data.count}</span>
                </p>
                <p className="text-xs text-slate-600">IDs: {availabilityMutation.data.available_rooms.join(", ") || "sin coincidencias"}</p>
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
            <p className="text-xs uppercase tracking-wide text-slate-500">Asignacion</p>
            <h2 className="text-lg font-semibold text-slate-900">Recalculo y movimientos</h2>
            <p className="text-sm text-slate-600">
              Ejecuta una corrida de asignacion y permite revertir grupos recientes de movimientos de habitacion.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {allocationRunMutation.isPending ? <span>Recalculando...</span> : null}
            {movementGroupsQuery.isFetching ? <span>Actualizando grupos...</span> : null}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-5">
          <label className="text-xs font-semibold text-slate-600">
            Desde
            <input
              type="date"
              value={allocationForm.horizon_start}
              onChange={(e) => setAllocationForm((prev) => ({ ...prev, horizon_start: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Hasta
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
            Aplicar cambios
          </label>
          <div className="flex items-end md:col-span-2">
            <button
              type="button"
              onClick={handleAllocationRun}
              disabled={allocationRunMutation.isPending || subscriptionBlocked}
              className="w-full rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Recalcular asignacion
            </button>
          </div>
        </div>

        {allocationRunMutation.data ? (
          <div className="mt-3 grid gap-2 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-900 sm:grid-cols-4">
            <div>
              <p className="text-xs text-emerald-700">Run</p>
              <p className="font-semibold">#{allocationRunMutation.data.run_id}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">Estado</p>
              <p className="font-semibold">{allocationRunMutation.data.status}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">Asignadas</p>
              <p className="font-semibold">{allocationRunMutation.data.assignments_created}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-700">Movidas / sin asignar</p>
              <p className="font-semibold">
                {allocationRunMutation.data.moved_count} / {allocationRunMutation.data.unassigned_count}
              </p>
            </div>
          </div>
        ) : null}

        <div className="mt-4 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-slate-500">Grupos recientes</p>
            <button
              type="button"
              onClick={() => movementGroupsQuery.refetch()}
              className="text-xs font-semibold text-brand-700 hover:underline"
            >
              Actualizar
            </button>
          </div>
          {movementGroupsQuery.isError ? (
            <div className="px-3 py-3 text-sm text-rose-700">
              No se pudieron cargar los grupos de movimiento:{" "}
              {movementGroupsQuery.error instanceof Error ? movementGroupsQuery.error.message : "error desconocido"}
            </div>
          ) : movementGroupsQuery.isLoading ? (
            <div className="px-3 py-3 text-sm text-slate-500">Cargando grupos...</div>
          ) : recentMovementGroups.length === 0 ? (
            <div className="px-3 py-3 text-sm text-slate-600">Sin grupos de movimiento recientes.</div>
          ) : (
            <div className="divide-y divide-slate-200">
              {recentMovementGroups.map((group) => {
                const moveCount = group.move_events.length;
                return (
                  <div key={group.id} className="flex flex-col gap-3 px-3 py-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">Grupo #{group.id}</p>
                        <span
                          className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                            group.is_reverted ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {group.is_reverted ? "Revertido" : "Activo"}
                        </span>
                        <span className="text-xs text-slate-500">{formatDateTime(group.created_at)}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">
                        {group.trigger_reason} - {moveCount} movimiento{moveCount === 1 ? "" : "s"}
                      </p>
                      {group.notes ? <p className="mt-1 text-xs text-slate-500">{group.notes}</p> : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRevertMovementGroup(group)}
                      disabled={group.is_reverted || revertMovementGroupMutation.isPending || subscriptionBlocked}
                      className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Revertir
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
            <p className="text-xs uppercase tracking-wide text-slate-500">Matriz</p>
            <h2 className="text-lg font-semibold text-slate-900">Habitación vs fechas</h2>
            <p className="text-xs text-slate-500">Marcadores de estadía, check-in (verde) y check-out (celeste).</p>
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white px-2 py-1 text-left font-semibold text-slate-600">Hab</th>
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
                      Hab {room.room_number || room.id}
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
            <p className="text-xs uppercase tracking-wide text-slate-500">Listado</p>
            <h2 className="text-lg font-semibold text-slate-900">Reservas recientes</h2>
            {isFetching && <p className="text-xs text-slate-500">Actualizando...</p>}
            {error && <p className="text-xs text-rose-700">No se pudo cargar: {(error as Error).message}</p>}
          </div>
          <span className="text-xs text-slate-500">Total: {reservations.length}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Código</th>
                <th className="px-4 py-2">Huésped</th>
                <th className="px-4 py-2">Hab./Cat</th>
                <th className="px-4 py-2">Ingreso</th>
                <th className="px-4 py-2">Salida</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2 text-right">Monto</th>
                <th className="px-4 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {!isLoading && reservations.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-sm text-slate-500" colSpan={8}>
                    No hay reservas con los filtros actuales.
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
                        {reservationGuestLabel(reservation)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {reservation.room_id ? `Hab ${reservation.room_id}` : "Sin asignar"} · Cat {reservation.category_id}
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
                          Editar
                        </button>
                        <button
                          type="button"
                          onClick={() => openDetails(reservation)}
                          className="rounded-lg border border-slate-200 px-2 py-1 hover:border-slate-300"
                        >
                          Ficha
                        </button>
                        <button
                          type="button"
                          disabled={!canCancel(reservation.status) || cancelMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCancel(reservation.id)}
                          className="rounded-lg border border-rose-200 px-2 py-1 text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckIn(reservation.status) || checkInMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCheckIn(reservation)}
                          title={
                            isCheckInReady(reservation.status)
                              ? "Registrar check-in"
                              : "Cobrar el saldo antes del check-in"
                          }
                          className="rounded-lg border border-emerald-200 px-2 py-1 text-emerald-700 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-in
                        </button>
                        <button
                          type="button"
                          disabled={!canCheckOut(reservation.status) || checkOutMutation.isPending || subscriptionBlocked}
                          onClick={() => handleCheckOut(reservation)}
                          className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Check-out
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {formOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/40 px-4 py-6">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{editing ? "Editar" : "Crear"}</p>
                <h3 className="text-lg font-semibold text-slate-900">Reserva</h3>
                <p className="text-xs text-slate-500">Completá los campos mínimos: Huésped, Categoría y fechas.</p>
              </div>
              <button onClick={closeForm} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
            </div>

            {subscriptionBlocked && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                {subscriptionBlockReason} No podrás crear o editar reservas hasta regularizarlo.{" "}
                <Link to="/settings/subscription" className="font-semibold underline">
                  Ir a Suscripción
                </Link>
                .
              </div>
            )}
            {formError && <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</div>}

            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                Datos de la reserva
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  ID Huésped
                  <input
                    type="number"
                    min={1}
                    placeholder="Ej: 12 (deja vacío y usa Huésped rápido)"
                    value={formValues.guest_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, guest_id: e.target.value }))}
                    disabled={Boolean(editing)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Categoría
                  <select
                    value={formValues.category_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, category_id: e.target.value, room_id: "" }))}
                    disabled={Boolean(editing)}
                    title={editing ? "La categoría de una reserva existente no se puede cambiar desde acá." : undefined}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="">Elegí una Categoría</option>
                    {categoryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">Huésped rápido</p>
                    <p className="text-xs text-slate-600">Creá y asigná sin salir del formulario.</p>
                  </div>
                  {guestMutation.isPending && <span className="text-xs text-slate-500">Guardando...</span>}
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
                  <input
                    placeholder="Nombre"
                    value={guestForm.first_name}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, first_name: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Apellido"
                    value={guestForm.last_name}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, last_name: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Email"
                    value={guestForm.email}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, email: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <input
                    placeholder="Teléfono"
                    value={guestForm.phone}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, phone: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                  <label className="text-xs font-semibold text-slate-600">
                    Tipo de documento
                    <select
                      aria-label="Tipo de documento"
                      value={guestForm.document_type ?? "DNI"}
                      onChange={(e) =>
                        setGuestForm((prev) => ({
                          ...prev,
                          document_type: e.target.value as NonNullable<GuestPayload["document_type"]>
                        }))
                      }
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                    >
                      <option value="DNI">DNI</option>
                      <option value="PASSPORT">Pasaporte</option>
                      <option value="CEDULA">Cédula</option>
                    </select>
                  </label>
                  <input
                    placeholder="Documento"
                    value={guestForm.document_number ?? ""}
                    onChange={(e) => setGuestForm((prev) => ({ ...prev, document_number: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  <button
                    type="button"
                    onClick={handleCreateGuest}
                    disabled={guestMutation.isPending || !guestForm.first_name || !guestForm.last_name}
                    className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Crear Huésped y asignar ID
                  </button>
                  <span>Se asigna automáticamente al campo ID Huésped</span>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  Habitación (opcional)
                  <select
                    value={formValues.room_id}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, room_id: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  >
                    <option value="">Sin asignar</option>
                    {availableRooms.map((room) => (
                      <option key={room.id} value={room.id}>
                        {`Hab ${room.room_number || room.id} · Cat ${room.category_id}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Origen
                  <select
                    value={formValues.source}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, source: e.target.value as ReservationSource }))}
                    disabled={Boolean(editing)}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="direct">Directo</option>
                    <option value="booking">Booking.com</option>
                    <option value="expedia">Expedia</option>
                    <option value="other_ota">Otra OTA</option>
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">
                  Check-in
                  <input
                    type="date"
                    value={formValues.check_in_date}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, check_in_date: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Check-out
                  <input
                    type="date"
                    value={formValues.check_out_date}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, check_out_date: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
              </div>

              {!editing && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-xs font-semibold text-slate-600">
                      Medio para calcular total
                      <select
                        value={pricingPaymentMethod}
                        onChange={(e) => setPricingPaymentMethod(e.target.value as PricingPaymentMethod)}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      >
                        {pricingPaymentMethodOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Seña manual
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={depositAmountInput}
                        onChange={(e) => setDepositAmountInput(e.target.value)}
                        placeholder="Usar configuración del hotel"
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      />
                    </label>
                  </div>

                  <div className="mt-3 grid gap-2 sm:grid-cols-4">
                    <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      <p className="text-xs text-slate-500">Noches</p>
                      <p className="font-semibold">{reservationQuote?.nights ?? quoteNights}</p>
                    </div>
                    <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      <p className="text-xs text-slate-500">Total final</p>
                      <p className="font-semibold">
                        {quoteQuery.isFetching
                          ? "Actualizando..."
                          : quoteQuery.isError
                            ? "Total no disponible"
                          : formatMoney(reservationQuote?.total ?? 0, reservationQuote?.currencyCode ?? "ARS")}
                      </p>
                    </div>
                    <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      <p className="text-xs text-slate-500">Seña</p>
                      <p className="font-semibold">
                        {quoteQuery.isError
                          ? "No disponible"
                          : depositPreview !== null
                          ? formatMoney(depositPreview, reservationQuote?.currencyCode ?? "ARS")
                          : "Por configurar"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2 text-sm text-slate-800">
                      <p className="text-xs text-slate-500">Saldo estimado</p>
                      <p className="font-semibold">
                        {quoteBalancePreview !== null
                          ? formatMoney(quoteBalancePreview, reservationQuote?.currencyCode ?? "ARS")
                          : "-"}
                      </p>
                    </div>
                  </div>

                  {quoteQuery.isError ? (
                    <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
                      <p>
                        {quoteQuery.error instanceof ApiError && quoteQuery.error.status === 404
                          ? "No hay una tarifa disponible para la categoría y las fechas elegidas."
                          : "No se pudo calcular la cotización. Revisá las fechas y las tarifas antes de confirmar."}
                      </p>
                      <button
                        type="button"
                        onClick={() => void quoteQuery.refetch()}
                        disabled={quoteQuery.isFetching}
                        className="mt-2 rounded-lg border border-rose-300 bg-white px-3 py-2 font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
                      >
                        Reintentar
                      </button>
                    </div>
                  ) : reservationQuote?.rows.length ? (
                    <div className="mt-3 overflow-x-auto rounded-lg border border-blue-100 bg-white/70">
                      <table className="min-w-full text-left text-xs">
                        <thead className="bg-white text-slate-500">
                          <tr>
                            <th className="px-3 py-2 font-semibold">Noche</th>
                            <th className="px-3 py-2 font-semibold">Origen</th>
                            <th className="px-3 py-2 text-right font-semibold">Importe</th>
                          </tr>
                        </thead>
                        <tbody>
                          {reservationQuote.rows.slice(0, 6).map((row) => (
                            <tr key={row.date} className="border-t border-blue-100">
                              <td className="px-3 py-2 text-slate-700">{row.date}</td>
                              <td className="px-3 py-2 text-slate-500">{row.source}</td>
                              <td className="px-3 py-2 text-right font-semibold text-slate-800">
                                {formatMoney(row.amount, reservationQuote.currencyCode)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {reservationQuote.rows.length > 6 ? (
                        <p className="border-t border-blue-100 px-3 py-2 text-xs text-slate-500">
                          {reservationQuote.rows.length - 6} noches más incluidas en el total.
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-600">
                      {quoteNights > 0
                        ? "Calculando la cotización vigente desde Tarifas..."
                        : "Elegí categoría y fechas para calcular el precio desde Tarifas."}
                    </p>
                  )}
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="text-xs font-semibold text-slate-600">
                  Adultos
                  <input
                    type="number"
                    min={1}
                    value={formValues.num_adults}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, num_adults: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Menores
                  <input
                    type="number"
                    min={0}
                    value={formValues.num_children}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, num_children: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-600">
                  Estado
                  <select
                    value={formValues.status}
                    onChange={(e) => setFormValues((prev) => ({ ...prev, status: e.target.value as ReservationStatus }))}
                    disabled={Boolean(editing)}
                    title={
                      editing
                        ? "El estado no se cambia desde acá: usá Check-in, Check-out, Cancelar o Marcar no-show."
                        : undefined
                    }
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm disabled:bg-slate-50"
                  >
                    <option value="pending">Pendiente</option>
                    <option value="deposit_paid">Seña</option>
                    <option value="fully_paid">Pago completo</option>
                    <option value="pre_check_in">Pre check-in</option>
                    <option value="checked_in">Check-in</option>
                    <option value="checked_out">Check-out</option>
                    <option value="cancelled">Cancelada</option>
                  </select>
                </label>
              </div>

              <label className="text-xs font-semibold text-slate-600">
                Notas
                <textarea
                  value={formValues.notes}
                  placeholder="Notas internas (opcional)"
                  onChange={(e) => setFormValues((prev) => ({ ...prev, notes: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                  rows={3}
                />
              </label>

              {editing && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-emerald-700">Pagos y balance</p>
                      <p className="text-xs text-emerald-800">Resumen financiero y acciones rápidas.</p>
                    </div>
                    {paymentSummaryQuery.isFetching && <span className="text-xs text-emerald-700">Actualizando...</span>}
                  </div>
                  {paymentSummary ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-4">
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Total</p>
                        <p className="font-semibold">
                          {formatMoney(paymentSummary.operational_total_amount ?? paymentSummary.total_amount ?? 0, editingCurrencyCode)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Pagado</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.amount_paid ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Seña requerida</p>
                        <p className="font-semibold">{formatMoney(paymentSummary.deposit_required ?? 0, editingCurrencyCode)}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-800">
                        <p className="text-xs text-slate-500">Saldo</p>
                        <p className="font-semibold">
                          {formatMoney(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0, editingCurrencyCode)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-600">Cargando resumen...</p>
                  )}

                  <div className="mt-3 grid gap-2 sm:grid-cols-6 sm:items-end">
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">
                      Medio de pago
                      <select
                        value={paymentMethod}
                        onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 shadow-sm"
                      >
                        {availablePaymentMethods.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Monto a cobrar
                      <input
                        aria-label="Monto a cobrar"
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={paymentAmountInput}
                        onChange={(event) => setPaymentAmountInput(event.target.value)}
                        placeholder="Importe parcial"
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
                      Registrar Seña
                    </button>
                    <button
                      type="button"
                      onClick={handlePayFull}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-emerald-200 bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-800 hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Pago total
                    </button>
                    <button
                      type="button"
                      onClick={handleRefund}
                      disabled={paymentMutation.isPending || paymentSummaryQuery.isLoading || paymentMethod !== "cash"}
                      className="rounded-lg border border-violet-200 bg-violet-100 px-3 py-2 text-sm font-semibold text-violet-800 hover:border-violet-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Registrar devolución
                    </button>
                    {paymentMutation.isError && (
                      <p className="text-xs text-rose-600">Error al registrar pago.</p>
                    )}
                  </div>

                  {paymentMethod === "cash" && (
                    hasOpenCashSession ? (
                      <p className="mt-2 text-xs text-emerald-700">
                        El cobro en efectivo se registrará automáticamente en la caja abierta.
                      </p>
                    ) : (
                      <p className="mt-2 text-xs text-amber-700">
                        No hay caja abierta: abrí caja antes de cobrar en efectivo.{" "}
                        <Link to="/caja" className="font-semibold underline">
                          Abrir caja
                        </Link>
                        .
                      </p>
                    )
                  )}

                  {paymentMethod === "bank_transfer" && (
                    <div className="mt-3 space-y-3 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-3 text-xs text-slate-700">
                      <div>
                        <p className="font-semibold text-slate-800">Comprobante de transferencia</p>
                        <p className="mt-1 text-slate-600">La transferencia no descuenta saldo hasta que un responsable la aprueba.</p>
                      </div>
                      <label className="block text-xs font-semibold text-slate-700">
                        Imagen del comprobante
                        <input
                          aria-label="Imagen del comprobante"
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
                        {paymentProofMutations.submitMutation.isPending ? "Enviando..." : "Enviar comprobante"}
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
                                  {viewingPaymentProofId === proof.id ? "Abriendo..." : "Ver imagen"}
                                </button>
                                {canApprovePaymentProof && proof.status === "pending" && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => paymentProofMutations.approveMutation.mutate(proof.id)}
                                      disabled={paymentProofMutations.approveMutation.isPending}
                                      className="rounded-lg border border-emerald-200 px-2 py-1 font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
                                    >
                                      Aprobar
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setRejectingPaymentProofId(rejectingPaymentProofId === proof.id ? null : proof.id)}
                                      disabled={paymentProofMutations.rejectMutation.isPending}
                                      className="rounded-lg border border-rose-200 px-2 py-1 font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                                    >
                                      Rechazar
                                    </button>
                                  </>
                                )}
                              </div>
                              {canApprovePaymentProof && rejectingPaymentProofId === proof.id && proof.status === "pending" && (
                                <div className="flex w-full flex-wrap items-center gap-2">
                                  <label className="sr-only" htmlFor={`payment-proof-reason-${proof.id}`}>
                                    Motivo del rechazo
                                  </label>
                                  <input
                                    id={`payment-proof-reason-${proof.id}`}
                                    value={paymentProofRejectReason}
                                    onChange={(event) => setPaymentProofRejectReason(event.target.value)}
                                    placeholder="Motivo del rechazo"
                                    className="min-w-[12rem] flex-1 rounded-lg border border-rose-200 px-2 py-1 text-xs"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleRejectPaymentProof(proof.id)}
                                    disabled={paymentProofMutations.rejectMutation.isPending}
                                    className="rounded-lg bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                                  >
                                    Confirmar rechazo
                                  </button>
                                </div>
                              )}
                              {paymentProofPreview?.proofId === proof.id && (
                                <div className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2">
                                  <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold text-slate-700">
                                    <span>Vista privada del comprobante</span>
                                    <button type="button" onClick={closePaymentProofPreview} className="underline">
                                      Cerrar
                                    </button>
                                  </div>
                                  <img src={paymentProofPreview.url} alt={proof.original_filename || "Comprobante de transferencia"} className="max-h-64 w-full rounded object-contain" />
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
                      apply_surcharge=False), so showing a "se cobra más" figure here would
                      promise a recargo that is never actually charged. */}
                  {activeSurcharge && paymentMethod !== "bank_transfer" && paymentSummary && (paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0) > 0 && (
                    <p className="mt-2 text-xs text-amber-700">
                      Recargo por {paymentMethodOptions.find((o) => o.value === paymentMethod)?.label ?? paymentMethod}:{" "}
                      {activeSurcharge.surcharge_type === "percentage"
                        ? `${activeSurcharge.amount}%`
                        : formatMoney(activeSurcharge.amount, editingCurrencyCode)}
                      . Pago total: saldo{" "}
                      {formatMoney(paymentSummary.operational_balance_due ?? paymentSummary.balance_due ?? 0, editingCurrencyCode)} → se
                      cobra{" "}
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
                      <p className="font-semibold text-slate-800">Link de seña para el huésped</p>
                      <button
                        type="button"
                        onClick={handleGenerateDepositLink}
                        disabled={paymentLinkCreate.isPending || paymentSummaryQuery.isLoading}
                        className="rounded-lg border border-sky-200 bg-white px-3 py-1 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:opacity-60"
                      >
                        {paymentLinkCreate.isPending ? "Generando..." : "Generar link"}
                      </button>
                    </div>
                    {(paymentLinksQuery.data ?? []).length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {(paymentLinksQuery.data ?? []).map((lnk) => {
                          const url = lnk.external_checkout_url || `${window.location.origin}/pay/${lnk.link_code}`;
                          return (
                            <li key={lnk.id} className="flex items-center justify-between gap-2">
                              <span className="truncate">
                                {formatMoney(lnk.requested_amount, lnk.currency)} · {lnk.status}
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  navigator.clipboard?.writeText(url);
                                  showToast("success", "Link copiado");
                                }}
                                className="shrink-0 rounded-lg border border-slate-200 px-2 py-1 font-semibold text-slate-700 hover:bg-white"
                              >
                                Copiar link
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <p className="mt-1 text-slate-500">Sin links generados. Generá uno para cobrar la seña online (MercadoPago).</p>
                    )}
                  </div>

                  {paymentSummary?.transactions?.length ? (
                    <div className="mt-3 rounded-lg border border-emerald-100 bg-white/60 px-3 py-2 text-xs text-slate-700">
                      <p className="font-semibold text-slate-800">Movimientos</p>
                      <ul className="mt-1 space-y-1">
                        {paymentSummary.transactions.map((tx) => (
                          <li key={tx.id} className="flex items-center justify-between">
                            <span>
                              {tx.type} · {tx.method}
                              {tx.fee_amount && tx.fee_amount > 0 ? (
                                <span className="text-amber-700"> · recargo {formatMoney(tx.fee_amount, tx.currency)}</span>
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
                    <p className="mt-2 text-xs text-slate-600">Sin pagos registrados.</p>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={closeForm}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  disabled={
                    createMutation.isPending ||
                    updateMutation.isPending ||
                    subscriptionBlocked ||
                    (!editing && (quoteQuery.isFetching || !reservationQuote?.quoteToken))
                  }
                >
                  {editing ? "Guardar cambios" : quoteQuery.isFetching ? "Actualizando..." : "Crear"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {detailsReservation && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha</p>
                <h3 className="text-lg font-semibold text-slate-900">Reserva {detailsReservation.confirmation_code}</h3>
                <p className="text-xs text-slate-500">
                  {reservationGuestLabel(detailsReservation)} - Cat {detailsReservation.category_id} -{" "}
                  {detailsRoom ? `Hab ${detailsRoom.room_number}` : detailsReservation.room_id ? `Hab #${detailsReservation.room_id}` : "Sin asignar"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={exportVoucher}
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
                >
                  Exportar voucher PDF
                </button>
                <button onClick={closeDetails} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                  Cerrar
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Timeline</p>
                <ul className="space-y-2 text-sm text-slate-800">
                  <li>
                    <span className="font-semibold">Check-in:</span> {detailsReservation.check_in_date}
                  </li>
                  <li>
                    <span className="font-semibold">Check-out:</span> {detailsReservation.check_out_date}
                  </li>
                  <li>
                    <span className="font-semibold">Estado:</span> {statusConfig[detailsReservation.status]?.label ?? detailsReservation.status}
                  </li>
                  {detailsSummary?.transactions?.length ? (
                    <li>
                      <span className="font-semibold">Último pago:</span>{" "}
                      {detailsSummary.transactions[detailsSummary.transactions.length - 1].created_at}
                    </li>
                  ) : null}
                </ul>
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Finanzas</p>
                {detailsFinancialsLoading ? (
                  <p className="rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-sm text-slate-600">
                    Cargando resumen financiero…
                  </p>
                ) : detailsSummary ? (
                  <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                    <div>
                      <p className="text-xs text-slate-500">Total</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.total_amount, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Pagado</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.amount_paid, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Depósito</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.deposit_required, detailsCurrencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Saldo</p>
                      <p className="font-semibold">{formatMoney(detailsSummary.balance_due, detailsCurrencyCode)}</p>
                    </div>
                  </div>
                ) : (
                  <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    No se pudo cargar el resumen financiero. Reintentá abrir la ficha.
                  </p>
                )}
                {detailsOperations?.financial_summary ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-slate-500">Total operativo</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_total_amount ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Saldo operativo</p>
                        <p className="font-semibold">
                          {formatMoney(
                            detailsOperations.financial_summary.operational_balance_due ?? 0,
                            detailsOperations.financial_summary.currency_code
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Cobro</p>
                        <p className="font-semibold">{detailsOperations.payment_collection_model}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Settlement</p>
                        <p className="font-semibold">{detailsOperations.settlement_status}</p>
                      </div>
                    </div>
                    {detailsOperations.financial_summary.recommended_next_action ? (
                      <p className="mt-2 text-xs text-amber-700">
                        Próxima acción sugerida: {detailsOperations.financial_summary.recommended_next_action}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
                  {detailsOperationsQuery.isFetching ? <span className="text-xs text-slate-500">Actualizando...</span> : null}
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-800">
                  <div>
                    <p className="text-xs text-slate-500">Asignación</p>
                    <p className="font-semibold">{detailsOperations?.allocation_status ?? detailsReservation.allocation_status ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Revisión manual</p>
                    <p className="font-semibold">{detailsOperations?.requires_manual_review ? "Sí" : "No"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Acciones pendientes</p>
                    <p className="font-semibold">{detailsOperations?.pending_action_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Último movimiento</p>
                    <p className="font-semibold">{detailsOperations?.latest_room_move?.move_type ?? "-"}</p>
                  </div>
                </div>
                {detailsOperations?.ota_link ? (
                  <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                    <p className="font-semibold text-slate-800">Canal externo</p>
                    <p>Estado: {detailsOperations.ota_link.provider_state}</p>
                    <p>Sync: {detailsOperations.ota_link.sync_status ?? "-"}</p>
                    {detailsOperations.ota_link.error_message ? (
                      <p className="mt-1 text-amber-700">{detailsOperations.ota_link.error_message}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Acciones</p>
                {detailsOperations?.pending_actions?.length ? (
                  <div className="space-y-2">
                    {detailsOperations.pending_actions.map((action) => {
                      const priority = priorityConfig[action.priority];
                      const isResolveExternal =
                        action.code === "resolve_external_channel" || action.code === "resolve_adjustment_external_action";
                      const isManualReview = action.code === "manual_review_required";

                      return (
                        <div key={action.action_key} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${priority.className}`}>
                                  {priority.label}
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
                                  Cerrar revisión
                                </button>
                              ) : null}
                              {isResolveExternal ? (
                                <button
                                  type="button"
                                  onClick={() => handleResolveExternal(detailsReservation.id)}
                                  disabled={resolveExternalMutation.isPending}
                                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Marcar resuelto
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">Sin acciones pendientes para esta reserva.</p>
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
                  <p className="text-xs uppercase tracking-wide text-slate-500">Operación</p>
                  <h4 id="stay-operations-title" className="text-sm font-semibold text-slate-900">
                    Operaciones de estadía
                  </h4>
                  <p className="text-xs text-slate-600">
                    Los cambios quedan auditados. El no-show no genera un cargo automático.
                  </p>
                </div>
                {detailsReservation.version !== undefined ? (
                  <span className="text-xs text-slate-500">Versión {detailsReservation.version}</span>
                ) : null}
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <form className="space-y-3 rounded-lg border border-slate-200 bg-white p-3" onSubmit={handleRoomMove}>
                  <p className="text-sm font-semibold text-slate-800">Cambiar habitación</p>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Habitación destino</span>
                    <select
                      value={roomMoveForm.to_room_id}
                      onChange={(event) => setRoomMoveForm((current) => ({ ...current, to_room_id: event.target.value }))}
                      disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      <option value="">Seleccionar habitación</option>
                      {moveRoomOptions.map((room) => (
                        <option key={room.id} value={room.id}>
                          Hab {room.room_number} · Piso {room.floor}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Motivo del cambio</span>
                    <input
                      value={roomMoveForm.reason_code}
                      onChange={(event) => setRoomMoveForm((current) => ({ ...current, reason_code: event.target.value }))}
                      disabled={!canMoveRoom(detailsReservation.status) || roomMoveMutation.isPending}
                      placeholder="Mantenimiento, upgrade, pedido del huésped"
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Notas del cambio</span>
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
                    {roomMoveMutation.isPending ? "Moviendo..." : "Mover habitación"}
                  </button>
                  {moveRoomOptions.length === 0 && canMoveRoom(detailsReservation.status) ? (
                    <p className="text-xs text-amber-700">No hay otra habitación activa disponible en esta categoría.</p>
                  ) : null}
                </form>

                <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-slate-800">Registrar no-show</p>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Notas del no-show</span>
                    <textarea
                      aria-label="Notas del no-show"
                      value={noShowNotes}
                      onChange={(event) => setNoShowNotes(event.target.value)}
                      disabled={!canNoShow(detailsReservation.status) || noShowMutation.isPending}
                      rows={4}
                      placeholder="Motivo o contacto realizado"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={handleNoShow}
                    disabled={!canNoShow(detailsReservation.status) || noShowMutation.isPending}
                    className="w-full rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-800 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {noShowMutation.isPending ? "Registrando..." : "Marcar no-show"}
                  </button>
                  {!canNoShow(detailsReservation.status) ? (
                    <p className="text-xs text-slate-500">Esta reserva ya no admite marcar no-show desde su estado actual.</p>
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
                  <p className="text-xs uppercase tracking-wide text-slate-500">Cuenta del huésped</p>
                  <h4 id="reservation-charges-title" className="text-sm font-semibold text-slate-900">
                    Consumos y cargos
                  </h4>
                  <p className="text-xs text-slate-600">
                    Cargá minibar, desayuno u otros extras sin editar el precio original de la reserva.
                  </p>
                </div>
                {detailsOperations?.financial_summary ? (
                  <span className="text-xs font-semibold text-slate-700">
                    Saldo operativo: {formatMoney(detailsOperations.financial_summary.operational_balance_due ?? 0, detailsOperations.financial_summary.currency_code)}
                  </span>
                ) : null}
              </div>

              {detailsOperations?.financial_summary?.billing_adjustments?.length ? (
                <ul className="mt-3 space-y-2" aria-label="Consumos registrados">
                  {detailsOperations.financial_summary.billing_adjustments.map((charge) => (
                    <li key={charge.id} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
                      <div>
                        <p className="font-semibold text-slate-900">{charge.notes || "Cargo adicional"}</p>
                        <p className="text-xs text-slate-500">{charge.type === "charge" ? "Consumo" : charge.type}</p>
                      </div>
                      <span className="font-semibold text-slate-900">{formatMoney(charge.total_amount, charge.currency_code)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-slate-600">Todavía no hay consumos cargados.</p>
              )}

              <form
                className="mt-3 grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[minmax(0,1fr)_10rem_auto] md:items-end"
                onSubmit={(event) => {
                  event.preventDefault();
                  const amount = Number(chargeForm.amount);
                  if (!chargeForm.description.trim() || !Number.isFinite(amount) || amount <= 0) {
                    showToast("error", "Ingresá un detalle y un importe positivo para el consumo.");
                    return;
                  }
                  chargeMutation.mutate({
                    reservationId: detailsReservation.id,
                    payload: { description: chargeForm.description, amount, currency_code: detailsReservation.currency_code || "ARS" }
                  });
                }}
              >
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Detalle del consumo</span>
                  <input
                    value={chargeForm.description}
                    onChange={(event) => setChargeForm((current) => ({ ...current, description: event.target.value }))}
                    placeholder="Minibar, desayuno, late checkout..."
                    disabled={!canAddCharge(detailsReservation.status) || chargeMutation.isPending}
                    required
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Importe</span>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={chargeForm.amount}
                    onChange={(event) => setChargeForm((current) => ({ ...current, amount: event.target.value }))}
                    placeholder="0,00"
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
                  {chargeMutation.isPending ? "Cargando..." : "Cargar consumo"}
                </button>
              </form>
              {!canAddCharge(detailsReservation.status) ? (
                <p className="mt-2 text-xs text-slate-500">La reserva ya no admite consumos porque la estadía terminó.</p>
              ) : null}
            </section>

            {detailsOperations?.open_adjustments?.length ? (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Ajustes operativos</p>
                </div>
                <div className="divide-y divide-slate-200 p-3">
                  {detailsOperations.open_adjustments.map((adjustment) => (
                    <div key={adjustment.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                      <div>
                        <p className="font-semibold text-slate-900">{adjustment.kind}</p>
                        <p className="text-xs text-slate-600">
                          Estado: {adjustment.status} · Resolución externa: {adjustment.external_resolution_status ?? "-"}
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
                <p className="text-xs uppercase tracking-wide text-slate-500">Pagos</p>
              </div>
              <div className="p-3 text-sm text-slate-800">
                {detailsSummary?.transactions?.length ? (
                  <ul className="divide-y divide-slate-200">
                    {detailsSummary.transactions.map((tx) => (
                      <li key={tx.id} className="flex items-center justify-between py-2">
                        <div>
                          <p className="font-semibold">{formatMoney(tx.amount, tx.currency)}</p>
                          <p className="text-xs text-slate-500">
                            {tx.type} · {tx.method} · {tx.status}
                          </p>
                        </div>
                        <span className="text-xs text-slate-500">{tx.created_at}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600">Sin transacciones registradas.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {guestIdOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/30 px-4 py-6">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha de Huésped</p>
                <h3 className="text-lg font-semibold text-slate-900">
                  {guestQuery.data ? `${guestQuery.data.first_name} ${guestQuery.data.last_name}` : `Huésped #${guestIdOpen}`}
                </h3>
                <p className="text-xs text-slate-500">Contacto y reservas asociadas.</p>
              </div>
              <button onClick={closeGuest} type="button" className="text-sm text-slate-500 hover:text-slate-800">
                Cerrar
              </button>
            </div>

            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">Contacto</p>
                <p className="mt-1">{guestQuery.data?.email ?? "Sin email"}</p>
                <p>{guestQuery.data?.phone ?? "Sin teléfono"}</p>
                <p className="text-xs text-slate-500">
                  Doc: {guestQuery.data?.document_type ?? "-"} {guestQuery.data?.document_number ?? ""}
                </p>
                <p className="text-xs text-slate-500">
                  {guestQuery.data?.city ?? ""} {guestQuery.data?.country ?? ""}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-500">Histórico</p>
                {guestHistory.length ? (
                  <ul className="mt-2 space-y-2">
                    {guestHistory.map((r) => (
                      <li key={r.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-2 py-1">
                        <span className="text-xs text-slate-600">
                          {r.check_in_date} → {r.check_out_date} · {statusConfig[r.status]?.label ?? r.status}
                        </span>
                        <button className="text-xs font-semibold text-brand-700 hover:underline" onClick={() => openDetails(r)} type="button">
                          Ver
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-600">Sin reservas asociadas en esta vista.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
