import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { GuestUpdatePayload } from "../api/guests";
import type { Reservation, ReservationGuestArrival } from "../api/reservations";
import { ApiError } from "../api/client";
import { useReservationGuestArrivals, useReservationMutations, useValidateGuestCheckin } from "../hooks/useReservations";
import { useGuest } from "../hooks/useGuests";
import { useRestrictionOverridePrompt } from "../hooks/useRestrictionOverridePrompt";
import { RestrictionOverrideModal } from "./RestrictionOverrideModal";

type GuestProfile = {
  id: number;
  first_name: string;
  last_name: string;
};

type GuestArrivalRowProps = {
  guest: GuestProfile;
  arrival?: ReservationGuestArrival;
  checkInEnabled: boolean;
  isPending: boolean;
  onCheckIn: (guestId: number, payload: GuestUpdatePayload | undefined, restrictionOverride?: {
    restriction_id: number;
    reason: string;
  }) => Promise<unknown>;
};

function GuestArrivalRow({
  guest,
  arrival,
  checkInEnabled,
  isPending,
  onCheckIn
}: GuestArrivalRowProps) {
  const { t } = useTranslation("reservations");
  const guestQuery = useGuest(guest.id);
  const validationQuery = useValidateGuestCheckin(guest.id);
  const restrictionPrompt = useRestrictionOverridePrompt();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<GuestUpdatePayload>({ terms_accepted: false });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!guestQuery.data) return;
    setForm({
      document_type: guestQuery.data.document_type ?? undefined,
      document_number: guestQuery.data.document_number ?? undefined,
      nationality: guestQuery.data.nationality ?? undefined,
      country: guestQuery.data.country ?? undefined,
      birth_place: guestQuery.data.birth_place ?? undefined,
      birth_country: guestQuery.data.birth_country ?? undefined,
      marital_status: guestQuery.data.marital_status ?? undefined,
      occupation: guestQuery.data.occupation ?? undefined,
      terms_accepted: false
    });
  }, [guestQuery.data]);

  const validation = validationQuery.data;
  const profileNeedsWork = validation?.valid === false;
  const arrivalTime = arrival
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(arrival.arrived_at))
    : null;

  const submit = async (restrictionOverride?: { restriction_id: number; reason: string }) => {
    setError(null);
    try {
      const payload = profileNeedsWork
        ? {
            document_type: form.document_type || undefined,
            document_number: form.document_number?.trim() || undefined,
            nationality: form.nationality?.trim() || undefined,
            country: form.country?.trim() || undefined,
            birth_place: form.birth_place?.trim() || undefined,
            birth_country: form.birth_country?.trim() || undefined,
            marital_status: form.marital_status?.trim() || undefined,
            occupation: form.occupation?.trim() || undefined,
            terms_accepted: form.terms_accepted === true
          }
        : undefined;
      await onCheckIn(guest.id, payload, restrictionOverride);
      setFormOpen(false);
    } catch (cause) {
      if (restrictionPrompt.handleError(cause, (override) => void submit(override))) return;
      setError(cause instanceof ApiError ? cause.message : t("drawer.guestArrivals.checkInFailed"));
    }
  };

  const setTextField = (field: keyof GuestUpdatePayload, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));

  return (
    <li className="rounded-md border border-slate-200 bg-white px-3 py-2" data-testid={"guest-arrival-row-" + guest.id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-slate-800">{guest.first_name} {guest.last_name}</p>
          {arrival ? (
            <p className="mt-1 text-xs text-emerald-800" role="status">
              {t("drawer.guestArrivals.arrivedAt", { time: arrivalTime })}
              {" · "}
              {t("drawer.guestArrivals.recordedBy", { actor: arrival.actor_display_name || arrival.actor_role })}
            </p>
          ) : profileNeedsWork ? (
            <p className="mt-1 text-xs text-amber-800">{t("drawer.guestArrivals.profileIncomplete")}</p>
          ) : validationQuery.isError || guestQuery.isError ? (
            <p className="mt-1 text-xs text-rose-700" role="alert">{t("drawer.guestArrivals.profileUnavailable")}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-500">{t("drawer.guestArrivals.pending")}</p>
          )}
        </div>
        {!arrival && checkInEnabled ? (
          <div className="flex flex-wrap gap-2">
            {profileNeedsWork ? (
              <button
                type="button"
                onClick={() => setFormOpen((open) => !open)}
                className="min-h-9 rounded-md border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900"
              >
                {formOpen ? t("drawer.guestArrivals.hideProfile") : t("drawer.guestArrivals.completeProfile")}
              </button>
            ) : null}
            <button
              type="button"
              disabled={isPending || !validation?.valid || guestQuery.isLoading || validationQuery.isLoading}
              onClick={() => void submit()}
              className="min-h-9 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid={"guest-arrival-submit-" + guest.id}
            >
              {isPending ? t("drawer.guestArrivals.submitting") : t("drawer.guestArrivals.register")}
            </button>
          </div>
        ) : null}
      </div>

      {profileNeedsWork && formOpen && !arrival ? (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3" data-testid={"guest-arrival-profile-" + guest.id}>
          <p className="text-xs text-amber-800">{(validation?.errors ?? []).join("; ")}</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-xs text-slate-600">
              {t("drawer.checkinCapture.documentType")}
              <select
                value={form.document_type ?? ""}
                onChange={(event) => setTextField("document_type", event.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="">{t("drawer.checkinCapture.documentTypeUnspecified")}</option>
                <option value="DNI">{t("drawer.checkinCapture.documentTypeDni")}</option>
                <option value="PASSPORT">{t("drawer.checkinCapture.documentTypePassport")}</option>
                <option value="CEDULA">{t("drawer.checkinCapture.documentTypeCedula")}</option>
              </select>
            </label>
            {([
              ["document_number", "documentNumber"],
              ["nationality", "nationality"],
              ["country", "country"],
              ["birth_place", "birthPlace"],
              ["birth_country", "birthCountry"],
              ["marital_status", "maritalStatus"],
              ["occupation", "occupation"]
            ] as const).map(([field, label]) => (
              <label key={field} className="text-xs text-slate-600">
                {t("drawer.checkinCapture." + label)}
                <input
                  value={String(form[field] ?? "")}
                  onChange={(event) => setTextField(field, event.target.value)}
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
                />
              </label>
            ))}
          </div>
          <label className="flex items-start gap-2 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={form.terms_accepted === true}
              onChange={(event) => setForm((current) => ({ ...current, terms_accepted: event.target.checked }))}
              className="mt-0.5"
            />
            {t("drawer.checkinCapture.acceptTerms")}
          </label>
          <div className="flex justify-end">
            <button
              type="button"
              disabled={isPending || !validation?.valid}
              onClick={() => void submit()}
              className="min-h-9 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isPending ? t("drawer.guestArrivals.submitting") : t("drawer.guestArrivals.completeAndRegister")}
            </button>
          </div>
        </div>
      ) : null}
      {error ? <p className="mt-2 text-xs text-rose-700" role="alert">{error}</p> : null}
      {restrictionPrompt.phase !== "idle" ? (
        <RestrictionOverrideModal
          phase={restrictionPrompt.phase}
          onSubmit={restrictionPrompt.submit}
          onCancel={restrictionPrompt.dismiss}
          isPending={isPending}
        />
      ) : null}
    </li>
  );
}

export function ReservationGuestArrivalPanel({ reservation, canCheckIn }: { reservation: Reservation; canCheckIn: boolean }) {
  const { t } = useTranslation("reservations");
  const summaryQuery = useReservationGuestArrivals(reservation.id);
  const { checkInGuestMutation } = useReservationMutations();
  const primaryGuest = reservation.guest
    ? {
        id: reservation.guest.id,
        first_name: reservation.guest.first_name,
        last_name: reservation.guest.last_name
      }
    : { id: reservation.guest_id, first_name: t("drawer.guests.guestFallbackNone"), last_name: "" };
  const guests = [
    primaryGuest,
    ...(reservation.additional_guests ?? []).map((guest) => ({
      id: guest.id,
      first_name: guest.first_name,
      last_name: guest.last_name
    }))
  ];
  const arrivals = summaryQuery.data?.arrivals ?? [];
  const terminal = reservation.status === "cancelled" || reservation.status === "no_show" || reservation.status === "checked_out";

  return (
    <section className="rounded-lg border border-emerald-200 bg-emerald-50/40 p-3" data-testid="reservation-guest-arrivals">
      <p className="text-xs uppercase tracking-wide text-emerald-900">{t("drawer.guestArrivals.title")}</p>
      {summaryQuery.isLoading ? (
        <p className="mt-2 text-xs text-slate-500">{t("drawer.guestArrivals.loading")}</p>
      ) : summaryQuery.isError ? (
        <div className="mt-2 flex items-center justify-between gap-2 text-xs text-rose-700" role="alert">
          <span>{t("drawer.guestArrivals.loadFailed")}</span>
          <button type="button" onClick={() => void summaryQuery.refetch()} className="font-semibold underline">
            {t("drawer.guestArrivals.retry")}
          </button>
        </div>
      ) : summaryQuery.data ? (
        <>
          <p className="mt-1 text-xs text-slate-600">
            {t("drawer.guestArrivals.progress", {
              arrived: summaryQuery.data.arrived_guest_count,
              expected: summaryQuery.data.expected_guest_count
            })}
            {" · "}
            {summaryQuery.data.status_policy === "partial_checkin"
              ? t("drawer.guestArrivals.partialPolicy")
              : t("drawer.guestArrivals.firstGuestPolicy")}
          </p>
          {summaryQuery.data.missing_profile_count > 0 ? (
            <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900" role="status">
              {t("drawer.guestArrivals.missingProfiles", { count: summaryQuery.data.missing_profile_count })}
            </p>
          ) : null}
          <ul className="mt-2 space-y-2">
            {guests.map((guest) => (
              <GuestArrivalRow
                key={guest.id}
                guest={guest}
                arrival={arrivals.find((item) => item.guest_id === guest.id)}
                checkInEnabled={canCheckIn && !terminal}
                isPending={checkInGuestMutation.isPending}
                onCheckIn={async (guestId, payload, restrictionOverride) => {
                  await checkInGuestMutation.mutateAsync({
                    reservationId: reservation.id,
                    guestId,
                    payload: { guest: payload, restriction_override: restrictionOverride }
                  });
                }}
              />
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
