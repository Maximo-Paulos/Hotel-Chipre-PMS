import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { type TFunction } from "i18next";

import { ApiError } from "../api/client";
import { fetchCompanyDocumentFile, type CompanyNightlyRate } from "../api/companies";
import {
  createCompanyNightCharges,
  correctCompanyNightChargeAmounts,
  type CompanyNightChargeCorrection
} from "../api/companyNightCharges";
import { invalidateQueriesInBackground, refreshPaymentState, refreshReservationRecordState } from "../api/queryInvalidation";
import {
  extendReservationStay,
  isDeferredCompanyReservation,
  previewReservationStayExtension,
  type ReservationExtensionImpactAction,
  type ReservationExtensionImpactPlan,
  type ReservationExtensionPayload,
  type ReservationExtensionPreview
} from "../api/reservations";
import { type GuestUpdatePayload } from "../api/guests";
import { type RestrictionOverride } from "../api/guestRestrictions";
import { type PaymentMethod } from "../api/payments";
import { grossWithSurcharge } from "../api/paymentSurcharges";
import { useDialogA11y } from "../hooks/useDialogA11y";
import {
  useReservation,
  useReservationMutations,
  useReservationOperationsSummary,
  useValidateGuestCheckin
} from "../hooks/useReservations";
import { useGuest } from "../hooks/useGuests";
import { useCompanyNightCharges } from "../hooks/useCompanyNightCharges";
import {
  useCompanyDocumentMutations,
  useCompanyNightlyRates,
  useMarkCompanyDocumentSigned,
  useReservationCompanyDocuments
} from "../hooks/useCompanies";
import { useEffectivePermissions } from "../hooks/usePermissions";
import { usePaymentMutation, usePaymentSummary } from "../hooks/usePayments";
import { usePaymentSurchargeQuote, usePaymentSurcharges } from "../hooks/usePaymentSurcharges";
import { useRestrictionOverridePrompt } from "../hooks/useRestrictionOverridePrompt";
import { useGuardedMutation } from "../hooks/useGuardedMutation";
import { useSession } from "../state/session";
import { formatMoney, normalizeCurrencyCode } from "../utils/currency";
import { calculateCashTender, calculateCashTip } from "../utils/cashTender.mjs";
import {
  canCancelReservation,
  canCheckInReservation,
  canCheckOutReservation,
  canPartialCheckIn,
  reservationStatusConfig
} from "../utils/reservationStatus";

import { GuestRestrictionBadge } from "./GuestRestrictionBadge";
import { CashTenderField } from "./CashTenderField";
import { PaymentQuoteSummary } from "./PaymentQuoteSummary";
import ConfirmDialog from "./ConfirmDialog";
import TemporaryCancelPermissionRequest from "./TemporaryCancelPermissionRequest";
import { RestrictionOverrideModal } from "./RestrictionOverrideModal";
import { ReservationGuestArrivalPanel } from "./ReservationGuestArrivalPanel";
import { CompanyTermsReviewPanel } from "./CompanyTermsReviewPanel";

type CheckinCaptureForm = {
  document_type: "" | "DNI" | "PASSPORT" | "CEDULA";
  document_number: string;
  nationality: string;
  country: string;
  birth_place: string;
  birth_country: string;
  marital_status: string;
  occupation: string;
  terms_accepted: boolean;
};

const emptyCaptureForm: CheckinCaptureForm = {
  document_type: "",
  document_number: "",
  nationality: "",
  country: "",
  birth_place: "",
  birth_country: "",
  marital_status: "",
  occupation: "",
  terms_accepted: false
};

const MAX_COMPANY_VOUCHER_PDF_BYTES = 5 * 1024 * 1024;

const checkinValidationErrorKeys: Record<string, string> = {
  "First name is required": "drawer.checkinCapture.requiredFields.firstName",
  "Last name is required": "drawer.checkinCapture.requiredFields.lastName",
  "Document type (DNI/Passport) is required": "drawer.checkinCapture.requiredFields.documentType",
  "Document number is required": "drawer.checkinCapture.requiredFields.documentNumber",
  "Nationality is required": "drawer.checkinCapture.requiredFields.nationality",
  "Country is required": "drawer.checkinCapture.requiredFields.country",
  "Birth place is required": "drawer.checkinCapture.requiredFields.birthPlace",
  "Birth country is required": "drawer.checkinCapture.requiredFields.birthCountry",
  "Marital status is required": "drawer.checkinCapture.requiredFields.maritalStatus",
  "Occupation is required": "drawer.checkinCapture.requiredFields.occupation",
  "Guest must accept terms and conditions": "drawer.checkinCapture.requiredFields.termsAccepted",
  "El nombre es obligatorio": "drawer.checkinCapture.requiredFields.firstName",
  "El apellido es obligatorio": "drawer.checkinCapture.requiredFields.lastName",
  "El tipo de documento (DNI/pasaporte) es obligatorio": "drawer.checkinCapture.requiredFields.documentType",
  "El número de documento es obligatorio": "drawer.checkinCapture.requiredFields.documentNumber",
  "La nacionalidad es obligatoria": "drawer.checkinCapture.requiredFields.nationality",
  "El país es obligatorio": "drawer.checkinCapture.requiredFields.country",
  "El lugar de nacimiento es obligatorio": "drawer.checkinCapture.requiredFields.birthPlace",
  "El país de nacimiento es obligatorio": "drawer.checkinCapture.requiredFields.birthCountry",
  "El estado civil es obligatorio": "drawer.checkinCapture.requiredFields.maritalStatus",
  "La ocupación es obligatoria": "drawer.checkinCapture.requiredFields.occupation",
  "El huésped debe aceptar los términos y condiciones": "drawer.checkinCapture.requiredFields.termsAccepted"
};

const checkinFieldKeysByName: Record<string, string> = {
  first_name: "drawer.checkinCapture.requiredFields.firstName",
  last_name: "drawer.checkinCapture.requiredFields.lastName",
  document_type: "drawer.checkinCapture.requiredFields.documentType",
  document_number: "drawer.checkinCapture.requiredFields.documentNumber",
  nationality: "drawer.checkinCapture.requiredFields.nationality",
  country: "drawer.checkinCapture.requiredFields.country",
  birth_place: "drawer.checkinCapture.requiredFields.birthPlace",
  birth_country: "drawer.checkinCapture.requiredFields.birthCountry",
  marital_status: "drawer.checkinCapture.requiredFields.maritalStatus",
  occupation: "drawer.checkinCapture.requiredFields.occupation",
  terms_accepted: "drawer.checkinCapture.requiredFields.termsAccepted"
};

const getCheckinApiErrorDetail = (error: unknown): unknown => {
  if (!(error instanceof ApiError) || !error.payload || typeof error.payload !== "object") return null;
  return (error.payload as Record<string, unknown>).detail;
};

const isStructuredMissingGuestData = (detail: unknown): boolean => {
  if (!detail || typeof detail !== "object") return false;
  const record = detail as Record<string, unknown>;
  const code = typeof record.code === "string" ? record.code.toUpperCase() : "";
  const hasGuestDataCode = code.includes("GUEST_DATA") && (code.includes("MISSING") || code.includes("REQUIRED"));
  const describesGuestField = (value: unknown): boolean => {
    if (typeof value === "string") {
      return Boolean(checkinFieldKeysByName[value] || checkinValidationErrorKeys[value]);
    }
    if (!value || typeof value !== "object") return false;
    const item = value as Record<string, unknown>;
    const field = [item.field, item.name, item.path, ...(Array.isArray(item.loc) ? item.loc : [])]
      .find((part) => typeof part === "string" && checkinFieldKeysByName[part]);
    return typeof field === "string";
  };
  const structuredFields = [record.fields, record.errors].filter(Array.isArray).flat();
  return hasGuestDataCode || structuredFields.some(describesGuestField);
};

const getCheckinActionErrorMessage = (
  error: unknown,
  t: TFunction,
  balanceDue: number,
  currencyCode: string
): string => {
  const detail = getCheckinApiErrorDetail(error);
  const structuredMessage =
    detail && typeof detail === "object" && typeof (detail as Record<string, unknown>).message === "string"
      ? (detail as Record<string, unknown>).message as string
      : "";
  const message = typeof detail === "string" ? detail : structuredMessage;

  // Accept current English and localized API detail prefixes plus a structured field list,
  // while keeping the operator UI localized and independent of transport wording.
  if (isStructuredMissingGuestData(detail) || /missing required guest data|faltan datos obligatorios del huésped/i.test(message)) {
    return t("drawer.checkinCapture.submitMissingFields");
  }
  if (/must be paid first|debe abonarse/i.test(message)) {
    return t("drawer.errors.checkInPaymentRequired", {
      balance: formatMoney(Math.max(0, balanceDue), currencyCode)
    });
  }
  if (/after the reservation departure date|después de la fecha de salida/i.test(message)) {
    return t("drawer.errors.checkInDepartureDatePassed");
  }
  return t("drawer.errors.checkInFailed");
};

type Props = {
  reservationId: number | null;
  onClose: () => void;
};

const paymentMethodValues: PaymentMethod[] = [
  "cash",
  "bank_transfer",
  "credit_card",
  "debit_card"
];
const manualPaymentMethods: PaymentMethod[] = ["credit_card", "debit_card", "bank_transfer"];
type ExtensionManualPaymentMethod = Extract<PaymentMethod, "cash" | "credit_card" | "debit_card" | "bank_transfer">;
type IndividualExtensionPaymentAction = "payment_link" | "immediate_payment" | "pending_balance";

const mutatingExtensionImpactActions = new Set<ReservationExtensionImpactAction["action"]>([
  "moved_equivalent",
  "moved_superior",
  "assignment_released"
]);

function hasBlockedExtensionImpact(impactPlan?: ReservationExtensionImpactPlan | null): boolean {
  return Boolean(impactPlan?.actions.some((item) => item.action === "blocked"));
}

function hasMutatingExtensionImpact(impactPlan?: ReservationExtensionImpactPlan | null): boolean {
  return Boolean(impactPlan?.actions.some((item) => mutatingExtensionImpactActions.has(item.action)));
}

function extensionImpactSummary(t: TFunction, impactPlan?: ReservationExtensionImpactPlan | null): string {
  if (!impactPlan) return t("drawer.extensionImpact.noMovements");
  if (impactPlan.actions.length === 0) return t("drawer.extensionImpact.noMovements");

  return impactPlan.actions.map((item) => {
    const action = t(`drawer.extensionImpact.actions.${item.action}`);
    const room = item.room_label || t("drawer.extensionImpact.unknownRoom");
    const dates = `${item.check_in_date} → ${item.check_out_date}`;
    const confirmation = item.confirmation_code
      ? ` (${t("drawer.extensionImpact.confirmationCode", { code: item.confirmation_code })})`
      : "";
    return `${action}: ${room}, ${dates}${confirmation}`;
  }).join("; ");
}

function extensionImpactMessage(
  t: TFunction,
  baseMessage: string,
  impactPlan?: ReservationExtensionImpactPlan | null
): string {
  return `${baseMessage} ${t("drawer.extensionImpact.title")}: ${extensionImpactSummary(t, impactPlan)}`;
}

function isCurrentExtensionPreview(
  preview: ReservationExtensionPreview,
  reservationId: number,
  currentCheckoutDate: string,
  newCheckoutDate: string,
  currentVersion: number,
  allowZeroAmount: boolean
): boolean {
  const amount = preview.extension_amount == null ? null : Number(preview.extension_amount);
  return preview.reservation_id === reservationId &&
    preview.current_checkout_date === currentCheckoutDate &&
    preview.new_checkout_date === newCheckoutDate &&
    preview.client_version === currentVersion &&
    Number.isInteger(preview.client_version) &&
    (allowZeroAmount
      ? amount === null || (Number.isFinite(amount) && amount >= 0)
      : amount !== null && Number.isFinite(amount) && amount > 0) &&
    (!preview.impact_plan || (
      typeof preview.impact_plan.fingerprint === "string" &&
      preview.impact_plan.fingerprint.length > 0 &&
      Array.isArray(preview.impact_plan.actions)
    ));
}

function guestFullName(
  t: TFunction,
  guest?: { first_name: string; last_name: string } | null,
  fallbackId?: number
) {
  if (guest) return `${guest.first_name} ${guest.last_name}`.trim();
  return fallbackId ? t("drawer.guests.guestFallbackWithId", { id: fallbackId }) : t("drawer.guests.guestFallbackNone");
}

function addIsoDays(isoDate: string, dayCount: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + dayCount);
  return date.toISOString().slice(0, 10);
}

function isValidPaymentEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function effectiveCompanyNightlyRate(rates: CompanyNightlyRate[], stayDate: string): CompanyNightlyRate | null {
  return rates.reduce<CompanyNightlyRate | null>((effective, rate) => {
    if (rate.effective_from > stayDate) return effective;
    if (
      !effective ||
      rate.effective_from > effective.effective_from ||
      (rate.effective_from === effective.effective_from && rate.id > effective.id)
    ) {
      return rate;
    }
    return effective;
  }, null);
}

export function ReservationDetailDrawer({ reservationId, onClose }: Props) {
  const { t } = useTranslation("reservations");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [cashReceivedAmountInput, setCashReceivedAmountInput] = useState("");
  const [cashTipAmountInput, setCashTipAmountInput] = useState("");
  const [paymentReferenceInput, setPaymentReferenceInput] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [captureForm, setCaptureForm] = useState<CheckinCaptureForm>(emptyCaptureForm);
  const [companyExtensionNote, setCompanyExtensionNote] = useState("");
  const [companyExtensionCheckoutDate, setCompanyExtensionCheckoutDate] = useState("");
  const [companyExtensionPreview, setCompanyExtensionPreview] = useState<ReservationExtensionPreview | null>(null);
  const [companyExtensionPreviewPending, setCompanyExtensionPreviewPending] = useState(false);
  const [companyExtensionConfirmOpen, setCompanyExtensionConfirmOpen] = useState(false);
  const [individualExtensionCheckoutDate, setIndividualExtensionCheckoutDate] = useState("");
  const [individualExtensionPaymentAction, setIndividualExtensionPaymentAction] =
    useState<IndividualExtensionPaymentAction>("payment_link");
  const [individualExtensionPaymentMethod, setIndividualExtensionPaymentMethod] =
    useState<ExtensionManualPaymentMethod>("cash");
  const [individualExtensionManualReference, setIndividualExtensionManualReference] = useState("");
  const [individualExtensionCashReceivedAmountInput, setIndividualExtensionCashReceivedAmountInput] = useState("");
  const [individualExtensionCashTipAmountInput, setIndividualExtensionCashTipAmountInput] = useState("");
  const [individualExtensionRecipientEmail, setIndividualExtensionRecipientEmail] = useState("");
  const [individualExtensionPreview, setIndividualExtensionPreview] = useState<ReservationExtensionPreview | null>(null);
  const [individualExtensionPreviewPending, setIndividualExtensionPreviewPending] = useState(false);
  const [individualExtensionConfirmOpen, setIndividualExtensionConfirmOpen] = useState(false);
  const [individualExtensionCreatedLink, setIndividualExtensionCreatedLink] = useState<{
    external_checkout_url?: string | null;
    execution_mode: "local_only" | "provider";
    payable: boolean;
  } | null>(null);
  const expectedIndividualExtensionDateRef = useRef<{
    reservationId: number;
    checkoutDate: string;
  } | null>(null);
  const [companionForm, setCompanionForm] = useState({ first_name: "", last_name: "", document_number: "" });
  const [companionError, setCompanionError] = useState<string | null>(null);
  const [selectedCompanyChargeIds, setSelectedCompanyChargeIds] = useState<number[]>([]);
  const [selectedCompanyChargeDates, setSelectedCompanyChargeDates] = useState<string[]>([]);
  const [companyExtraPersonCount, setCompanyExtraPersonCount] = useState("1");
  const [selectedCompanyCorrectionIds, setSelectedCompanyCorrectionIds] = useState<number[]>([]);
  const [companyCorrectionAmounts, setCompanyCorrectionAmounts] = useState<Record<number, string>>({});
  const [companyCorrectionReason, setCompanyCorrectionReason] = useState("");
  const [companyVoucherFile, setCompanyVoucherFile] = useState<File | null>(null);
  const [companyVoucherFeedback, setCompanyVoucherFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const companyVoucherFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setActionError(null);
    setActionMessage(null);
    setPaymentAmount("");
    setCashReceivedAmountInput("");
    setCashTipAmountInput("");
    setCaptureForm(emptyCaptureForm);
    setCompanyExtensionPreview(null);
    setCompanyExtensionConfirmOpen(false);
    setIndividualExtensionPreview(null);
    setIndividualExtensionConfirmOpen(false);
    setIndividualExtensionCreatedLink(null);
    expectedIndividualExtensionDateRef.current = null;
    setCompanyVoucherFile(null);
    setCompanyVoucherFeedback(null);
    if (companyVoucherFileInputRef.current) companyVoucherFileInputRef.current.value = "";
  }, [reservationId]);

  const reservationQuery = useReservation(reservationId ?? undefined);
  const queryClient = useQueryClient();
  const { session } = useSession();
  const operationsQuery = useReservationOperationsSummary(reservationId ?? undefined);
  const summaryQuery = usePaymentSummary(reservationId ?? undefined);
  const paymentMutation = usePaymentMutation(reservationId ?? undefined);
  const individualExtensionMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReservationExtensionPayload }) =>
      extendReservationStay(id, payload, session),
    onSuccess: async (_, variables) => Promise.all([
      refreshPaymentState(queryClient, session.hotelId, variables.id),
      refreshReservationRecordState(queryClient, session.hotelId, variables.id, { includePaymentLinks: true })
    ])
  });
  const companyNightChargesQuery = useCompanyNightCharges(reservationId ?? undefined, Boolean(reservationQuery.data?.company_id));
  const refreshCompanyNightCharges = () => {
    if (!reservationId) return;
    invalidateQueriesInBackground(queryClient, {
      queryKey: ["company-night-charges", session.hotelId, reservationId]
    });
    void refreshPaymentState(queryClient, session.hotelId, reservationId).catch(() => undefined);
  };
  const createCompanyNightChargesMutation = useGuardedMutation({
    mutationFn: ({ stayDates, extraPersonCount }: { stayDates: string[]; extraPersonCount: number }) => {
      if (!reservationId) throw new Error("No reservation selected");
      return createCompanyNightCharges(reservationId, stayDates, session, extraPersonCount);
    },
    onSuccess: refreshCompanyNightCharges
  });
  const correctCompanyNightChargesMutation = useGuardedMutation({
    mutationFn: (items: CompanyNightChargeCorrection[]) => {
      if (!reservationId) throw new Error("No reservation selected");
      return correctCompanyNightChargeAmounts(reservationId, items, session);
    },
    onSuccess: refreshCompanyNightCharges
  });
  const { hasPermission, permissionsKnown } = useEffectivePermissions();
  const canReadCompanyDocuments = permissionsKnown && hasPermission("company:documents:read");
  const companyDocumentsQuery = useReservationCompanyDocuments(
    reservationQuery.data?.company_id && canReadCompanyDocuments ? reservationId ?? undefined : undefined
  );
  const companyDocumentMutations = useCompanyDocumentMutations(reservationQuery.data?.company_id ?? undefined);
  const markCompanyDocumentSignedMutation = useMarkCompanyDocumentSigned();
  const paymentSurchargesQuery = usePaymentSurcharges({
    enabled: Boolean(reservationId && hasPermission("cash:operate"))
  });
  const canManageCompanyCharges = hasPermission("company:manage");
  const canReviewCompanyTerms = permissionsKnown
    && canManageCompanyCharges
    && hasPermission("reservation:read");
  const companyNightlyRatesQuery = useCompanyNightlyRates(
    reservationQuery.data?.company_id ?? undefined,
    Boolean(reservationId && canManageCompanyCharges)
  );
  const canApplyCompanyExtension = hasPermission("reservation:update") && canManageCompanyCharges;
  const {
    cancelMutation,
    checkInMutation,
    partialCheckInMutation,
    checkOutMutation,
    addGuestsMutation,
    companyExtensionRequestMutation,
    companyAccountExtensionMutation
  } =
    useReservationMutations();
  const restrictionOverridePrompt = useRestrictionOverridePrompt();

  const open = Boolean(reservationId);
  const reservation = reservationQuery.data;
  const operations = operationsQuery.data;
  const summary = summaryQuery.data;
  const deferredCompanyBilling = isDeferredCompanyReservation(reservation);
  const hasPaymentHistory = (summary?.completed_payments ?? 0) > 0;
  const canCancelBase = hasPermission("reservation:cancel");
  const canCancelPaid = !hasPaymentHistory || hasPermission("reservation:cancel_paid");
  const canManageCompanyReservation = !reservation?.company_id || canManageCompanyCharges;
  const cancellationRequirementsKnown = permissionsKnown && summaryQuery.isSuccess;
  const canCancelAsCurrentRole = cancellationRequirementsKnown && canCancelBase && canCancelPaid && canManageCompanyReservation;
  const canRequestTemporaryCancel = cancellationRequirementsKnown && !canCancelBase && !hasPaymentHistory && !reservation?.company_id;

  // Load and validate check-in data for every pre-arrival reservation state.
  // Payment eligibility is enforced by the backend's hotel policy; a balance
  // must not hide the guest fields needed to complete check-in.
  const checkinDataRelevant = Boolean(reservation) && (
    canCheckInReservation(reservation!.status)
    || reservation?.settlement_status === "deferred"
  );
  const guestQuery = useGuest(checkinDataRelevant ? reservation?.guest_id : undefined);
  const checkinValidation = useValidateGuestCheckin(checkinDataRelevant ? reservation?.guest_id : undefined);
  const needsCheckinCapture = checkinDataRelevant && checkinValidation.data?.valid === false;
  const checkinDataLoading = checkinDataRelevant && (
    guestQuery.isLoading || guestQuery.isFetching || checkinValidation.isLoading || checkinValidation.isFetching
  );
  const checkinDataError = checkinDataRelevant && (guestQuery.isError || checkinValidation.isError);
  const checkinDataReady = !checkinDataRelevant || (
    guestQuery.isSuccess && checkinValidation.isSuccess && !checkinDataLoading && !checkinDataError
  );
  const localizedCheckinErrors = (checkinValidation.data?.errors ?? []).map((error) => {
    const key = checkinValidationErrorKeys[error];
    return key ? t(key) : t("drawer.checkinCapture.requiredFields.unknown");
  });
  const pendingActionMessage = individualExtensionMutation.isPending
    ? t("drawer.individualExtension.applying")
    : paymentMutation.isPending
    ? t("drawer.payment.submitting")
    : partialCheckInMutation.isPending
      ? t("drawer.actions.partialCheckInPending")
      : checkInMutation.isPending
        ? t("drawer.actions.confirmCheckInPending")
        : checkOutMutation.isPending
          ? t("drawer.actions.checkOutPending")
          : cancelMutation.isPending
            ? t("drawer.actions.cancelPending")
            : null;

  useEffect(() => {
    if (!guestQuery.data) return;
    setCaptureForm({
      document_type: guestQuery.data.document_type ?? "",
      document_number: guestQuery.data.document_number ?? "",
      nationality: guestQuery.data.nationality ?? "",
      country: guestQuery.data.country ?? "",
      birth_place: guestQuery.data.birth_place ?? "",
      birth_country: guestQuery.data.birth_country ?? "",
      marital_status: guestQuery.data.marital_status ?? "",
      occupation: guestQuery.data.occupation ?? "",
      // Consent applies to the current check-in. A saved guest profile must
      // not silently accept terms for a new stay.
      terms_accepted: false
    });
  }, [guestQuery.data]);

  useEffect(() => {
    setCompanyExtensionNote(reservation?.company_extension_request_note ?? "");
  }, [reservation?.id, reservation?.company_extension_request_note]);

  const currentReservationId = reservation?.id;
  const currentReservationCheckoutDate = reservation?.check_out_date;

  useEffect(() => {
    const expectedExtension = expectedIndividualExtensionDateRef.current;
    const isAppliedExtensionDate = Boolean(
      currentReservationId != null &&
      expectedExtension?.reservationId === currentReservationId &&
      expectedExtension.checkoutDate === currentReservationCheckoutDate
    );
    if (isAppliedExtensionDate) expectedIndividualExtensionDateRef.current = null;

    setCompanyExtensionCheckoutDate(
      currentReservationCheckoutDate ? addIsoDays(currentReservationCheckoutDate, 1) : ""
    );
    setCompanyExtensionConfirmOpen(false);
    setIndividualExtensionCheckoutDate(
      currentReservationCheckoutDate ? addIsoDays(currentReservationCheckoutDate, 1) : ""
    );
    setIndividualExtensionPaymentAction("payment_link");
    setIndividualExtensionPaymentMethod("cash");
    setIndividualExtensionManualReference("");
    setIndividualExtensionCashReceivedAmountInput("");
    setIndividualExtensionCashTipAmountInput("");
    setIndividualExtensionRecipientEmail("");
    setIndividualExtensionPreview(null);
    setIndividualExtensionPreviewPending(false);
    setIndividualExtensionConfirmOpen(false);
    if (!isAppliedExtensionDate) setIndividualExtensionCreatedLink(null);
  }, [currentReservationId, currentReservationCheckoutDate]);

  const buildGuestPatch = (): GuestUpdatePayload => ({
    document_type: captureForm.document_type || undefined,
    document_number: captureForm.document_number.trim() || undefined,
    nationality: captureForm.nationality.trim() || undefined,
    country: captureForm.country.trim() || undefined,
    birth_place: captureForm.birth_place.trim() || undefined,
    birth_country: captureForm.birth_country.trim() || undefined,
    marital_status: captureForm.marital_status.trim() || undefined,
    occupation: captureForm.occupation.trim() || undefined,
    terms_accepted: captureForm.terms_accepted
  });

  const handleAddCompanion = async () => {
    if (!reservationId) return;
    if (!companionForm.first_name.trim() || !companionForm.last_name.trim()) {
      setCompanionError(t("drawer.errors.companionRequired"));
      return;
    }
    setCompanionError(null);
    try {
      await addGuestsMutation.mutateAsync({
        id: reservationId,
        guests: [
          {
            first_name: companionForm.first_name.trim(),
            last_name: companionForm.last_name.trim(),
            document_number: companionForm.document_number.trim() || undefined
          }
        ]
      });
      setCompanionForm({ first_name: "", last_name: "", document_number: "" });
    } catch (err) {
      setCompanionError(err instanceof ApiError ? err.message : t("drawer.errors.addCompanionFailed"));
    }
  };
  // Bug documented in frontend/src/api/payments.ts: total_amount/balance_due
  // ignore consumption charges. Always prefer the operational figures for
  // anything the operator will actually collect.
  const currencyCode = normalizeCurrencyCode(summary?.currency_code ?? reservation?.currency_code);
  const extensionPaymentSurcharge = (paymentSurchargesQuery.data ?? []).find(
    (surcharge) => surcharge.payment_method === individualExtensionPaymentMethod && surcharge.is_active
  ) ?? null;
  const operationalBalanceDue = summary?.operational_balance_due ?? summary?.balance_due;
  const companyNightCharges = companyNightChargesQuery.data;
  const companyChargeRows = companyNightCharges?.charges ?? [];
  const chargedCompanyDates = new Set(companyChargeRows.map((charge) => charge.stay_date));
  const outstandingCompanyCharges = companyChargeRows.filter((charge) => Number(charge.remaining_due) > 0.01);
  const selectedCompanyCorrectionRows = companyChargeRows.filter((charge) =>
    selectedCompanyCorrectionIds.includes(charge.id)
  );
  const hasInvalidCompanyCorrectionAmount = selectedCompanyCorrectionRows.some((charge) => {
    const amount = Number(companyCorrectionAmounts[charge.id]);
    return !Number.isFinite(amount) || amount <= 0 || Math.round(amount * 100) === Math.round(Number(charge.amount) * 100);
  });
  const companyNightPaidTotal = companyChargeRows.reduce((total, charge) => total + Number(charge.paid_amount), 0);
  const companyBasePaid = Math.max(0, Number(summary?.amount_paid ?? 0) - companyNightPaidTotal);
  const companyBaseBalanceDue = Math.max(0, Number(summary?.total_amount ?? 0) - companyBasePaid);
  const selectedCompanyChargeTotal = outstandingCompanyCharges
    .filter((charge) => selectedCompanyChargeIds.includes(charge.id) && !charge.review_only && !charge.payment_pending)
    .reduce((total, charge) => total + Number(charge.remaining_due), 0);
  const paymentCashPreviewBase = Number(paymentAmount) > 0
    ? Number(paymentAmount)
    : selectedCompanyChargeIds.length > 0
      ? selectedCompanyChargeTotal
      : Number(operationalBalanceDue ?? 0);
  const paymentQuoteQuery = usePaymentSurchargeQuote(
    reservation && Number.isFinite(paymentCashPreviewBase) && paymentCashPreviewBase > 0
      ? {
          reservation_id: reservation.id,
          payment_method: paymentMethod,
          currency_code: currencyCode,
          base_amount: paymentCashPreviewBase
        }
      : null,
    {
      enabled: Boolean(
        reservation &&
        Number.isFinite(paymentCashPreviewBase) &&
        paymentCashPreviewBase > 0 &&
        hasPermission("cash:operate")
      )
    }
  );
  const paymentQuote = paymentQuoteQuery.data;
  const paymentCashPreviewTotal = paymentQuote ? Number(paymentQuote.final_amount) : 0;
  const extensionCashPreviewBase = Number(individualExtensionPreview?.extension_amount ?? 0);
  const extensionCashPreviewTotal = grossWithSurcharge(extensionCashPreviewBase, extensionPaymentSurcharge);
  const hasUnpaidCompanyCharges = outstandingCompanyCharges.length > 0;
  const isManualPaymentMethod = manualPaymentMethods.includes(paymentMethod);
  const canSignCompanyDocuments = hasPermission("checkin:perform") && canReadCompanyDocuments;
  const canApplyPendingCompanyExtension = Boolean(
    reservation?.company_id &&
    reservation.status === "checked_in" &&
    reservation.company_extension_request_pending &&
    reservation.settlement_status === "deferred" &&
    canApplyCompanyExtension
  );
  const canCollectExtension = hasPermission("reservation:charge") && hasPermission("cash:operate");
  const canExtendIndividualReservation = Boolean(
    reservation &&
    !reservation.company_id &&
    !reservation.group_id &&
    reservation.source === "direct" &&
    !reservation.external_id &&
    !reservation.source_provider_code &&
    operationsQuery.isSuccess &&
    !operations?.ota_link &&
    !deferredCompanyBilling &&
    (reservation.status === "checked_in" || reservation.status === "fully_paid") &&
    hasPermission("reservation:update")
  );
  useEffect(() => {
    if (!canCollectExtension) setIndividualExtensionPaymentAction("pending_balance");
  }, [canCollectExtension]);
  const candidateCompanyChargeDates: string[] = [];
  if (reservation?.check_in_date && reservation.check_out_date) {
    const current = new Date(`${reservation.check_in_date}T00:00:00Z`);
    const checkout = new Date(`${reservation.check_out_date}T00:00:00Z`);
    while (current < checkout && candidateCompanyChargeDates.length < 90) {
      candidateCompanyChargeDates.push(current.toISOString().slice(0, 10));
      current.setUTCDate(current.getUTCDate() + 1);
    }
  }
  const companyNightlyRates = companyNightlyRatesQuery.data?.rates ?? [];
  const chargeableCompanyChargeOptions = candidateCompanyChargeDates.flatMap((stayDate) => {
    const rate = effectiveCompanyNightlyRate(companyNightlyRates, stayDate);
    return rate && Number.isFinite(Number(rate.amount)) && Number(rate.amount) > 0
      ? [{ stayDate, rate }]
      : [];
  });

  useEffect(() => {
    setSelectedCompanyChargeIds([]);
    setSelectedCompanyChargeDates([]);
    setCompanyExtraPersonCount("1");
    setSelectedCompanyCorrectionIds([]);
    setCompanyCorrectionAmounts({});
    setCompanyCorrectionReason("");
    setPaymentAmount("");
    setPaymentReferenceInput("");
  }, [reservationId]);

  useEffect(() => {
    if (selectedCompanyChargeIds.length > 0) {
      setPaymentAmount(selectedCompanyChargeTotal.toFixed(2));
    } else {
      setPaymentAmount("");
    }
  }, [selectedCompanyChargeIds, selectedCompanyChargeTotal]);

  const handleCreateCompanyNightCharges = async () => {
    if (!reservationId || selectedCompanyChargeDates.length === 0) return;
    const extraPersonCount = Number(companyExtraPersonCount);
    if (!Number.isInteger(extraPersonCount) || extraPersonCount < 1 || extraPersonCount > 99) {
      setActionError(t("drawer.companyCharges.invalidPersonCount"));
      return;
    }
    setActionError(null);
    setActionMessage(null);
    try {
      await createCompanyNightChargesMutation.mutateAsync({
        stayDates: selectedCompanyChargeDates,
        extraPersonCount
      });
      setSelectedCompanyChargeDates([]);
      setActionMessage(t("drawer.companyCharges.created"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyCharges.createFailed"));
    }
  };

  const handleCorrectCompanyNightCharges = async () => {
    if (!reservationId || selectedCompanyCorrectionRows.length === 0) return;
    const reason = companyCorrectionReason.trim();
    if (!reason) {
      setActionError(t("drawer.companyCharges.correctionReasonRequired"));
      return;
    }
    if (hasInvalidCompanyCorrectionAmount) {
      setActionError(t("drawer.companyCharges.correctionAmountInvalid"));
      return;
    }

    const items = selectedCompanyCorrectionRows.map((charge) => ({
      charge_id: charge.id,
      new_amount: Number(companyCorrectionAmounts[charge.id]),
      reason
    }));
    setActionError(null);
    setActionMessage(null);
    try {
      await correctCompanyNightChargesMutation.mutateAsync(items);
      setSelectedCompanyCorrectionIds([]);
      setCompanyCorrectionAmounts({});
      setCompanyCorrectionReason("");
      setSelectedCompanyChargeIds([]);
      setPaymentAmount("");
      setActionMessage(t("drawer.companyCharges.corrected"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyCharges.correctionFailed"));
    }
  };

  const handleOpenCompanyDocument = async (documentId: number) => {
    const documentTab = window.open("about:blank", "_blank");
    if (!documentTab) {
      setActionError(t("drawer.companyDocuments.openFailed"));
      return;
    }
    documentTab.opener = null;
    try {
      const objectUrl = await fetchCompanyDocumentFile(documentId, session);
      documentTab.location.href = objectUrl;
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (err) {
      documentTab.close();
      setActionError(err instanceof Error ? err.message : t("drawer.companyDocuments.openFailed"));
    }
  };

  const handleCompanyVoucherFileChange = (file: File | null) => {
    setCompanyVoucherFeedback(null);
    if (!file) {
      setCompanyVoucherFile(null);
      return;
    }

    const hasPdfName = file.name.toLocaleLowerCase().endsWith(".pdf");
    const hasCompatibleMimeType = !file.type || file.type === "application/pdf";
    if (!hasPdfName || !hasCompatibleMimeType) {
      setCompanyVoucherFile(null);
      if (companyVoucherFileInputRef.current) companyVoucherFileInputRef.current.value = "";
      setCompanyVoucherFeedback({ kind: "error", message: t("drawer.companyDocuments.pdfOnly") });
      return;
    }
    if (file.size <= 0 || file.size > MAX_COMPANY_VOUCHER_PDF_BYTES) {
      setCompanyVoucherFile(null);
      if (companyVoucherFileInputRef.current) companyVoucherFileInputRef.current.value = "";
      setCompanyVoucherFeedback({ kind: "error", message: t("drawer.companyDocuments.pdfSizeInvalid") });
      return;
    }

    setCompanyVoucherFile(file);
  };

  const handleUploadCompanyVoucher = async () => {
    if (!reservationId || !reservation?.company_id || !canManageCompanyCharges) return;
    if (!companyVoucherFile) {
      setCompanyVoucherFeedback({ kind: "error", message: t("drawer.companyDocuments.fileRequired") });
      return;
    }

    const file = companyVoucherFile;
    setCompanyVoucherFeedback(null);
    try {
      const contentBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Could not read the PDF."));
        reader.readAsDataURL(file);
      });
      await companyDocumentMutations.uploadDocumentMutation.mutateAsync({
        reservation_id: reservationId,
        company_id: reservation.company_id,
        doc_type: "voucher_pdf",
        file_name: file.name,
        content_base64: contentBase64,
        requires_signature: false
      });
      setCompanyVoucherFile(null);
      if (companyVoucherFileInputRef.current) companyVoucherFileInputRef.current.value = "";

      const refreshedDocuments = await companyDocumentsQuery.refetch();
      setCompanyVoucherFeedback(refreshedDocuments.isError
        ? { kind: "error", message: t("drawer.companyDocuments.uploadedRefreshFailed") }
        : { kind: "success", message: t("drawer.companyDocuments.uploaded") });
    } catch {
      setCompanyVoucherFeedback({ kind: "error", message: t("drawer.companyDocuments.uploadFailed") });
    }
  };

  const handleMarkCompanyDocumentSigned = async (documentId: number) => {
    setActionError(null);
    setActionMessage(null);
    try {
      await markCompanyDocumentSignedMutation.mutateAsync(documentId);
      setActionMessage(t("drawer.companyDocuments.markedSigned"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyDocuments.signFailed"));
    }
  };

  const handleCompanyExtensionRequest = async () => {
    if (!reservationId || !reservation) return;
    const note = companyExtensionNote.trim();
    if (!note) {
      setActionError(t("drawer.companyExtension.noteRequired"));
      return;
    }
    setActionError(null);
    setActionMessage(null);
    try {
      await companyExtensionRequestMutation.mutateAsync({
        id: reservation.id,
        payload: {
          pending: true,
          note,
          client_version: reservation.version ?? 0
        }
      });
      setActionMessage(t("drawer.companyExtension.saved"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyExtension.saveFailed"));
    }
  };

  const handleOpenCompanyExtensionConfirmation = async () => {
    if (!reservation || !companyExtensionCheckoutDate) return;
    if (companyExtensionCheckoutDate <= reservation.check_out_date) {
      setActionError(t("drawer.companyExtension.checkoutDateMustBeLater"));
      setActionMessage(null);
      return;
    }
    setActionError(null);
    setActionMessage(null);
    setCompanyExtensionPreview(null);
    setCompanyExtensionConfirmOpen(false);
    setCompanyExtensionPreviewPending(true);
    try {
      const preview = await previewReservationStayExtension(
        reservation.id,
        companyExtensionCheckoutDate,
        "company_account",
        session
      );
      if (!isCurrentExtensionPreview(
        preview,
        reservation.id,
        reservation.check_out_date,
        companyExtensionCheckoutDate,
        reservation.version ?? 0,
        true
      )) {
        throw new Error(t("drawer.companyExtension.previewStale"));
      }
      setCompanyExtensionPreview(preview);
      if (hasBlockedExtensionImpact(preview.impact_plan)) {
        setActionError(t("drawer.extensionImpact.manualResolutionRequired"));
        return;
      }
      setCompanyExtensionConfirmOpen(true);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyExtension.previewFailed"));
    } finally {
      setCompanyExtensionPreviewPending(false);
    }
  };

  const handleApplyCompanyExtension = async () => {
    if (
      !reservation ||
      !canApplyPendingCompanyExtension ||
      !companyExtensionPreview ||
      !companyExtensionCheckoutDate ||
      !isCurrentExtensionPreview(
        companyExtensionPreview,
        reservation.id,
        reservation.check_out_date,
        companyExtensionCheckoutDate,
        reservation.version ?? 0,
        true
      ) ||
      hasBlockedExtensionImpact(companyExtensionPreview.impact_plan)
    ) {
      setCompanyExtensionConfirmOpen(false);
      setActionError(t("drawer.companyExtension.previewStale"));
      return;
    }
    const confirmedImpactFingerprint = hasMutatingExtensionImpact(companyExtensionPreview.impact_plan)
      ? companyExtensionPreview.impact_plan?.fingerprint
      : undefined;
    if (hasMutatingExtensionImpact(companyExtensionPreview.impact_plan) && !confirmedImpactFingerprint) {
      setCompanyExtensionConfirmOpen(false);
      setActionError(t("drawer.companyExtension.previewStale"));
      return;
    }
    setCompanyExtensionConfirmOpen(false);
    setActionError(null);
    setActionMessage(null);
    try {
      await companyAccountExtensionMutation.mutateAsync({
        id: reservation.id,
        payload: {
          new_checkout_date: companyExtensionCheckoutDate,
          client_version: reservation.version ?? 0,
          pricing_mode: "current_rate",
          payment_action: "company_account",
          ...(confirmedImpactFingerprint ? { confirmed_impact_fingerprint: confirmedImpactFingerprint } : {})
        }
      });
      setCompanyExtensionPreview(null);
      setActionMessage(t("drawer.companyExtension.applied"));
    } catch (err) {
      setCompanyExtensionConfirmOpen(false);
      setCompanyExtensionPreview(null);
      setActionError(err instanceof ApiError ? err.message : t("drawer.companyExtension.applyFailed"));
    }
  };

  const handlePreviewIndividualExtension = async () => {
    if (!reservation || !canExtendIndividualReservation) return;
    if (individualExtensionCheckoutDate <= reservation.check_out_date) {
      setActionError(t("drawer.individualExtension.checkoutDateMustBeLater"));
      setActionMessage(null);
      return;
    }
    if (
      individualExtensionPaymentAction === "immediate_payment" &&
      manualPaymentMethods.includes(individualExtensionPaymentMethod) &&
      !individualExtensionManualReference.trim()
    ) {
      setActionError(t("drawer.individualExtension.manualReferenceRequired"));
      setActionMessage(null);
      return;
    }
    if (
      individualExtensionPaymentAction === "payment_link" &&
      !isValidPaymentEmail(individualExtensionRecipientEmail)
    ) {
      setActionError(t("drawer.individualExtension.recipientEmailInvalid"));
      setActionMessage(null);
      return;
    }

    setActionError(null);
    setActionMessage(null);
    setIndividualExtensionCreatedLink(null);
    setIndividualExtensionPreview(null);
    setIndividualExtensionCashReceivedAmountInput("");
    setIndividualExtensionCashTipAmountInput("");
    setIndividualExtensionConfirmOpen(false);
    setIndividualExtensionPreviewPending(true);
    try {
      const preview = await previewReservationStayExtension(
        reservation.id,
        individualExtensionCheckoutDate,
        "individual",
        session
      );
      if (!isCurrentExtensionPreview(
        preview,
        reservation.id,
        reservation.check_out_date,
        individualExtensionCheckoutDate,
        reservation.version ?? 0,
        false
      )) {
        throw new Error(t("drawer.individualExtension.previewStale"));
      }
      setIndividualExtensionPreview(preview);
      if (hasBlockedExtensionImpact(preview.impact_plan)) {
        setActionError(t("drawer.extensionImpact.manualResolutionRequired"));
        return;
      }
      setIndividualExtensionConfirmOpen(!(
        individualExtensionPaymentAction === "immediate_payment" &&
        individualExtensionPaymentMethod === "cash"
      ));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.individualExtension.previewFailed"));
    } finally {
      setIndividualExtensionPreviewPending(false);
    }
  };

  const handleOpenIndividualExtensionConfirmation = () => {
    if (!individualExtensionPreview) return;
    if (
      individualExtensionPaymentAction === "immediate_payment" &&
      individualExtensionPaymentMethod === "cash"
    ) {
      const expectedCashAmount = grossWithSurcharge(
        Number(individualExtensionPreview.extension_amount),
        extensionPaymentSurcharge
      );
      const cashTender = calculateCashTender(individualExtensionCashReceivedAmountInput, expectedCashAmount);
      if (!cashTender.valid) {
        setActionError(
          cashTender.reason === "insufficient"
            ? t("page.form.cashReceivedInsufficient", {
                amount: formatMoney(expectedCashAmount, individualExtensionPreview.currency_code)
              })
            : t("page.form.cashReceivedInvalid")
        );
        return;
      }
      const cashTip = calculateCashTip(
        individualExtensionCashTipAmountInput,
        cashTender.changeAmount ?? 0
      );
      if (!cashTip.valid) {
        setActionError(t("page.form.cashTipInvalid"));
        return;
      }
    }
    setActionError(null);
    setIndividualExtensionConfirmOpen(true);
  };

  const handleConfirmIndividualExtension = async () => {
    if (!reservation || !individualExtensionPreview || individualExtensionMutation.isPending) return;
    if (!isCurrentExtensionPreview(
      individualExtensionPreview,
      reservation.id,
      reservation.check_out_date,
      individualExtensionCheckoutDate,
      reservation.version ?? 0,
      false
    ) || hasBlockedExtensionImpact(individualExtensionPreview.impact_plan)) {
      setActionError(t("drawer.individualExtension.previewStale"));
      setIndividualExtensionConfirmOpen(false);
      setIndividualExtensionPreview(null);
      setIndividualExtensionCashReceivedAmountInput("");
      setIndividualExtensionCashTipAmountInput("");
      return;
    }
    const confirmedImpactFingerprint = hasMutatingExtensionImpact(individualExtensionPreview.impact_plan)
      ? individualExtensionPreview.impact_plan?.fingerprint
      : undefined;
    if (hasMutatingExtensionImpact(individualExtensionPreview.impact_plan) && !confirmedImpactFingerprint) {
      setActionError(t("drawer.individualExtension.previewStale"));
      setIndividualExtensionConfirmOpen(false);
      setIndividualExtensionPreview(null);
      return;
    }
    const amount = Number(individualExtensionPreview.extension_amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setActionError(t("drawer.individualExtension.previewFailed"));
      setIndividualExtensionConfirmOpen(false);
      setIndividualExtensionPreview(null);
      return;
    }
    const expectedCashAmount = grossWithSurcharge(amount, extensionPaymentSurcharge);
    const extensionCashTender = individualExtensionPaymentAction === "immediate_payment" && individualExtensionPaymentMethod === "cash"
      ? calculateCashTender(individualExtensionCashReceivedAmountInput, expectedCashAmount)
      : null;
    if (extensionCashTender && (!extensionCashTender.valid || extensionCashTender.receivedAmount === null)) {
      setActionError(
        extensionCashTender.reason === "insufficient"
          ? t("page.form.cashReceivedInsufficient", {
              amount: formatMoney(expectedCashAmount, individualExtensionPreview.currency_code)
            })
          : t("page.form.cashReceivedInvalid")
      );
      setIndividualExtensionConfirmOpen(false);
      return;
    }
    const extensionCashTip = extensionCashTender
      ? calculateCashTip(individualExtensionCashTipAmountInput, extensionCashTender.changeAmount ?? 0)
      : null;
    if (extensionCashTip && (!extensionCashTip.valid || extensionCashTip.tipAmount === null)) {
      setActionError(t("page.form.cashTipInvalid"));
      setIndividualExtensionConfirmOpen(false);
      return;
    }

    const payload: ReservationExtensionPayload = {
      new_checkout_date: individualExtensionPreview.new_checkout_date,
      client_version: individualExtensionPreview.client_version,
      pricing_mode: "current_rate",
      payment_action: individualExtensionPaymentAction,
      ...(confirmedImpactFingerprint ? { confirmed_impact_fingerprint: confirmedImpactFingerprint } : {})
    };
    if (individualExtensionPaymentAction === "immediate_payment") {
      const manualReference = individualExtensionManualReference.trim();
      if (manualPaymentMethods.includes(individualExtensionPaymentMethod) && !manualReference) {
        setActionError(t("drawer.individualExtension.manualReferenceRequired"));
        setIndividualExtensionConfirmOpen(false);
        setIndividualExtensionPreview(null);
        return;
      }
      payload.immediate_payment = {
        reservation_id: reservation.id,
        amount,
        payment_method: individualExtensionPaymentMethod,
        transaction_type: "balance_payment",
        currency: individualExtensionPreview.currency_code,
        ...(extensionCashTender?.receivedAmount !== null && extensionCashTender?.receivedAmount !== undefined
          ? { cash_received_amount: extensionCashTender.receivedAmount }
          : {}),
        ...(extensionCashTip?.tipAmount !== null && extensionCashTip?.tipAmount !== undefined && extensionCashTip.tipAmount > 0
          ? { cash_tip_amount: extensionCashTip.tipAmount }
          : {}),
        description: t("drawer.individualExtension.paymentDescription", {
          date: individualExtensionPreview.new_checkout_date
        }),
        ...(manualReference ? { manual_reference: manualReference } : {})
      };
    } else if (individualExtensionPaymentAction === "payment_link") {
      const recipientEmail = individualExtensionRecipientEmail.trim();
      if (!isValidPaymentEmail(recipientEmail)) {
        setActionError(t("drawer.individualExtension.recipientEmailInvalid"));
        setIndividualExtensionConfirmOpen(false);
        setIndividualExtensionPreview(null);
        return;
      }
      payload.payment_link = {
        reservation_id: reservation.id,
        requested_amount: amount,
        currency: individualExtensionPreview.currency_code,
        recipient_email: recipientEmail,
        recipient_name: [reservation.guest?.first_name, reservation.guest?.last_name].filter(Boolean).join(" ") || undefined,
        title: t("drawer.individualExtension.paymentLinkTitle", { code: reservation.confirmation_code }),
        description: t("drawer.individualExtension.paymentDescription", {
          date: individualExtensionPreview.new_checkout_date
        })
      };
    }

    setActionError(null);
    setActionMessage(null);
    expectedIndividualExtensionDateRef.current = {
      reservationId: reservation.id,
      checkoutDate: payload.new_checkout_date
    };
    try {
      const result = await individualExtensionMutation.mutateAsync({ id: reservation.id, payload });
      setIndividualExtensionConfirmOpen(false);
      setIndividualExtensionPreview(null);
      setIndividualExtensionCashReceivedAmountInput("");
      setIndividualExtensionCashTipAmountInput("");
      if (individualExtensionPaymentAction === "payment_link") {
        setIndividualExtensionCreatedLink(result.payment_link ? {
          external_checkout_url: result.payment_link.external_checkout_url,
          execution_mode: result.payment_link.execution_mode,
          payable: result.payment_link.payable
        } : null);
        setActionMessage(t("drawer.individualExtension.paymentLinkCreated"));
      } else if (individualExtensionPaymentAction === "pending_balance") {
        setActionMessage(t("drawer.individualExtension.balanceLeftPending"));
      } else {
        setActionMessage(t("drawer.individualExtension.paymentRegistered"));
      }
    } catch (err) {
      expectedIndividualExtensionDateRef.current = null;
      setIndividualExtensionConfirmOpen(false);
      setIndividualExtensionPreview(null);
      setActionError(err instanceof ApiError ? err.message : t("drawer.individualExtension.applyFailed"));
    }
  };

  const runAction = async (label: string, action: () => Promise<unknown>, onSuccess: () => void): Promise<boolean> => {
    setActionError(null);
    setActionMessage(null);
    try {
      await action();
      onSuccess();
      return true;
    } catch (err) {
      setActionError(
        label === t("drawer.actions.labels.partialCheckIn")
          ? t("drawer.errors.checkInFailed")
          : err instanceof ApiError
            ? err.message
            : t("drawer.errors.actionFailed", { label })
      );
      return false;
    }
  };

  const handlePay = async () => {
    if (!reservationId) return;
    const amount = Number(paymentAmount);
    const manualReference = isManualPaymentMethod ? paymentReferenceInput.trim() : undefined;
    if (deferredCompanyBilling && selectedCompanyChargeIds.length === 0) {
      setActionError(t("drawer.companyCharges.selectBeforePayment"));
      return;
    }
    if (
      !deferredCompanyBilling &&
      hasUnpaidCompanyCharges &&
      selectedCompanyChargeIds.length === 0 &&
      (!Number.isFinite(amount) || amount > companyBaseBalanceDue + 0.01)
    ) {
      setActionError(t("drawer.companyCharges.selectBeforePayment"));
      return;
    }
    if (isManualPaymentMethod && !manualReference) {
      setActionError(t("drawer.errors.manualPaymentReferenceRequired"));
      return;
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setActionError(t("drawer.errors.invalidAmount"));
      return;
    }
    const quote = paymentQuoteQuery.data;
    if (!quote || Math.abs(Number(quote.base_amount) - amount) >= 0.005) {
      setActionError(t("page.errors.paymentQuoteUnavailable"));
      return;
    }
    const expectedCashAmount = Number(quote.final_amount);
    const cashTender = paymentMethod === "cash"
      ? calculateCashTender(cashReceivedAmountInput, expectedCashAmount)
      : null;
    if (cashTender && (!cashTender.valid || cashTender.receivedAmount === null)) {
      setActionError(
        cashTender.reason === "insufficient"
          ? t("page.form.cashReceivedInsufficient", { amount: formatMoney(expectedCashAmount, currencyCode) })
          : t("page.form.cashReceivedInvalid")
      );
      return;
    }
    const cashTip = cashTender
      ? calculateCashTip(cashTipAmountInput, cashTender.changeAmount ?? 0)
      : null;
    if (cashTip && (!cashTip.valid || cashTip.tipAmount === null)) {
      setActionError(t("page.form.cashTipInvalid"));
      return;
    }
    setActionError(null);
    setActionMessage(null);
    try {
      // usePaymentMutation keeps this promise pending until the server-backed
      // reservation, operations, payment, cash and analytics queries have
      // refetched. The drawer must not report success or become closable before
      // that confirmation arrives.
      await paymentMutation.mutateAsync({
        reservation_id: reservationId,
        amount,
        payment_method: paymentMethod,
        transaction_type: reservation?.status === "pending" ? "deposit" : "balance_payment",
        currency: currencyCode,
        payment_quote_token: quote.payment_quote_token,
        ...(cashTender?.receivedAmount !== null && cashTender?.receivedAmount !== undefined
          ? { cash_received_amount: cashTender.receivedAmount }
          : {}),
        ...(cashTip?.tipAmount !== null && cashTip?.tipAmount !== undefined && cashTip.tipAmount > 0
          ? { cash_tip_amount: cashTip.tipAmount }
          : {}),
        ...(manualReference ? { manual_reference: manualReference } : {}),
        ...(selectedCompanyChargeIds.length > 0 ? { company_night_charge_ids: selectedCompanyChargeIds } : {})
      });
      setSelectedCompanyChargeIds([]);
      setPaymentAmount("");
      setCashReceivedAmountInput("");
      setCashTipAmountInput("");
      setPaymentReferenceInput("");
      setActionMessage(t("drawer.messages.paymentRegistered"));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("drawer.errors.paymentFailed"));
    }
  };

  const handleClose = () => {
    if (
      individualExtensionMutation.isPending ||
      paymentMutation.isPending ||
      addGuestsMutation.isPending ||
      partialCheckInMutation.isPending ||
      checkInMutation.isPending ||
      checkOutMutation.isPending ||
      cancelMutation.isPending
    ) {
      return;
    }
    onClose();
  };

  const submitCheckIn = async (restrictionOverride?: RestrictionOverride): Promise<void> => {
    if (!reservationId || !reservation) return;
    setActionError(null);
    setActionMessage(null);
    try {
      await checkInMutation.mutateAsync({
        id: reservation.id,
        guest: needsCheckinCapture ? buildGuestPatch() : undefined,
        restriction_override: restrictionOverride
      });
      setActionMessage(t("drawer.messages.checkInDone"));
    } catch (err) {
      // The guest has an active GuestRestriction -- prompt for an override
      // reason and retry through the same atomic endpoint.
      if (restrictionOverridePrompt.handleError(err, (override) => void submitCheckIn(override))) return;
      setActionError(
        getCheckinActionErrorMessage(err, t, Number(operationalBalanceDue ?? 0), currencyCode)
      );
    }
  };

  const containerRef = useDialogA11y(open, handleClose);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-labelledby="reservation-drawer-title">
      <div className="flex-1 animate-fade-in bg-black/30" onClick={handleClose} />
      <div
        ref={containerRef}
        tabIndex={-1}
        className="flex w-full max-w-xl animate-slide-in-right flex-col border-l border-slate-200 bg-white shadow-xl outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.reservationLabel")}</p>
            <h3 id="reservation-drawer-title" className="truncate text-lg font-semibold text-slate-900">
              {reservation ? reservation.confirmation_code : `#${reservationId}`}
            </h3>
            {reservation && (
              <span
                className={`mt-1 inline-block rounded-full px-2 py-1 text-xs font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
              >
                {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={paymentMutation.isPending || individualExtensionMutation.isPending}
            aria-label={t("drawer.closeAria")}
            className="text-lg leading-none text-slate-500 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            ×
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm text-slate-700">
          {reservationQuery.isLoading && <p className="text-slate-500">{t("drawer.loading")}</p>}
          {reservationQuery.isError && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700" role="alert" data-testid="reservation-drawer-load-error">
              <span>{t("drawer.loadError")}</span>
              <button
                type="button"
                onClick={() => void reservationQuery.refetch()}
                disabled={reservationQuery.isFetching}
                className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-60"
              >
                {t("drawer.loadRetry")}
              </button>
            </div>
          )}

          {reservation && (
            <>
              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.stay.title")}</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {reservation.check_in_date} → {reservation.check_out_date}
                </p>
                <p className="text-xs text-slate-500">
                  {reservation.room_number
                    ? t("drawer.stay.roomNumber", { id: reservation.room_number })
                    : t("drawer.stay.noRoomAssigned")}{" "}
                  · {t("drawer.stay.category")}{" "}
                  {reservation.category_name ?? t("drawer.stay.informationUnavailable")}
                </p>
                <p className="mt-2 text-xs text-slate-600">
                  {t("drawer.stay.reservedNights")}: {reservation.reserved_nights ?? reservation.nights ?? 0}
                  <span className="mx-2">·</span>
                  {t("drawer.stay.usedNights")}: {reservation.used_nights ?? t("drawer.stay.pendingCheckout")}
                </p>
              </section>

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.guests.title")}</p>
                <p data-testid="drawer-guest-name" className="mt-1 font-semibold text-slate-900">{guestFullName(t, reservation.guest, reservation.guest_id)}</p>
                <p className="text-xs text-slate-500">{t("drawer.guests.primary")}</p>
                {reservation.guest_id ? (
                  <GuestRestrictionBadge guestId={reservation.guest_id} className="mt-1" />
                ) : null}
                {reservation.additional_guests && reservation.additional_guests.length > 0 ? (
                  <ul className="mt-2 space-y-1">
                    {reservation.additional_guests.map((guest) => (
                      <li key={guest.id} className="text-sm text-slate-800">
                        {guestFullName(t, guest)}
                        <span className="ml-2 text-xs text-slate-500">{t("drawer.guests.companion")}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">{t("drawer.guests.noCompanions")}</p>
                )}

                {reservation.status !== "cancelled" && reservation.status !== "checked_out" && (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.guests.addCompanion")}</p>
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <input
                        type="text"
                        placeholder={t("drawer.guests.firstNamePlaceholder")}
                        value={companionForm.first_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, first_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.firstNameAria")}
                      />
                      <input
                        type="text"
                        placeholder={t("drawer.guests.lastNamePlaceholder")}
                        value={companionForm.last_name}
                        onChange={(event) => setCompanionForm((prev) => ({ ...prev, last_name: event.target.value }))}
                        className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.lastNameAria")}
                      />
                      <input
                        type="text"
                        placeholder={t("drawer.guests.documentPlaceholder")}
                        value={companionForm.document_number}
                        onChange={(event) =>
                          setCompanionForm((prev) => ({ ...prev, document_number: event.target.value }))
                        }
                        className="w-36 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.guests.documentAria")}
                      />
                      <button
                        type="button"
                        onClick={handleAddCompanion}
                        disabled={addGuestsMutation.isPending}
                        className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {addGuestsMutation.isPending ? t("drawer.guests.adding") : t("drawer.guests.add")}
                      </button>
                    </div>
                    {companionError && <p className="mt-2 text-xs text-rose-700">{companionError}</p>}
                  </div>
                )}
              </section>

              <ReservationGuestArrivalPanel
                reservation={reservation}
                canCheckIn={permissionsKnown && hasPermission("checkin:perform")}
              />

              {reservation.company_id && canReviewCompanyTerms ? (
                <CompanyTermsReviewPanel reservationId={reservation.id} />
              ) : null}

              {reservation.company_id && (canReadCompanyDocuments || canManageCompanyCharges) ? (
                <section className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3">
                  <p className="text-xs uppercase tracking-wide text-indigo-800">{t("drawer.companyDocuments.title")}</p>
                  {canReadCompanyDocuments && companyDocumentsQuery.isLoading ? (
                    <p className="mt-2 text-xs text-slate-500">{t("drawer.companyDocuments.loading")}</p>
                  ) : canReadCompanyDocuments && companyDocumentsQuery.isError ? (
                    <p className="mt-2 text-xs text-rose-700">{t("drawer.companyDocuments.loadFailed")}</p>
                  ) : canReadCompanyDocuments && (companyDocumentsQuery.data ?? []).length === 0 ? (
                    <p className="mt-2 text-xs text-slate-600">{t("drawer.companyDocuments.empty")}</p>
                  ) : canReadCompanyDocuments ? (
                    <ul className="mt-2 space-y-2">
                      {(companyDocumentsQuery.data ?? []).map((companyDocument) => (
                        <li key={companyDocument.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-indigo-100 bg-white px-2 py-2">
                          <div className="min-w-0">
                            <p className="truncate text-xs font-semibold text-slate-800">
                              {companyDocument.file_name || companyDocument.doc_type}
                            </p>
                            <p className="text-xs text-slate-500">
                              {t(`drawer.companyDocuments.status.${companyDocument.status}`)}
                              {companyDocument.requires_signature ? ` · ${t("drawer.companyDocuments.signatureRequired")}` : ""}
                            </p>
                            {companyDocument.notes ? <p className="mt-1 text-xs text-slate-500">{companyDocument.notes}</p> : null}
                          </div>
                          <div className="flex items-center gap-2">
                            {companyDocument.stored_object_id ? (
                              <button
                                type="button"
                                onClick={() => void handleOpenCompanyDocument(companyDocument.id)}
                                className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                              >
                                {t("drawer.companyDocuments.open")}
                              </button>
                            ) : null}
                            {canSignCompanyDocuments && companyDocument.requires_signature && companyDocument.status === "pending" && companyDocument.stored_object_id ? (
                              <button
                                type="button"
                                onClick={() => void handleMarkCompanyDocumentSigned(companyDocument.id)}
                                disabled={markCompanyDocumentSignedMutation.isPending}
                                className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-60"
                              >
                                {t("drawer.companyDocuments.markSigned")}
                              </button>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {canManageCompanyCharges ? (
                    <div className="mt-3 border-t border-indigo-100 pt-3">
                      <label htmlFor="company-voucher-pdf" className="block text-xs font-semibold text-slate-700">
                        {t("drawer.companyDocuments.uploadLabel")}
                      </label>
                      <input
                        ref={companyVoucherFileInputRef}
                        id="company-voucher-pdf"
                        data-testid="company-voucher-pdf-input"
                        type="file"
                        accept="application/pdf,.pdf"
                        onChange={(event) => handleCompanyVoucherFileChange(event.target.files?.[0] ?? null)}
                        disabled={companyDocumentMutations.uploadDocumentMutation.isPending}
                        className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs text-slate-700 file:mr-2 file:rounded file:border-0 file:bg-slate-100 file:px-2 file:py-1 file:text-xs file:font-semibold"
                      />
                      <p className="mt-1 text-xs text-slate-500">{t("drawer.companyDocuments.uploadHint")}</p>
                      {companyVoucherFeedback ? (
                        <p
                          className={`mt-2 text-xs ${companyVoucherFeedback.kind === "error" ? "text-rose-700" : "text-emerald-700"}`}
                          role={companyVoucherFeedback.kind === "error" ? "alert" : "status"}
                          aria-live={companyVoucherFeedback.kind === "error" ? "assertive" : "polite"}
                          data-testid="company-voucher-upload-feedback"
                        >
                          {companyVoucherFeedback.message}
                        </p>
                      ) : null}
                      <div className="mt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => void handleUploadCompanyVoucher()}
                          disabled={!companyVoucherFile || companyDocumentMutations.uploadDocumentMutation.isPending}
                          className="rounded-md bg-indigo-700 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {companyDocumentMutations.uploadDocumentMutation.isPending
                            ? t("drawer.companyDocuments.uploading")
                            : t("drawer.companyDocuments.upload")}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {reservation.company_id ? (
                <section className="rounded-lg border border-amber-200 bg-amber-50/60 p-3" data-testid="company-extension-request">
                  <p className="text-xs uppercase tracking-wide text-amber-900">{t("drawer.companyExtension.title")}</p>
                  <p className="mt-1 text-xs text-amber-900">{t("drawer.companyExtension.hint")}</p>
                  <p className="mt-2 text-sm font-semibold text-amber-950" role="status">
                    {reservation.company_extension_request_pending
                      ? t("drawer.companyExtension.pending")
                      : t("drawer.companyExtension.none")}
                  </p>
                  <label className="mt-2 block space-y-1 text-xs">
                    <span className="text-slate-700">{t("drawer.companyExtension.noteLabel")}</span>
                    <textarea
                      maxLength={1000}
                      rows={2}
                      value={companyExtensionNote}
                      onChange={(event) => setCompanyExtensionNote(event.target.value)}
                      placeholder={t("drawer.companyExtension.notePlaceholder")}
                      className="w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-sm"
                      aria-label={t("drawer.companyExtension.noteLabel")}
                    />
                  </label>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleCompanyExtensionRequest()}
                      disabled={companyExtensionRequestMutation.isPending}
                      className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-950 hover:bg-amber-100 disabled:opacity-60"
                    >
                      {companyExtensionRequestMutation.isPending
                        ? t("drawer.companyExtension.saving")
                        : reservation.company_extension_request_pending
                          ? t("drawer.companyExtension.update")
                          : t("drawer.companyExtension.save")}
                    </button>
                  </div>
                </section>
              ) : null}

              {canApplyPendingCompanyExtension && reservation ? (
                <section className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-3" data-testid="company-extension-apply">
                  <p className="text-xs uppercase tracking-wide text-indigo-900">{t("drawer.companyExtension.applyTitle")}</p>
                  <p className="mt-1 text-xs text-indigo-900">{t("drawer.companyExtension.applyHint")}</p>
                  {reservation.company_extension_request_note ? (
                    <p className="mt-2 rounded-md bg-white/80 p-2 text-sm text-slate-700">
                      {reservation.company_extension_request_note}
                    </p>
                  ) : null}
                  <label className="mt-2 block space-y-1 text-xs">
                    <span className="text-slate-700">{t("drawer.companyExtension.newCheckoutDate")}</span>
                    <input
                      type="date"
                      value={companyExtensionCheckoutDate}
                      min={addIsoDays(reservation.check_out_date, 1)}
                      disabled={companyExtensionPreviewPending}
                      onChange={(event) => {
                        setCompanyExtensionCheckoutDate(event.target.value);
                        setCompanyExtensionPreview(null);
                        setCompanyExtensionConfirmOpen(false);
                      }}
                      aria-label={t("drawer.companyExtension.newCheckoutDate")}
                      className="w-full rounded-lg border border-indigo-200 bg-white px-2 py-1.5 text-sm"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => void handleOpenCompanyExtensionConfirmation()}
                    disabled={companyAccountExtensionMutation.isPending || companyExtensionPreviewPending || !companyExtensionCheckoutDate}
                    className="mt-2 min-h-10 rounded-md border border-indigo-300 bg-white px-3 py-2 text-xs font-semibold text-indigo-950 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {companyExtensionPreviewPending
                      ? t("drawer.companyExtension.previewing")
                      : companyAccountExtensionMutation.isPending
                      ? t("drawer.companyExtension.applying")
                      : t("drawer.companyExtension.apply")}
                  </button>
                  {companyExtensionPreview?.impact_plan && hasBlockedExtensionImpact(companyExtensionPreview.impact_plan) ? (
                    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950" role="alert" data-testid="company-extension-impact-plan">
                      <p className="font-semibold">{t("drawer.extensionImpact.manualResolutionRequired")}</p>
                      <p className="mt-1">{t("drawer.extensionImpact.title")}: {extensionImpactSummary(t, companyExtensionPreview.impact_plan)}</p>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {canExtendIndividualReservation && reservation ? (
                <section className="rounded-lg border border-cyan-200 bg-cyan-50/60 p-3" data-testid="individual-extension">
                  <p className="text-xs uppercase tracking-wide text-cyan-950">{t("drawer.individualExtension.title")}</p>
                  <p className="mt-1 text-xs text-cyan-900">{t("drawer.individualExtension.hint")}</p>
                  <label className="mt-2 block space-y-1 text-xs">
                    <span className="text-slate-700">{t("drawer.individualExtension.newCheckoutDate")}</span>
                    <input
                      type="date"
                      value={individualExtensionCheckoutDate}
                      min={addIsoDays(reservation.check_out_date, 1)}
                      disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                      onChange={(event) => {
                        setIndividualExtensionCheckoutDate(event.target.value);
                        setIndividualExtensionPreview(null);
                        setIndividualExtensionCashReceivedAmountInput("");
                        setIndividualExtensionCashTipAmountInput("");
                        setIndividualExtensionConfirmOpen(false);
                        setIndividualExtensionCreatedLink(null);
                      }}
                      aria-label={t("drawer.individualExtension.newCheckoutDate")}
                      className="w-full rounded-lg border border-cyan-200 bg-white px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="mt-2 block space-y-1 text-xs">
                    <span className="text-slate-700">{t("drawer.individualExtension.paymentAction")}</span>
                    <select
                      value={individualExtensionPaymentAction}
                      disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                      onChange={(event) => {
                        setIndividualExtensionPaymentAction(event.target.value as IndividualExtensionPaymentAction);
                        setIndividualExtensionPreview(null);
                        setIndividualExtensionCashReceivedAmountInput("");
                        setIndividualExtensionCashTipAmountInput("");
                        setIndividualExtensionConfirmOpen(false);
                        setIndividualExtensionCreatedLink(null);
                      }}
                      aria-label={t("drawer.individualExtension.paymentAction")}
                      className="w-full rounded-lg border border-cyan-200 bg-white px-2 py-1.5 text-sm"
                    >
                      <option value="pending_balance">{t("drawer.individualExtension.pendingBalance")}</option>
                      {canCollectExtension ? (
                        <>
                          <option value="payment_link">{t("drawer.individualExtension.paymentLink")}</option>
                          <option value="immediate_payment">{t("drawer.individualExtension.immediatePayment")}</option>
                        </>
                      ) : null}
                    </select>
                  </label>
                  {individualExtensionPaymentAction === "payment_link" ? (
                    <label className="mt-2 block space-y-1 text-xs">
                      <span className="text-slate-700">{t("drawer.individualExtension.recipientEmail")}</span>
                      <input
                        type="email"
                        required
                        maxLength={320}
                        value={individualExtensionRecipientEmail}
                        disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                        onChange={(event) => {
                          setIndividualExtensionRecipientEmail(event.target.value);
                          setIndividualExtensionPreview(null);
                          setIndividualExtensionCreatedLink(null);
                        }}
                        aria-label={t("drawer.individualExtension.recipientEmail")}
                        className="w-full rounded-lg border border-cyan-200 bg-white px-2 py-1.5 text-sm"
                      />
                    </label>
                  ) : individualExtensionPaymentAction === "immediate_payment" ? (
                    <>
                      <label className="mt-2 block space-y-1 text-xs">
                        <span className="text-slate-700">{t("drawer.individualExtension.paymentMethod")}</span>
                        <select
                          value={individualExtensionPaymentMethod}
                          disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                          onChange={(event) => {
                            setIndividualExtensionPaymentMethod(event.target.value as ExtensionManualPaymentMethod);
                            setIndividualExtensionPreview(null);
                            setIndividualExtensionCashReceivedAmountInput("");
                            setIndividualExtensionCashTipAmountInput("");
                            setIndividualExtensionCreatedLink(null);
                          }}
                          aria-label={t("drawer.individualExtension.paymentMethod")}
                          className="w-full rounded-lg border border-cyan-200 bg-white px-2 py-1.5 text-sm"
                        >
                          <option value="cash">{t("drawer.payment.methods.cash")}</option>
                          <option value="bank_transfer">{t("drawer.payment.methods.bank_transfer")}</option>
                          <option value="credit_card">{t("drawer.payment.methods.credit_card")}</option>
                          <option value="debit_card">{t("drawer.payment.methods.debit_card")}</option>
                        </select>
                      </label>
                      {manualPaymentMethods.includes(individualExtensionPaymentMethod) ? (
                        <label className="mt-2 block space-y-1 text-xs">
                          <span className="text-slate-700">{t("drawer.individualExtension.manualReference")}</span>
                          <input
                            type="text"
                            required
                            maxLength={120}
                            value={individualExtensionManualReference}
                            disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                            onChange={(event) => {
                              setIndividualExtensionManualReference(event.target.value);
                              setIndividualExtensionPreview(null);
                            }}
                            aria-label={t("drawer.individualExtension.manualReference")}
                            className="w-full rounded-lg border border-cyan-200 bg-white px-2 py-1.5 text-sm"
                          />
                        </label>
                      ) : null}
                      <p className="mt-2 text-xs text-cyan-950">{t("drawer.individualExtension.immediatePaymentHint")}</p>
                    </>
                  ) : (
                    <p className="mt-2 rounded-md bg-white px-3 py-2 text-xs text-cyan-950">
                      {t("drawer.individualExtension.pendingBalanceHint")}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={() => void handlePreviewIndividualExtension()}
                    disabled={!individualExtensionCheckoutDate || individualExtensionPreviewPending || individualExtensionMutation.isPending}
                    className="mt-3 min-h-10 rounded-md border border-cyan-300 bg-white px-3 py-2 text-xs font-semibold text-cyan-950 hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {individualExtensionPreviewPending
                      ? t("drawer.individualExtension.previewing")
                      : t("drawer.individualExtension.preview")}
                  </button>
                  {individualExtensionPreview &&
                  individualExtensionPaymentAction === "immediate_payment" &&
                  individualExtensionPaymentMethod === "cash" &&
                  !hasBlockedExtensionImpact(individualExtensionPreview.impact_plan) ? (
                    <div className="mt-3 space-y-3 rounded-md border border-cyan-200 bg-white p-3" data-testid="individual-extension-cash-tender">
                      <CashTenderField
                        amount={individualExtensionCashReceivedAmountInput}
                        tipAmount={individualExtensionCashTipAmountInput}
                        expectedAmount={extensionCashPreviewTotal}
                        currency={individualExtensionPreview.currency_code}
                        label={t("page.form.cashReceived", { currency: individualExtensionPreview.currency_code })}
                        hint={t("page.form.cashReceivedHint")}
                        changeLabel={t("page.form.cashChange")}
                        tipToggleLabel={t("page.form.cashTipToggle")}
                        tipAmountLabel={t("page.form.cashTipAmount")}
                        tipHint={t("page.form.cashTipHint")}
                        invalidAmountMessage={t("page.form.cashReceivedInvalid")}
                        insufficientMessage={t("page.form.cashReceivedInsufficient", { amount: formatMoney(extensionCashPreviewTotal, individualExtensionPreview.currency_code) })}
                        tipInvalidMessage={t("page.form.cashTipInvalid")}
                        onChange={setIndividualExtensionCashReceivedAmountInput}
                        onTipAmountChange={setIndividualExtensionCashTipAmountInput}
                        testId="individual-extension-cash-received"
                        disabled={individualExtensionPreviewPending || individualExtensionMutation.isPending}
                      />
                      <button
                        type="button"
                        onClick={handleOpenIndividualExtensionConfirmation}
                        disabled={individualExtensionMutation.isPending || !calculateCashTender(individualExtensionCashReceivedAmountInput, extensionCashPreviewTotal).valid}
                        className="min-h-10 rounded-md border border-cyan-300 bg-cyan-700 px-3 py-2 text-xs font-semibold text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
                        data-testid="individual-extension-cash-confirm"
                      >
                        {t("drawer.individualExtension.confirmApply")}
                      </button>
                    </div>
                  ) : null}
                  {individualExtensionPreview?.impact_plan && hasBlockedExtensionImpact(individualExtensionPreview.impact_plan) ? (
                    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950" role="alert" data-testid="individual-extension-impact-plan">
                      <p className="font-semibold">{t("drawer.extensionImpact.manualResolutionRequired")}</p>
                      <p className="mt-1">{t("drawer.extensionImpact.title")}: {extensionImpactSummary(t, individualExtensionPreview.impact_plan)}</p>
                    </div>
                  ) : null}
                  {individualExtensionCreatedLink ? (
                    <div className="mt-3 rounded-md border border-cyan-200 bg-white px-3 py-2 text-xs" role="status" data-testid="individual-extension-payment-link">
                      {individualExtensionCreatedLink.execution_mode === "provider" &&
                      individualExtensionCreatedLink.payable &&
                      individualExtensionCreatedLink.external_checkout_url ? (
                        <a
                          href={individualExtensionCreatedLink.external_checkout_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-semibold text-cyan-900 underline underline-offset-2"
                        >
                          {t("drawer.individualExtension.openPaymentLink")}
                        </a>
                      ) : (
                        <span>{t("drawer.individualExtension.paymentLinkLocalOnly")}</span>
                      )}
                    </div>
                  ) : null}
                </section>
              ) : null}

              {needsCheckinCapture && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="checkin-capture-form">
                  <p className="text-xs uppercase tracking-wide text-amber-800">{t("drawer.checkinCapture.title")}</p>
                  {checkinValidation.data && checkinValidation.data.errors.length > 0 && (
                    <p className="mt-1 text-xs text-amber-800">{localizedCheckinErrors.join("; ")}</p>
                  )}
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.documentType")}</span>
                      <select
                        value={captureForm.document_type}
                        onChange={(event) =>
                          setCaptureForm((prev) => ({
                            ...prev,
                            document_type: event.target.value as CheckinCaptureForm["document_type"]
                          }))
                        }
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      >
                        <option value="">{t("drawer.checkinCapture.documentTypeUnspecified")}</option>
                        <option value="DNI">{t("drawer.checkinCapture.documentTypeDni")}</option>
                        <option value="PASSPORT">{t("drawer.checkinCapture.documentTypePassport")}</option>
                        <option value="CEDULA">{t("drawer.checkinCapture.documentTypeCedula")}</option>
                      </select>
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.documentNumber")}</span>
                      <input
                        type="text"
                        value={captureForm.document_number}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, document_number: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.nationality")}</span>
                      <input
                        type="text"
                        value={captureForm.nationality}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, nationality: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.country")}</span>
                      <input
                        type="text"
                        value={captureForm.country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.birthPlace")}</span>
                      <input
                        type="text"
                        value={captureForm.birth_place}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_place: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.birthPlace")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.birthCountry")}</span>
                      <input
                        type="text"
                        value={captureForm.birth_country}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, birth_country: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.birthCountry")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.maritalStatus")}</span>
                      <input
                        type="text"
                        value={captureForm.marital_status}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, marital_status: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.maritalStatus")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.checkinCapture.occupation")}</span>
                      <input
                        type="text"
                        value={captureForm.occupation}
                        onChange={(event) => setCaptureForm((prev) => ({ ...prev, occupation: event.target.value }))}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        aria-label={t("drawer.checkinCapture.occupation")}
                      />
                    </label>
                  </div>
                  <label className="mt-2 flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={captureForm.terms_accepted}
                      onChange={(event) => setCaptureForm((prev) => ({ ...prev, terms_accepted: event.target.checked }))}
                    />
                    {t("drawer.checkinCapture.acceptTerms")}
                  </label>
                </section>
              )}

              <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.billing.title")}</p>
                  {summaryQuery.isFetching && <span className="text-xs text-slate-500">{t("drawer.billing.updating")}</span>}
                </div>
                {operationsQuery.isError ? (
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert" data-testid="reservation-drawer-operations-error">
                    <span>{t("drawer.operationLoadError")}</span>
                    <button
                      type="button"
                      onClick={() => void operationsQuery.refetch()}
                      disabled={operationsQuery.isFetching}
                      className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 font-semibold hover:bg-rose-100 disabled:opacity-60"
                    >
                      {t("drawer.operationRetry")}
                    </button>
                  </div>
                ) : null}
                {deferredCompanyBilling ? (
                  <p className="mt-2 text-sm text-slate-700" data-testid="deferred-company-billing-note">
                    {t("drawer.billing.deferredCompany")}
                  </p>
                ) : summaryQuery.isLoading ? (
                  <p className="mt-2 text-slate-500">{t("drawer.billing.loadingSummary")}</p>
                ) : summary ? (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.operationalTotal")}</p>
                      <p className="font-semibold">
                        {formatMoney(operations?.financial_summary?.operational_total_amount ?? summary.total_amount, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.paid")}</p>
                      <p className="font-semibold">{formatMoney(summary.amount_paid, currencyCode)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.operationalBalance")}</p>
                      <p className="font-semibold text-slate-900" data-testid="drawer-balance-due">
                        {formatMoney(operationalBalanceDue ?? 0, currencyCode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">{t("drawer.billing.depositRequired")}</p>
                      <p className="font-semibold">{formatMoney(summary.deposit_required, currencyCode)}</p>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert" data-testid="reservation-drawer-financial-summary-error">
                    <span>{t("drawer.billing.loadError")}</span>
                    <button
                      type="button"
                      onClick={() => void summaryQuery.refetch()}
                      disabled={summaryQuery.isFetching}
                      className="min-h-11 rounded-lg border border-rose-300 bg-white px-3 py-1 font-semibold hover:bg-rose-100 disabled:opacity-60"
                    >
                      {t("drawer.operationRetry")}
                    </button>
                  </div>
                )}
                {!deferredCompanyBilling && (reservation.quoted_amount_ars != null || reservation.quoted_amount_usd != null) && (
                  <div className="mt-3 rounded-md border border-slate-200 bg-white p-2">
                    <p className="text-xs font-semibold text-slate-700">{t("drawer.billing.amountsTitle")}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {t("drawer.billing.amountsHint")}
                    </p>
                    <div className="mt-1 grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-xs text-slate-500">{t("drawer.billing.inPesos")}</p>
                        <p className="font-semibold">
                          {reservation.quoted_amount_ars != null ? formatMoney(reservation.quoted_amount_ars, "ARS") : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">{t("drawer.billing.inDollars")}</p>
                        <p className="font-semibold">
                          {reservation.quoted_amount_usd != null ? formatMoney(reservation.quoted_amount_usd, "USD") : "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </section>

              {reservation.company_id ? (
                <section className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-xs uppercase tracking-wide text-amber-900">{t("drawer.companyCharges.title")}</p>
                    {companyNightCharges?.nightly_surcharge_amount != null ? (
                      <span className="text-xs text-slate-600">
                        {t("drawer.companyCharges.perNight", { amount: formatMoney(companyNightCharges.nightly_surcharge_amount, currencyCode) })}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-slate-600">{t("drawer.companyCharges.roomAndContractNote")}</p>
                  <p className="mt-1 text-xs text-slate-600">{t("drawer.companyCharges.roleHint")}</p>
                  {companyNightChargesQuery.isLoading ? (
                    <p className="mt-2 text-xs text-slate-500">{t("drawer.companyCharges.loading")}</p>
                  ) : companyNightChargesQuery.isError ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-rose-700">
                      <span>{t("drawer.companyCharges.loadFailed")}</span>
                      <button
                        type="button"
                        onClick={() => void companyNightChargesQuery.refetch()}
                        className="rounded border border-rose-300 bg-white px-2 py-1 font-semibold hover:bg-rose-50"
                      >
                        {t("drawer.companyCharges.retry")}
                      </button>
                    </div>
                  ) : (
                    <>
                      {companyChargeRows.length === 0 ? (
                        <p className="mt-2 text-xs text-slate-600">{t("drawer.companyCharges.empty")}</p>
                      ) : (
                        <ul className="mt-2 space-y-2">
                          {companyChargeRows.map((charge) => (
                            <li key={charge.id} className="rounded-md border border-amber-100 bg-white px-2 py-2">
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <label className="flex min-w-0 items-start gap-2 text-xs">
                                  {Number(charge.remaining_due) > 0.01 && !charge.payment_pending && !charge.review_only ? (
                                    <input
                                      type="checkbox"
                                      checked={selectedCompanyChargeIds.includes(charge.id)}
                                      onChange={(event) => setSelectedCompanyChargeIds((current) =>
                                        event.target.checked
                                          ? [...current, charge.id]
                                          : current.filter((id) => id !== charge.id)
                                      )}
                                      aria-label={t("drawer.companyCharges.selectNight", { date: charge.stay_date })}
                                    />
                                  ) : <span className="w-3" />}
                                  <span>
                                    <span className="block font-semibold text-slate-800">{charge.stay_date}</span>
                                    <span className="block text-slate-500">
                                      {t("drawer.companyCharges.quantityAndUnit", {
                                        quantity: charge.quantity,
                                        amount: formatMoney(charge.unit_amount, charge.currency_code)
                                      })}
                                    </span>
                                    <span className="text-slate-500">
                                      {t("drawer.companyCharges.paidDue", {
                                        paid: formatMoney(charge.paid_amount, charge.currency_code),
                                        due: formatMoney(charge.remaining_due, charge.currency_code)
                                      })}
                                    </span>
                                    {charge.review_only ? <span className="mt-0.5 block text-rose-700">{t("drawer.companyCharges.reviewOnly")}</span> : null}
                                    {charge.payment_pending ? <span className="mt-0.5 block text-amber-800">{t("drawer.companyCharges.paymentPending")}</span> : null}
                                  </span>
                                </label>
                                <div className="flex flex-col items-end gap-2">
                                  <span className="text-xs font-semibold text-slate-700">{formatMoney(charge.amount, charge.currency_code)}</span>
                                  {canManageCompanyCharges ? (
                                    <label className="flex items-center gap-1.5 text-xs text-slate-600">
                                      <input
                                        type="checkbox"
                                        checked={selectedCompanyCorrectionIds.includes(charge.id)}
                                        disabled={correctCompanyNightChargesMutation.isPending}
                                        onChange={(event) => {
                                          setSelectedCompanyCorrectionIds((current) => event.target.checked
                                            ? [...current, charge.id]
                                            : current.filter((id) => id !== charge.id));
                                          setCompanyCorrectionAmounts((current) => {
                                            if (event.target.checked) {
                                              return { ...current, [charge.id]: current[charge.id] ?? Number(charge.amount).toFixed(2) };
                                            }
                                            const next = { ...current };
                                            delete next[charge.id];
                                            return next;
                                          });
                                        }}
                                        aria-label={t("drawer.companyCharges.selectForCorrection", { date: charge.stay_date })}
                                      />
                                      {t("drawer.companyCharges.selectForCorrectionLabel")}
                                    </label>
                                  ) : null}
                                </div>
                              </div>
                              {selectedCompanyCorrectionIds.includes(charge.id) ? (
                                <label className="mt-2 block max-w-xs space-y-1 text-xs">
                                  <span className="text-slate-600">{t("drawer.companyCharges.newAmountLabel", { date: charge.stay_date })}</span>
                                  <input
                                    type="number"
                                    min="0.01"
                                    step="0.01"
                                    value={companyCorrectionAmounts[charge.id] ?? ""}
                                    onChange={(event) => setCompanyCorrectionAmounts((current) => ({
                                      ...current,
                                      [charge.id]: event.target.value
                                    }))}
                                    disabled={correctCompanyNightChargesMutation.isPending}
                                    className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                                    aria-label={t("drawer.companyCharges.newAmountLabel", { date: charge.stay_date })}
                                  />
                                </label>
                              ) : null}
                              {charge.adjustments.length > 0 ? (
                                <details className="mt-2 text-xs text-slate-600">
                                  <summary className="cursor-pointer font-medium">
                                    {t("drawer.companyCharges.adjustmentHistory", { count: charge.adjustments.length })}
                                  </summary>
                                  <ul className="mt-1 space-y-1 pl-4">
                                    {charge.adjustments.map((adjustment) => (
                                      <li key={adjustment.id}>
                                        <span className="font-medium">{new Date(adjustment.created_at).toLocaleString()}</span>
                                        {": "}
                                        {formatMoney(adjustment.previous_amount, charge.currency_code)}
                                        {" → "}
                                        {formatMoney(adjustment.new_amount, charge.currency_code)}
                                        {` (${formatMoney(adjustment.delta_amount, charge.currency_code)})`}
                                        <span className="block">{adjustment.reason}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </details>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                      {hasUnpaidCompanyCharges ? (
                        <p className="mt-2 text-xs text-amber-900">{t("drawer.companyCharges.selectBeforePayment")}</p>
                      ) : null}
                      {canManageCompanyCharges && candidateCompanyChargeDates.length > 0 ? (
                        <div className="mt-3 border-t border-amber-200 pt-3">
                          <p className="text-xs font-semibold text-slate-700">{t("drawer.companyCharges.applyTitle")}</p>
                          <p className="mt-1 text-xs text-slate-600">{t("drawer.companyCharges.applyHint")}</p>
                          {companyNightlyRatesQuery.isLoading ? (
                            <p className="mt-2 text-xs text-slate-500" role="status">{t("drawer.companyCharges.ratesLoading")}</p>
                          ) : companyNightlyRatesQuery.isError ? (
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-rose-700" role="alert">
                              <span>{t("drawer.companyCharges.ratesLoadFailed")}</span>
                              <button
                                type="button"
                                onClick={() => void companyNightlyRatesQuery.refetch()}
                                className="rounded border border-rose-300 bg-white px-2 py-1 font-semibold hover:bg-rose-50"
                              >
                                {t("drawer.companyCharges.ratesRetry")}
                              </button>
                            </div>
                          ) : chargeableCompanyChargeOptions.length === 0 ? (
                            <p className="mt-2 text-xs text-slate-600">{t("drawer.companyCharges.noRateForStay")}</p>
                          ) : (
                            <>
                              <label className="mt-2 block max-w-xs space-y-1 text-xs">
                                <span className="text-slate-600">{t("drawer.companyCharges.extraPersonCount")}</span>
                                <input
                                  type="number"
                                  min="1"
                                  max="99"
                                  step="1"
                                  value={companyExtraPersonCount}
                                  onChange={(event) => setCompanyExtraPersonCount(event.target.value)}
                                  disabled={createCompanyNightChargesMutation.isPending}
                                  className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                                  aria-label={t("drawer.companyCharges.extraPersonCount")}
                                />
                              </label>
                              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {chargeableCompanyChargeOptions.map(({ stayDate, rate }) => {
                                  const alreadyCharged = chargedCompanyDates.has(stayDate);
                                  return (
                                    <label key={stayDate} className={`flex items-center gap-2 rounded border px-2 py-1.5 text-xs ${alreadyCharged ? "border-slate-100 bg-slate-100 text-slate-400" : "border-amber-100 bg-white text-slate-700"}`}>
                                      <input
                                        type="checkbox"
                                        checked={alreadyCharged || selectedCompanyChargeDates.includes(stayDate)}
                                        disabled={alreadyCharged || createCompanyNightChargesMutation.isPending}
                                        onChange={(event) => setSelectedCompanyChargeDates((current) =>
                                          event.target.checked
                                            ? [...current, stayDate]
                                            : current.filter((date) => date !== stayDate)
                                        )}
                                        aria-label={t("drawer.companyCharges.selectStayNight", { date: stayDate })}
                                      />
                                      <span>{stayDate} · {alreadyCharged
                                        ? t("drawer.companyCharges.alreadyAdded")
                                        : t("drawer.companyCharges.rateForNight", { amount: formatMoney(rate.amount, currencyCode) })}</span>
                                    </label>
                                  );
                                })}
                              </div>
                              <button
                                type="button"
                                onClick={() => void handleCreateCompanyNightCharges()}
                                disabled={selectedCompanyChargeDates.length === 0 || createCompanyNightChargesMutation.isPending}
                                className="mt-2 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {createCompanyNightChargesMutation.isPending ? t("drawer.companyCharges.applying") : t("drawer.companyCharges.apply")}
                              </button>
                            </>
                          )}
                        </div>
                      ) : null}
                      {selectedCompanyCorrectionRows.length > 0 ? (
                        <div className="mt-3 border-t border-amber-200 pt-3">
                          <p className="text-xs font-semibold text-slate-700">{t("drawer.companyCharges.correctionTitle")}</p>
                          <p className="mt-1 text-xs text-slate-600">{t("drawer.companyCharges.correctionHint")}</p>
                          <label className="mt-2 block space-y-1 text-xs">
                            <span className="text-slate-600">{t("drawer.companyCharges.correctionReason")}</span>
                            <textarea
                              rows={2}
                              maxLength={500}
                              value={companyCorrectionReason}
                              onChange={(event) => setCompanyCorrectionReason(event.target.value)}
                              disabled={correctCompanyNightChargesMutation.isPending}
                              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                              aria-label={t("drawer.companyCharges.correctionReason")}
                            />
                          </label>
                          <button
                            type="button"
                            onClick={() => void handleCorrectCompanyNightCharges()}
                            disabled={
                              selectedCompanyCorrectionRows.length === 0 ||
                              !companyCorrectionReason.trim() ||
                              hasInvalidCompanyCorrectionAmount ||
                              correctCompanyNightChargesMutation.isPending
                            }
                            className="mt-2 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {correctCompanyNightChargesMutation.isPending
                              ? t("drawer.companyCharges.correcting")
                              : t("drawer.companyCharges.correct")}
                          </button>
                        </div>
                      ) : null}
                    </>
                  )}
                </section>
              ) : null}

              {reservation.status !== "cancelled" && reservation.status !== "checked_out" &&
                (!deferredCompanyBilling || selectedCompanyChargeIds.length > 0) && (
                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("drawer.payment.title")}</p>
                  <div className="mt-2 flex flex-wrap items-end gap-2">
                    <label className="flex-1 space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.payment.amountLabel")}</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={paymentAmount}
                        onChange={(event) => setPaymentAmount(event.target.value)}
                        placeholder={
                          deferredCompanyBilling
                            ? t("drawer.companyCharges.selectBeforePayment")
                            : reservation.company_id && hasUnpaidCompanyCharges
                            ? companyBaseBalanceDue.toFixed(2)
                            : operationalBalanceDue
                              ? String(operationalBalanceDue)
                              : "0"
                        }
                        disabled={selectedCompanyChargeIds.length > 0}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label={t("drawer.payment.amountAria")}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-slate-600">{t("drawer.payment.methodLabel")}</span>
                      <select
                        value={paymentMethod}
                        onChange={(event) => {
                          const method = event.target.value as PaymentMethod;
                          setPaymentMethod(method);
                          if (method !== "cash") {
                            setCashReceivedAmountInput("");
                            setCashTipAmountInput("");
                          }
                        }}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        aria-label={t("drawer.payment.methodAria")}
                      >
                        {paymentMethodValues.map((value) => (
                          <option key={value} value={value}>
                            {t(`drawer.payment.methods.${value}`)}
                          </option>
                        ))}
                      </select>
                    </label>
                    {isManualPaymentMethod ? (
                      <label className="min-w-48 flex-1 space-y-1 text-xs">
                        <span className="text-slate-600">
                          {paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReference")
                            : t("page.form.manualCardReference")}
                        </span>
                        <input
                          type="text"
                          required
                          maxLength={120}
                          value={paymentReferenceInput}
                          onChange={(event) => setPaymentReferenceInput(event.target.value)}
                          placeholder={paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReferencePlaceholder")
                            : t("page.form.manualCardReferencePlaceholder")}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                          aria-label={paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReference")
                            : t("page.form.manualCardReference")}
                        />
                        <span className="block text-slate-500">
                          {paymentMethod === "bank_transfer"
                            ? t("page.form.manualTransferReferenceHint")
                            : t("page.form.manualCardReferenceHint")}
                        </span>
                      </label>
                    ) : null}
                    <button
                      type="button"
                      onClick={handlePay}
                      disabled={
                        paymentMutation.isPending ||
                        !paymentQuote ||
                        (Boolean(reservation.company_id) && (companyNightChargesQuery.isLoading || companyNightChargesQuery.isError)) ||
                        (deferredCompanyBilling
                          ? selectedCompanyChargeIds.length === 0 || selectedCompanyChargeTotal <= 0
                          : hasUnpaidCompanyCharges &&
                            (selectedCompanyChargeIds.length > 0
                              ? selectedCompanyChargeTotal <= 0
                              : companyBaseBalanceDue <= 0.01))
                      }
                      className="rounded-lg border border-brand-600 bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {paymentMutation.isPending ? t("drawer.payment.submitting") : t("drawer.payment.submit")}
                    </button>
                  </div>
                  {paymentQuoteQuery.isError ? (
                    <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert" data-testid="reservation-drawer-payment-quote-error">
                      {t("page.errors.paymentQuoteUnavailable")}
                    </p>
                  ) : paymentQuoteQuery.isLoading || !paymentQuote ? (
                    <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600" role="status">
                      {t("page.form.paymentQuoteLoading")}
                    </p>
                  ) : (
                    <div className="mt-3">
                      <PaymentQuoteSummary quote={paymentQuote} showCashSuggestion={paymentMethod === "cash"} />
                    </div>
                  )}
                  {paymentMethod === "cash" && paymentCashPreviewTotal > 0 ? (
                    <div className="mt-3">
                      <CashTenderField
                        amount={cashReceivedAmountInput}
                        tipAmount={cashTipAmountInput}
                        expectedAmount={paymentCashPreviewTotal}
                        currency={currencyCode}
                        label={t("page.form.cashReceived", { currency: currencyCode })}
                        hint={t("page.form.cashReceivedHint")}
                        changeLabel={t("page.form.cashChange")}
                        tipToggleLabel={t("page.form.cashTipToggle")}
                        tipAmountLabel={t("page.form.cashTipAmount")}
                        tipHint={t("page.form.cashTipHint")}
                        invalidAmountMessage={t("page.form.cashReceivedInvalid")}
                        insufficientMessage={t("page.form.cashReceivedInsufficient", { amount: formatMoney(paymentCashPreviewTotal, currencyCode) })}
                        tipInvalidMessage={t("page.form.cashTipInvalid")}
                        onChange={setCashReceivedAmountInput}
                        onTipAmountChange={setCashTipAmountInput}
                        testId="reservation-drawer-cash-received"
                        disabled={paymentMutation.isPending}
                      />
                    </div>
                  ) : null}
                </section>
              )}

              {operations?.pending_actions && operations.pending_actions.length > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-amber-800">{t("drawer.pendingActionsTitle")}</p>
                  <ul className="mt-2 space-y-1">
                    {operations.pending_actions.map((action) => (
                      <li key={`${action.reservation_id}:${action.action_key}`} className="text-sm text-amber-900">
                        {action.title}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {pendingActionMessage ? (
                <p
                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900"
                  data-testid="drawer-action-pending"
                  role="status"
                  aria-live="polite"
                  aria-atomic="true"
                >
                  {pendingActionMessage}
                </p>
              ) : null}

              {(actionError || actionMessage) && (
                <div
                  className={`rounded-lg border px-3 py-2 text-sm ${
                    actionError ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-800"
                  }`}
                >
                  {actionError || actionMessage}
                </div>
              )}

              {checkinDataLoading ? (
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600" role="status">
                  {t("drawer.checkinCapture.loading")}
                </p>
              ) : null}
              {checkinDataError ? (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700" role="alert">
                  <span>{t("drawer.checkinCapture.loadFailed")}</span>
                  <button
                    type="button"
                    onClick={() => void Promise.all([guestQuery.refetch(), checkinValidation.refetch()])}
                    disabled={checkinDataLoading}
                    className="font-semibold underline underline-offset-2 disabled:opacity-60"
                  >
                    {t("drawer.checkinCapture.retry")}
                  </button>
                </div>
              ) : null}

              <section className="flex flex-wrap gap-2 border-t border-slate-200 pt-3">
                {canPartialCheckIn(reservation.status) && (
                  <button
                    type="button"
                    disabled={partialCheckInMutation.isPending || !checkinDataReady}
                    onClick={() =>
                      void runAction(
                        t("drawer.actions.labels.partialCheckIn"),
                        () => partialCheckInMutation.mutateAsync({ id: reservation.id, guest: needsCheckinCapture ? buildGuestPatch() : undefined }),
                        () => setActionMessage(t("drawer.messages.partialCheckInDone"))
                      )
                    }
                    className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-700 hover:border-teal-300 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {partialCheckInMutation.isPending ? t("drawer.actions.partialCheckInPending") : t("drawer.actions.partialCheckIn")}
                  </button>
                )}
                <button
                  type="button"
                  disabled={!canCheckInReservation(reservation.status) || checkInMutation.isPending || !checkinDataReady}
                  onClick={() => void submitCheckIn()}
                  className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:border-brand-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {checkInMutation.isPending ? t("drawer.actions.confirmCheckInPending") : t("drawer.actions.confirmCheckIn")}
                </button>
                <button
                  type="button"
                  disabled={!canCheckOutReservation(reservation.status) || checkOutMutation.isPending}
                  onClick={() =>
                    void runAction(
                      t("drawer.actions.labels.checkOut"),
                      () => checkOutMutation.mutateAsync(reservation.id),
                      () => setActionMessage(t("drawer.messages.checkOutDone"))
                    )
                  }
                  className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:border-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {checkOutMutation.isPending ? t("drawer.actions.checkOutPending") : t("drawer.actions.checkOut")}
                </button>
                {canCancelReservation(reservation.status) ? (
                  <div className="min-w-full space-y-2">
                    {!cancellationRequirementsKnown ? (
                      <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700" role="status">
                        {t("drawer.cancellationPermission.checking")}
                      </p>
                    ) : canCancelAsCurrentRole ? (
                      <button
                        type="button"
                        disabled={cancelMutation.isPending}
                        onClick={() =>
                          void runAction(
                            t("drawer.actions.labels.cancel"),
                            () => cancelMutation.mutateAsync(reservation.id),
                            () => setActionMessage(t("drawer.messages.cancelled"))
                          )
                        }
                        className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:border-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {cancelMutation.isPending ? t("drawer.actions.cancelPending") : t("drawer.actions.cancel")}
                      </button>
                    ) : canRequestTemporaryCancel ? (
                      <TemporaryCancelPermissionRequest
                        key={reservation.id}
                        reservationId={reservation.id}
                        isCancelling={cancelMutation.isPending}
                        onCancelWithToken={(token) => runAction(
                          t("drawer.actions.labels.cancel"),
                          () => cancelMutation.mutateAsync({ id: reservation.id, temporaryGrantToken: token }),
                          () => setActionMessage(t("drawer.messages.cancelled"))
                        )}
                      />
                    ) : (
                      <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950" role="alert">
                        {reservation.company_id && !canManageCompanyCharges
                          ? t("drawer.cancellationPermission.companyRestricted")
                          : hasPaymentHistory && !hasPermission("reservation:cancel_paid")
                            ? t("drawer.cancellationPermission.paidRestricted")
                            : t("drawer.cancellationPermission.roleRestricted")}
                      </p>
                    )}
                  </div>
                ) : null}
              </section>
            </>
          )}
        </div>
      </div>

      {restrictionOverridePrompt.phase !== "idle" ? (
        <RestrictionOverrideModal
          phase={restrictionOverridePrompt.phase}
          onSubmit={restrictionOverridePrompt.submit}
          onCancel={restrictionOverridePrompt.dismiss}
          isPending={checkInMutation.isPending}
        />
      ) : null}
      <ConfirmDialog
        open={companyExtensionConfirmOpen && companyExtensionPreview !== null}
        title={t("drawer.companyExtension.confirmTitle")}
        message={extensionImpactMessage(
          t,
          t("drawer.companyExtension.confirmMessage", { date: companyExtensionCheckoutDate }),
          companyExtensionPreview?.impact_plan
        )}
        confirmLabel={t("drawer.companyExtension.confirmApply")}
        cancelLabel={t("drawer.companyExtension.cancel")}
        danger={false}
        onConfirm={() => void handleApplyCompanyExtension()}
        onCancel={() => setCompanyExtensionConfirmOpen(false)}
      />
      <ConfirmDialog
        open={individualExtensionConfirmOpen && individualExtensionPreview !== null}
        title={t("drawer.individualExtension.confirmTitle")}
        message={extensionImpactMessage(
          t,
          t("drawer.individualExtension.confirmMessage", {
            date: individualExtensionPreview?.new_checkout_date ?? individualExtensionCheckoutDate,
            amount: individualExtensionPreview
              ? formatMoney(Number(individualExtensionPreview.extension_amount), individualExtensionPreview.currency_code)
              : ""
          }),
          individualExtensionPreview?.impact_plan
        )}
        confirmLabel={individualExtensionMutation.isPending
          ? t("drawer.individualExtension.applying")
          : t("drawer.individualExtension.confirmApply")}
        cancelLabel={t("drawer.individualExtension.cancel")}
        danger={false}
        onConfirm={() => void handleConfirmIndividualExtension()}
        onCancel={() => {
          if (individualExtensionMutation.isPending) return;
          setIndividualExtensionConfirmOpen(false);
          setIndividualExtensionPreview(null);
        }}
      />
    </div>
  );
}

export default ReservationDetailDrawer;
