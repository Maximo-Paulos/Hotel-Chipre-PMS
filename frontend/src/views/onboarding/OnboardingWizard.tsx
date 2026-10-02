import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import {
  finishOnboarding,
  getOnboardingStatus,
  setCategories,
  setDepositPolicy,
  setHotelIdentity,
  setOtaChannels,
  setOwner as persistOwner,
  setPaymentMethods,
  setRooms,
  setStaff,
  setSubscriptionChoice,
  type CategoryPayload,
  type DepositPolicyPayload,
  type HotelIdentityPayload,
  type OnboardingProviderSetup,
  type OnboardingSubscription,
  type OnboardingStatus,
  type OTAChannelsPayload,
  type OwnerPayload,
  type PaymentMethodsPayload,
  type RoomPayload,
  type StaffPayload,
  type SubscriptionChoicePayload
} from "../../api/onboarding";
import { refreshAfterMutation } from "../../api/queryInvalidation";
import type { QueryDomain } from "../../api/queryKeys";
import { onboardingStatusKey, useOnboardingStatus } from "../../hooks/useOnboardingStatus";
import { useSubscriptionPlans } from "../../hooks/useSubscription";
import { useTimezones } from "../../hooks/useTimezones";
import { useSession } from "../../state/session";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { formatHotelDate } from "../../utils/date";

const steps = [
  { path: "", label: "Owner" },
  { path: "identity", label: "Identidad" },
  { path: "categories", label: "Categorías" },
  { path: "subscription", label: "Suscripción" },
  { path: "rooms", label: "Habitaciones" },
  { path: "policy", label: "Política" },
  { path: "payments", label: "Pagos" },
  { path: "ota", label: "OTAs" },
  { path: "staff", label: "Staff" }
];

const isOnboardingPath = (pathname: string) => pathname === "/onboarding" || pathname.startsWith("/onboarding/");

const defaultIdentityForm: HotelIdentityPayload = {
  name: "",
  timezone: "America/Argentina/Buenos_Aires",
  currency: "ARS",
  languages: ["es"],
  jurisdiction_code: "AR"
};

const defaultPolicyForm: DepositPolicyPayload = {
  deposit_percentage: 30,
  free_cancellation_hours: 48,
  cancellation_penalty_percentage: 0
};

const emptyProviderSetup = (): OnboardingProviderSetup => ({ enabled: false, credentials: {} });

const defaultPaymentsForm: PaymentMethodsPayload = {
  enable_cash: true,
  enable_bank_transfer: false,
  enable_debit_card: false,
  enable_credit_card: false,
  mercado_pago: emptyProviderSetup(),
  paypal: emptyProviderSetup(),
  stripe: emptyProviderSetup()
};

const defaultOtaForm: OTAChannelsPayload = {
  booking: emptyProviderSetup(),
  expedia: emptyProviderSetup(),
  despegar: emptyProviderSetup()
};

const defaultSubscriptionForm: SubscriptionChoicePayload = {
  plan_code: "pro",
  start_trial: true
};

const inputClassName =
  "rounded-lg border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500";

type StepStatus = Awaited<ReturnType<typeof getOnboardingStatus>>;
type StaffDraft = StaffPayload & { clientKey: string };

let staffDraftSequence = 0;
const createStaffDraft = (member: StaffPayload = { name: "", role: "receptionist", email: "" }): StaffDraft => ({
  ...member,
  clientKey: `staff-draft-${++staffDraftSequence}`
});

export function OnboardingWizard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSession();
  const plansQuery = useSubscriptionPlans();
  const timezonesQuery = useTimezones();
  const { data: status, isFetching, refetch } = useOnboardingStatus();

  const [ownerForm, setOwnerForm] = useState<OwnerPayload>({
    name: "",
    email: session.email || "",
    phone: "",
    role: "Owner"
  });
  const [identityForm, setIdentityForm] = useState<HotelIdentityPayload>(defaultIdentityForm);
  const [categories, setCategoriesState] = useState<CategoryPayload[]>([]);
  const [rooms, setRoomsState] = useState<RoomPayload[]>([]);
  const [policyForm, setPolicyForm] = useState<DepositPolicyPayload>(defaultPolicyForm);
  const [paymentsForm, setPaymentsForm] = useState<PaymentMethodsPayload>(defaultPaymentsForm);
  const [otaForm, setOtaForm] = useState<OTAChannelsPayload>(defaultOtaForm);
  const [subscriptionForm, setSubscriptionForm] = useState<SubscriptionChoicePayload>(defaultSubscriptionForm);
  const [staff, setStaffState] = useState<StaffDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const paymentMethodsHydratedForHotel = useRef<number | null>(null);
  const otaChannelsHydratedForHotel = useRef<number | null>(null);

  useEffect(() => {
    if (!status) return;

    if (status.owner && !ownerForm.name) {
      setOwnerForm((prev) => ({
        ...prev,
        name: String(status.owner?.name ?? prev.name ?? ""),
        email: String(status.owner?.email ?? prev.email ?? session.email ?? ""),
        phone: String(status.owner?.phone ?? prev.phone ?? ""),
        role: String(status.owner?.role ?? prev.role ?? "Owner")
      }));
    }

    if (status.hotel_identity && !identityForm.name) {
      setIdentityForm({
        name: String(status.hotel_identity.name ?? ""),
        timezone: String(status.hotel_identity.timezone ?? defaultIdentityForm.timezone),
        currency: String(status.hotel_identity.currency ?? defaultIdentityForm.currency),
        languages: Array.isArray(status.hotel_identity.languages)
          ? status.hotel_identity.languages.map((value) => String(value))
          : defaultIdentityForm.languages,
        jurisdiction_code: String(status.hotel_identity.jurisdiction_code ?? defaultIdentityForm.jurisdiction_code)
      });
    }

    if (status.categories?.length && !categories.length) {
      setCategoriesState(status.categories);
    }

    if (status.rooms?.length && !rooms.length) {
      setRoomsState(status.rooms);
    }

    if (status.deposit_policy && policyForm.deposit_percentage === defaultPolicyForm.deposit_percentage) {
      setPolicyForm({
        deposit_percentage: Number(status.deposit_policy.deposit_percentage ?? defaultPolicyForm.deposit_percentage),
        free_cancellation_hours: Number(
          status.deposit_policy.free_cancellation_hours ?? defaultPolicyForm.free_cancellation_hours
        ),
        cancellation_penalty_percentage: Number(
          status.deposit_policy.cancellation_penalty_percentage ?? defaultPolicyForm.cancellation_penalty_percentage
        )
      });
    }

    if (status.payment_methods && paymentMethodsHydratedForHotel.current !== status.hotel_id) {
      setPaymentsForm({
        enable_cash: status.payment_method_options?.enable_cash ?? true,
        enable_bank_transfer: status.payment_method_options?.enable_bank_transfer ?? false,
        enable_debit_card: status.payment_method_options?.enable_debit_card ?? false,
        enable_credit_card: status.payment_method_options?.enable_credit_card ?? false,
        mercado_pago: hydrateProvider(status.payment_methods.mercado_pago),
        paypal: hydrateProvider(status.payment_methods.paypal),
        stripe: hydrateProvider(status.payment_methods.stripe)
      });
      paymentMethodsHydratedForHotel.current = status.hotel_id;
    }

    if (status.ota_channels && otaChannelsHydratedForHotel.current !== status.hotel_id) {
      setOtaForm({
        booking: hydrateProvider(status.ota_channels.booking),
        expedia: hydrateProvider(status.ota_channels.expedia),
        despegar: hydrateProvider(status.ota_channels.despegar)
      });
      otaChannelsHydratedForHotel.current = status.hotel_id;
    }

    if (status.subscription_choice && subscriptionForm.plan_code === defaultSubscriptionForm.plan_code) {
      setSubscriptionForm({
        plan_code: String(status.subscription_choice.plan_code ?? defaultSubscriptionForm.plan_code),
        start_trial: Boolean(status.subscription_choice.start_trial)
      });
    } else if (
      status.current_subscription &&
      status.current_subscription.trial_available !== true &&
      subscriptionForm.plan_code === defaultSubscriptionForm.plan_code
    ) {
      setSubscriptionForm({
        plan_code: String(status.current_subscription.plan ?? defaultSubscriptionForm.plan_code),
        start_trial: false
      });
    }

    if (status.staff?.length && !staff.length) {
      setStaffState(status.staff.map((member) => createStaffDraft(member)));
    }
  }, [
    categories.length,
    identityForm.name,
    ownerForm.name,
    policyForm.deposit_percentage,
    rooms.length,
    session.email,
    staff.length,
    status,
    subscriptionForm.plan_code
  ]);

  const refreshCache = (data: OnboardingStatus) =>
    queryClient.setQueryData(onboardingStatusKey(session.hotelId, session.userId), data);

  const runWithFeedback = async (
    action: () => Promise<OnboardingStatus>,
    successMessage: string,
    domains: readonly QueryDomain[]
  ) => {
    setError(null);
    setToast(null);
    try {
      const data = await action();
      refreshCache(data);
      await refreshAfterMutation(queryClient, session.hotelId, domains);
      setToast(successMessage);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar este paso.");
      throw err;
    }
  };

  const ownerMutation = useGuardedMutation({
    mutationFn: () => runWithFeedback(() => persistOwner(ownerForm, session), "Owner guardado.", ["onboarding", "settings", "users"])
  });

  const identityMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setHotelIdentity(identityForm, session), "Identidad del hotel guardada.", [
        "onboarding",
        "settings",
        "rooms",
        "reservations"
      ])
  });

  const categoriesMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setCategories(categories, session), "Categorías guardadas.", [
        "onboarding",
        "rooms",
        "reservations",
        "analytics"
      ])
  });

  const roomsMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setRooms(rooms, session), "Habitaciones guardadas.", [
        "onboarding",
        "rooms",
        "reservations",
        "analytics"
      ])
  });

  const policyMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setDepositPolicy(policyForm, session), "Política guardada.", [
        "onboarding",
        "settings",
        "payments",
        "reservations"
      ])
  });

  const paymentsMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setPaymentMethods(paymentsForm, session), "Pagos guardados.", [
        "onboarding",
        "settings",
        "payments"
      ])
  });

  const otaMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setOtaChannels(otaForm, session), "Canales OTA guardados.", [
        "onboarding",
        "settings",
        "reservations",
        "rooms"
      ])
  });

  const subscriptionMutation = useGuardedMutation({
    mutationFn: () =>
      runWithFeedback(() => setSubscriptionChoice(subscriptionForm, session), "Suscripción configurada.", [
        "onboarding",
        "settings"
      ])
  });

  const staffMutation = useGuardedMutation({
    mutationFn: async () => {
      const result = await runWithFeedback(
        () => setStaff(staff.map((member) => ({
          name: member.name,
          role: member.role,
          email: member.email,
          phone: member.phone
        })), session),
        "Staff guardado.",
        ["onboarding", "users", "settings"]
      );
      const deliveries = result.staff_invitations ?? [];
      if (deliveries.length) {
        const sent = deliveries.filter((item) => item.email_delivery === "sent").length;
        const failed = deliveries.filter((item) => item.email_delivery === "failed").length;
        const notConfigured = deliveries.filter((item) => item.email_delivery === "not_configured").length;
        const summary = [
          sent ? `${sent} enviada${sent === 1 ? "" : "s"}` : "",
          failed ? `${failed} sin enviar` : "",
          notConfigured ? `${notConfigured} con correo sin configurar` : ""
        ].filter(Boolean).join("; ");
        setToast(`Personal guardado. Invitaciones: ${summary}.`);
      }
      return result;
    }
  });

  const finishMutation = useGuardedMutation({
    mutationFn: async () => {
      setError(null);
      setToast(null);
      await refreshStatus(refetch);
      return runWithFeedback(() => finishOnboarding(session), "Onboarding finalizado.", ["onboarding", "settings"]);
    },
    onSuccess: () => {
      if (typeof window !== "undefined" && isOnboardingPath(window.location.pathname)) {
        navigate("/dashboard", { replace: true });
      }
    }
  });

  const bannerText = useMemo(() => {
    if (!status || status.completed) return null;
    return `Falta: ${status.missing_steps.join(", ")}`;
  }, [status]);

  useEffect(() => {
    if (status?.completed && typeof window !== "undefined" && isOnboardingPath(window.location.pathname)) {
      navigate("/dashboard", { replace: true });
    }
  }, [status?.completed, navigate]);

  const currentSubscription = status?.current_subscription;
  const availablePlans = plansQuery.data ?? [];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Puesta en marcha</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Configurá tu hotel</h1>
        </div>
        <Link to="/dashboard" className="text-sm text-brand-700 hover:underline">
          Ir al dashboard
        </Link>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-600">
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">Hotel ID: {session.hotelId}</span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">Usuario: {session.email || session.userId}</span>
        {bannerText && <span className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800">{bannerText}</span>}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {steps.map((step, idx) => (
          <Link
            key={step.path}
            // ponytail: absolute path, not relative -- react-router-dom v7 made
            // v7_relativeSplatPath the default, so a relative `to` here now
            // resolves against the full "/onboarding/<current-step>" splat match
            // instead of the "/onboarding" base, stacking segments on every click
            // (e.g. /onboarding/identity/finish). Absolute paths sidestep that.
            to={`/onboarding${step.path ? `/${step.path}` : ""}`}
            className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700"
          >
            {idx + 1}. {step.label}
          </Link>
        ))}
        <Link
          to="/onboarding/finish"
          className="rounded-full border border-emerald-200 px-3 py-1 text-xs font-medium text-emerald-700 hover:border-emerald-400"
        >
          Finalizar
        </Link>
      </div>
      {status?.readiness_checklist?.length ? (
        <section className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4" aria-labelledby="readiness-title">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 id="readiness-title" className="text-sm font-semibold text-slate-900">Preparación para operar</h2>
              <p className="mt-1 text-xs text-slate-600">
                Verificamos los datos reales del hotel. Las conexiones externas son opcionales.
              </p>
            </div>
            {status.readiness_complete ? (
              <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800">Lista para operar</span>
            ) : (
              <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">Hay pasos pendientes</span>
            )}
          </div>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Lista de preparación">
            {status.readiness_checklist.map((item) => (
              <li key={item.key} className="flex items-center justify-between gap-3 rounded-lg bg-white px-3 py-2 text-sm">
                <span className={item.done ? "text-slate-700" : "text-slate-900"}>
                  <span aria-hidden="true" className="mr-2">{item.done ? "✓" : "○"}</span>
                  {item.label}{item.optional ? " (opcional)" : ""}
                </span>
                {!item.done && (
                  <Link to={item.route} className="shrink-0 text-xs font-medium text-brand-700 hover:underline">
                    Abrir
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {error && <p className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      {toast && <p role="status" className="mt-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{toast}</p>}

      <div className="mt-6">
        <Routes>
          <Route
            index
            element={
              <OwnerStep
                form={ownerForm}
                setForm={setOwnerForm}
                onSave={async () => {
                  await ownerMutation.mutateAsync();
                  navigate("/onboarding/identity");
                }}
                loading={ownerMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="identity"
            element={
              <IdentityStep
                form={identityForm}
                setForm={setIdentityForm}
                timezones={timezonesQuery.data ?? []}
                onSave={async () => {
                  await identityMutation.mutateAsync();
                  navigate("/onboarding/categories");
                }}
                loading={identityMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="categories"
            element={
              <CategoriesStep
                categories={categories}
                setCategories={setCategoriesState}
                onSave={async () => {
                  await categoriesMutation.mutateAsync();
                  navigate("/onboarding/subscription");
                }}
                loading={categoriesMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="rooms"
            element={
              <RoomsStep
                categories={categories}
                rooms={rooms}
                setRooms={setRoomsState}
                onSave={async () => {
                  await roomsMutation.mutateAsync();
                  navigate("/onboarding/policy");
                }}
                loading={roomsMutation.isPending}
                status={status}
                roomLimit={
                  Number(currentSubscription?.room_limit) > 0 ? Number(currentSubscription?.room_limit) : undefined
                }
                isTrialing={currentSubscription?.status === "trialing"}
                trialEndAt={currentSubscription?.trial_end_at}
                hotelTimeZone={identityForm.timezone}
              />
            }
          />
          <Route
            path="policy"
            element={
              <PolicyStep
                form={policyForm}
                setForm={setPolicyForm}
                onSave={async () => {
                  await policyMutation.mutateAsync();
                  navigate("/onboarding/payments");
                }}
                loading={policyMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="payments"
            element={
              <PaymentsStep
                form={paymentsForm}
                setForm={setPaymentsForm}
                onSave={async () => {
                  await paymentsMutation.mutateAsync();
                  navigate("/onboarding/ota");
                }}
                loading={paymentsMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="ota"
            element={
              <OtaStep
                form={otaForm}
                setForm={setOtaForm}
                onSave={async () => {
                  await otaMutation.mutateAsync();
                  navigate("/onboarding/staff");
                }}
                loading={otaMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="subscription"
            element={
              <SubscriptionStep
                form={subscriptionForm}
                setForm={setSubscriptionForm}
                onSave={async () => {
                  await subscriptionMutation.mutateAsync();
                  navigate("/onboarding/rooms");
                }}
                loading={subscriptionMutation.isPending}
                status={status}
                plans={availablePlans}
                currentSubscription={currentSubscription}
                stripeEnabled={Boolean(paymentsForm.stripe.enabled)}
              />
            }
          />
          <Route
            path="staff"
            element={
              <StaffStep
                staff={staff}
                setStaff={setStaffState}
                canAssignCoOwner={(session.baseRole ?? session.role) === "owner"}
                onSave={async () => {
                  await staffMutation.mutateAsync();
                  navigate("/onboarding/finish");
                }}
                loading={staffMutation.isPending}
                status={status}
              />
            }
          />
          <Route
            path="finish"
            element={
              <FinishStep
                status={status}
                isFetching={isFetching}
                loading={finishMutation.isPending}
                currentSubscription={currentSubscription}
                onFinish={async () => {
                  await finishMutation.mutateAsync();
                }}
              />
            }
          />
        </Routes>
      </div>
    </div>
  );
}

const refreshStatus = async (refetch: () => Promise<unknown>) => {
  try {
    await refetch();
  } catch {
    /* silent */
  }
};

const hydrateProvider = (provider?: OnboardingProviderSetup | null): OnboardingProviderSetup => ({
  enabled: Boolean(provider?.enabled),
  credentials: {}
});

function OwnerStep({
  form,
  setForm,
  onSave,
  loading,
  status
}: {
  form: OwnerPayload;
  setForm: (payload: OwnerPayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const handleChange = (field: keyof OwnerPayload, value: string) => setForm({ ...form, [field]: value });

  return (
    <StepCard title="Owner principal" status={status}>
      <form className="space-y-3" onSubmit={(event) => event.preventDefault()}>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Nombre completo">
            <input
              className={inputClassName}
              value={form.name}
              onChange={(event) => handleChange("name", event.target.value)}
              placeholder="Ej: Ana Manager"
              required
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              className={inputClassName}
              value={form.email}
              onChange={(event) => handleChange("email", event.target.value)}
              placeholder="Ej: admin@hotel.test"
              required
            />
          </Field>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Teléfono">
            <input
              className={inputClassName}
              value={form.phone || ""}
              placeholder="Ej: +54 9 11 5555 1234"
              onChange={(event) => handleChange("phone", event.target.value)}
            />
          </Field>
          <Field label="Rol">
            <input
              className={inputClassName}
              value={form.role || ""}
              placeholder="Ej: Owner"
              onChange={(event) => handleChange("role", event.target.value)}
            />
          </Field>
        </div>
        <StepActions onSave={onSave} loading={loading} helpText="Guarda owner en /api/onboarding/owner" />
      </form>
    </StepCard>
  );
}

function IdentityStep({
  form,
  setForm,
  timezones,
  onSave,
  loading,
  status
}: {
  form: HotelIdentityPayload;
  setForm: (payload: HotelIdentityPayload) => void;
  timezones: string[];
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const timezoneListId = "timezone-options";
  return (
    <StepCard title="Identidad del hotel" status={status}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Nombre del hotel">
          <input
            className={inputClassName}
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder="Ej: Hotel Chipre Centro"
          />
        </Field>
        <Field label="Zona horaria">
          <input
            className={inputClassName}
            value={form.timezone}
            onChange={(event) => setForm({ ...form, timezone: event.target.value })}
            placeholder="Ej: America/Argentina/Buenos_Aires"
            list={timezoneListId}
          />
          <datalist id={timezoneListId}>
            {timezones.map((timezone) => (
              <option key={timezone} value={timezone} />
            ))}
          </datalist>
        </Field>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <Field label="Moneda">
          <input
            className={inputClassName}
            value={form.currency}
            onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })}
            placeholder="ARS"
          />
        </Field>
        <Field label="Idiomas">
          <input
            className={inputClassName}
            value={form.languages.join(", ")}
            onChange={(event) =>
              setForm({
                ...form,
                languages: event.target.value
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean)
              })
            }
            placeholder="es, en"
          />
        </Field>
        <Field label="Jurisdicción">
          <select
            className={inputClassName}
            value={form.jurisdiction_code}
            onChange={(event) => setForm({ ...form, jurisdiction_code: event.target.value })}
          >
            <option value="AR">AR</option>
            <option value="UY">UY</option>
            <option value="CL">CL</option>
          </select>
        </Field>
      </div>
      <StepActions onSave={onSave} loading={loading} helpText="Persistimos nombre, timezone, moneda e idioma base." />
    </StepCard>
  );
}

function CategoriesStep({
  categories,
  setCategories,
  onSave,
  loading,
  status
}: {
  categories: CategoryPayload[];
  setCategories: (data: CategoryPayload[]) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const update = (idx: number, field: keyof CategoryPayload, value: string) => {
    const parsedValue =
      field === "base_price_per_night" || field === "max_occupancy" ? Number(value || 0) : value;
    setCategories(
      categories.map((category, index) =>
        index === idx ? ({ ...category, [field]: parsedValue } as CategoryPayload) : category
      )
    );
  };

  const addCategory = () =>
    setCategories([
      ...categories,
      { name: "", code: `CAT${categories.length + 1}`, description: "", base_price_per_night: 0, max_occupancy: 1 }
    ]);

  return (
    <StepCard title="Categorías" status={status}>
      <div className="space-y-4">
        {categories.map((category, idx) => (
          <div key={`${category.code}-${idx}`} className="rounded-lg border border-slate-200 p-4">
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Nombre de categoría">
                <input
                  className={inputClassName}
                  placeholder="Ej: Standard Doble"
                  value={category.name}
                  onChange={(event) => update(idx, "name", event.target.value)}
                />
              </Field>
              <Field label="Código interno">
                <input
                  className={inputClassName}
                  placeholder="Ej: STD"
                  value={category.code}
                  onChange={(event) => update(idx, "code", event.target.value)}
                />
              </Field>
              <Field label="Amenities">
                <input
                  className={inputClassName}
                  placeholder="Ej: wifi,ac"
                  value={category.amenities || ""}
                  onChange={(event) => update(idx, "amenities", event.target.value)}
                />
              </Field>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Field label="Precio base por noche">
                <input
                  className={inputClassName}
                  type="number"
                  value={category.base_price_per_night}
                  onChange={(event) => update(idx, "base_price_per_night", event.target.value)}
                />
              </Field>
              <Field label="Ocupación máxima">
                <input
                  className={inputClassName}
                  type="number"
                  value={category.max_occupancy}
                  onChange={(event) => update(idx, "max_occupancy", event.target.value)}
                />
              </Field>
              <Field label="Descripción breve">
                <input
                  className={inputClassName}
                  placeholder="Ej: Vista al jardín"
                  value={category.description || ""}
                  onChange={(event) => update(idx, "description", event.target.value)}
                />
              </Field>
            </div>
          </div>
        ))}
        <StepFooterButton label="+ Agregar categoría" onClick={addCategory} />
        <StepActions onSave={onSave} loading={loading} />
      </div>
    </StepCard>
  );
}

function RoomsStep({
  categories,
  rooms,
  setRooms,
  onSave,
  loading,
  status,
  roomLimit,
  isTrialing,
  trialEndAt,
  hotelTimeZone
}: {
  categories: CategoryPayload[];
  rooms: RoomPayload[];
  setRooms: (data: RoomPayload[]) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
  roomLimit?: number;
  isTrialing: boolean;
  trialEndAt?: string | null;
  hotelTimeZone: string;
}) {
  const [rangeStart, setRangeStart] = useState("101");
  const [categoryRoomLoads, setCategoryRoomLoads] = useState<Record<string, { quantity: string; floor: string }>>({});
  const [rangeError, setRangeError] = useState<string | null>(null);

  useEffect(() => {
    setCategoryRoomLoads((current) => {
      const next: Record<string, { quantity: string; floor: string }> = {};
      for (const category of categories) {
        next[category.code] = current[category.code] ?? { quantity: "0", floor: "1" };
      }
      return next;
    });
  }, [categories]);

  const update = (idx: number, field: keyof RoomPayload, value: string) => {
    const parsed = field === "floor" ? Number(value || 0) : value;
    setRooms(rooms.map((room, index) => (index === idx ? { ...room, [field]: parsed } : room)));
  };

  const updateCategoryRoomLoad = (categoryCode: string, field: "quantity" | "floor", value: string) => {
    setCategoryRoomLoads((current) => ({
      ...current,
      [categoryCode]: { ...(current[categoryCode] ?? { quantity: "0", floor: "1" }), [field]: value }
    }));
  };

  const addRoomRange = () => {
    const first = Number(rangeStart);
    if (!/^\d+$/.test(rangeStart) || rangeStart.length > 10 || !Number.isSafeInteger(first)) {
      setRangeError("Ingresá un número inicial entero de hasta 10 dígitos.");
      return;
    }
    if (!categories.length) {
      setRangeError("Primero agregá al menos una categoría de habitación.");
      return;
    }

    const plans: Array<{ categoryCode: string; quantity: number; floor: number }> = [];
    let total = 0;
    for (const category of categories) {
      const draft = categoryRoomLoads[category.code] ?? { quantity: "0", floor: "1" };
      const quantity = Number(draft.quantity);
      const floor = Number(draft.floor);
      if (!/^\d+$/.test(draft.quantity) || !Number.isSafeInteger(quantity) || quantity < 0) {
        setRangeError(`La cantidad para ${category.name} debe ser un entero igual o mayor que cero.`);
        return;
      }
      if (!/^\d+$/.test(draft.floor) || !Number.isSafeInteger(floor) || floor < 0) {
        setRangeError(`El piso para ${category.name} debe ser un entero igual o mayor que cero.`);
        return;
      }
      if (quantity > 0) {
        plans.push({ categoryCode: category.code, quantity, floor });
        total += quantity;
      }
    }
    if (total < 1) {
      setRangeError("Indicá cuántas habitaciones corresponden a cada categoría.");
      return;
    }
    if (total > 200) {
      setRangeError("Podés agregar hasta 200 habitaciones por carga.");
      return;
    }
    if (roomLimit != null && rooms.length + total > roomLimit) {
      setRangeError(`Esta carga supera el límite de ${roomLimit} habitaciones de tu plan.`);
      return;
    }
    const last = first + total - 1;
    if (!Number.isSafeInteger(last) || String(last).length > 10) {
      setRangeError("El rango generado supera los 10 dígitos permitidos para el número de habitación.");
      return;
    }

    const existingNumbers = new Set(rooms.map((room) => room.room_number.trim()));
    const newRooms: RoomPayload[] = [];
    let nextNumber = first;
    for (const plan of plans) {
      for (let index = 0; index < plan.quantity; index += 1) {
        const roomNumber = String(nextNumber++);
        if (existingNumbers.has(roomNumber)) {
          setRangeError(`La habitación ${roomNumber} ya está cargada. Cambiá el número inicial.`);
          return;
        }
        newRooms.push({ room_number: roomNumber, floor: plan.floor, category_code: plan.categoryCode });
      }
    }

    setRooms([...rooms, ...newRooms]);
    setCategoryRoomLoads((current) =>
      Object.fromEntries(Object.entries(current).map(([code, draft]) => [code, { ...draft, quantity: "0" }]))
    );
    setRangeError(null);
    setRangeStart(last < 9_999_999_999 ? String(last + 1) : "");
  };

  const addRoom = () => {
    if (roomLimit != null && rooms.length >= roomLimit) {
      setRangeError(`Tu plan permite hasta ${roomLimit} habitaciones activas.`);
      return;
    }
    const defaultCategory = categories[0]?.code || "STD";
    setRooms([
      ...rooms,
      { room_number: `${rooms.length + 101}`, floor: 1, category_code: rooms[rooms.length - 1]?.category_code || defaultCategory }
    ]);
    setRangeError(null);
  };

  let previewNumber = Number(rangeStart);
  const categoryRangePreviews = categories.map((category) => {
    const draft = categoryRoomLoads[category.code] ?? { quantity: "0", floor: "1" };
    const parsedQuantity = Number(draft.quantity);
    const quantity = Number.isSafeInteger(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity : 0;
    const first = previewNumber;
    const last = quantity > 0 ? first + quantity - 1 : null;
    if (last != null) previewNumber = last + 1;
    return { category, draft, quantity, first, last };
  });
  const persistedRoomNumbers = new Set((status?.rooms ?? []).map((room) => room.room_number));
  const trialEndLabel = isTrialing && trialEndAt ? formatHotelDate(trialEndAt, hotelTimeZone) : null;

  return (
    <StepCard title="Habitaciones" status={status}>
      <div className="space-y-3">
        {trialEndLabel && (
          <p
            role="status"
            data-testid="onboarding-trial-end"
            className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-medium text-sky-900"
          >
            Prueba Pro hasta {trialEndLabel}
          </p>
        )}
        <section aria-label="Agregar habitaciones por rango" className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">Carga por rango</p>
          <p className="mt-1 text-xs text-slate-600" data-testid="onboarding-room-limit">
            {roomLimit != null
              ? `Tu plan permite hasta ${roomLimit} habitaciones activas. Cargadas: ${rooms.length}.`
              : `Habitaciones cargadas: ${rooms.length}.`}
          </p>
          <p className="mt-3 text-xs text-slate-600">
            Indicá la cantidad y el piso de cada categoría. Los números se asignan correlativamente desde el primer número.
          </p>
          <div className="mt-3 max-w-xs">
            <Field label="Primer número de habitación">
              <input
                className={inputClassName}
                inputMode="numeric"
                value={rangeStart}
                onChange={(event) => {
                  setRangeStart(event.target.value);
                  setRangeError(null);
                }}
              />
            </Field>
          </div>
          <div className="mt-3 space-y-2">
            {categoryRangePreviews.map(({ category, draft, quantity, first, last }) => (
              <div
                key={category.code}
                data-testid="onboarding-room-category-plan"
                className="grid gap-3 rounded-lg border border-slate-200 bg-white p-3 sm:grid-cols-[minmax(0,1fr)_8rem_8rem] sm:items-end"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900">{category.name}</p>
                  <p className="text-xs text-slate-500">
                    {quantity > 0 && last != null
                      ? `Habitaciones ${first}–${last} · piso ${draft.floor}`
                      : "Sin habitaciones en esta carga"}
                  </p>
                </div>
                <Field label={`Cantidad de ${category.name}`}>
                  <input
                    className={inputClassName}
                    type="number"
                    min="0"
                    step="1"
                    value={draft.quantity}
                    onChange={(event) => updateCategoryRoomLoad(category.code, "quantity", event.target.value)}
                  />
                </Field>
                <Field label={`Piso de ${category.name}`}>
                  <input
                    className={inputClassName}
                    type="number"
                    min="0"
                    step="1"
                    value={draft.floor}
                    onChange={(event) => updateCategoryRoomLoad(category.code, "floor", event.target.value)}
                  />
                </Field>
              </div>
            ))}
          </div>
          {rangeError && <p role="alert" className="mt-3 text-sm text-rose-700">{rangeError}</p>}
          <button
            className="mt-3 rounded-lg border border-brand-200 px-3 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-60"
            type="button"
            onClick={addRoomRange}
            disabled={loading}
          >
            Agregar habitaciones
          </button>
        </section>
        {rooms.map((room, idx) => (
          <div key={`${room.room_number}-${idx}`} data-testid="onboarding-room-row" className="grid gap-3 md:grid-cols-3">
            <Field label="Número de habitación">
              <input
                className={inputClassName}
                value={room.room_number}
                onChange={(event) => update(idx, "room_number", event.target.value)}
              />
            </Field>
            <Field label="Piso">
              <input
                className={inputClassName}
                type="number"
                value={room.floor}
                onChange={(event) => update(idx, "floor", event.target.value)}
              />
            </Field>
            <Field label="Categoría">
              <select
                className={inputClassName}
                value={room.category_code}
                onChange={(event) => update(idx, "category_code", event.target.value)}
              >
                <option value="">Seleccioná una categoría</option>
                {categories.map((category) => (
                  <option key={category.code} value={category.code}>
                    {category.name} ({category.code})
                  </option>
                ))}
              </select>
            </Field>
            {!persistedRoomNumbers.has(room.room_number) && (
              <button
                className="min-h-11 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
                aria-label={`Quitar habitación ${room.room_number} de esta carga`}
                onClick={() => {
                  setRooms(rooms.filter((_, index) => index !== idx));
                  setRangeError(null);
                }}
              >
                Quitar de esta carga
              </button>
            )}
          </div>
        ))}
        <StepFooterButton label="+ Agregar habitación" onClick={addRoom} />
        <StepActions onSave={onSave} loading={loading} />
      </div>
    </StepCard>
  );
}

function PolicyStep({
  form,
  setForm,
  onSave,
  loading,
  status
}: {
  form: DepositPolicyPayload;
  setForm: (payload: DepositPolicyPayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  return (
    <StepCard title="Política de depósitos y cancelación" status={status}>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Seña (%)">
          <input
            className={inputClassName}
            type="number"
            value={form.deposit_percentage}
            onChange={(event) => setForm({ ...form, deposit_percentage: Number(event.target.value || 0) })}
          />
        </Field>
        <Field label="Cancelación gratis hasta (horas)">
          <input
            className={inputClassName}
            type="number"
            value={form.free_cancellation_hours}
            onChange={(event) => setForm({ ...form, free_cancellation_hours: Number(event.target.value || 0) })}
          />
        </Field>
        <Field label="Penalidad (%)">
          <input
            className={inputClassName}
            type="number"
            value={form.cancellation_penalty_percentage}
            onChange={(event) =>
              setForm({ ...form, cancellation_penalty_percentage: Number(event.target.value || 0) })
            }
          />
        </Field>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Las restricciones fijas de plataforma se aplican en backend. No permitimos cancelación luego del check-in desde este flujo.
      </p>
      <StepActions onSave={onSave} loading={loading} />
    </StepCard>
  );
}

function PaymentsStep({
  form,
  setForm,
  onSave,
  loading,
  status
}: {
  form: PaymentMethodsPayload;
  setForm: (payload: PaymentMethodsPayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const collectionMethods: Array<{ key: keyof Pick<PaymentMethodsPayload, "enable_cash" | "enable_bank_transfer" | "enable_debit_card" | "enable_credit_card">; label: string }> = [
    { key: "enable_cash", label: "Efectivo" },
    { key: "enable_bank_transfer", label: "Transferencia" },
    { key: "enable_debit_card", label: "Tarjeta de débito" },
    { key: "enable_credit_card", label: "Tarjeta de crédito" }
  ];

  return (
    <StepCard title="Métodos de pago" status={status}>
      <fieldset>
        <legend className="text-sm font-semibold text-slate-900">¿Cómo cobrás hoy?</legend>
        <p className="mt-1 text-sm text-slate-600">Elegí los medios que acepta el hotel. Podés cambiarlos después en Configuración del hotel.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {collectionMethods.map(({ key, label }) => (
            <label key={key} className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form[key]}
                onChange={(event) => setForm({ ...form, [key]: event.target.checked })}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <details className="mt-4 rounded-lg border border-slate-200 px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">Conectar cobros online (opcional)</summary>
        <p className="mt-2 text-sm text-slate-600">Las conexiones online pueden configurarse ahora o más adelante.</p>
        <div className="mt-3">
          <ProviderSetupGrid
            title="Pasarelas de pago"
            providers={[
              { key: "mercado_pago", label: "Mercado Pago" },
              { key: "paypal", label: "PayPal" },
              { key: "stripe", label: "Tarjeta de crédito / Stripe (solo Pro / Ultra)" }
            ]}
            values={{
              mercado_pago: form.mercado_pago,
              paypal: form.paypal,
              stripe: form.stripe
            }}
            onChange={(providers) =>
              setForm({
                ...form,
                mercado_pago: providers.mercado_pago ?? form.mercado_pago,
                paypal: providers.paypal ?? form.paypal,
                stripe: providers.stripe ?? form.stripe
              })
            }
          />
        </div>
      </details>
      <StepActions onSave={onSave} loading={loading} />
    </StepCard>
  );
}

function OtaStep({
  form,
  setForm,
  onSave,
  loading,
  status
}: {
  form: OTAChannelsPayload;
  setForm: (payload: OTAChannelsPayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  return (
    <StepCard title="Canales OTA" status={status}>
      <ProviderSetupGrid
        title="Conexiones"
        providers={[
          { key: "booking", label: "Booking" },
          { key: "expedia", label: "Expedia" },
          { key: "despegar", label: "Despegar" }
        ]}
        values={form}
        onChange={setForm}
      />
      <StepActions onSave={onSave} loading={loading} />
    </StepCard>
  );
}

function SubscriptionStep({
  form,
  setForm,
  onSave,
  loading,
  status,
  plans,
  currentSubscription,
  stripeEnabled
}: {
  form: SubscriptionChoicePayload;
  setForm: (payload: SubscriptionChoicePayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
  plans: Array<{ code: string; name: string; room_limit: number; staff_limit?: number; price_month?: number | null }>;
  currentSubscription?: OnboardingSubscription | null;
  stripeEnabled: boolean;
}) {
  const subscriptionStatusLabels: Record<string, string> = {
    active: "Activa",
    trialing: "Prueba gratis",
    demo: "Demostración",
    comped: "Acceso de cortesía",
    past_due: "Pago pendiente",
    suspended: "Suspendida",
    paused: "Pausada",
    cancelled: "Cancelada",
    canceled: "Cancelada"
  };
  const planLabels: Record<string, string> = { starter: "Starter", pro: "Pro", ultra: "Ultra" };
  const currentStatusLabel = currentSubscription?.status
    ? subscriptionStatusLabels[String(currentSubscription.status).toLowerCase()] ?? "Estado no disponible"
    : "Estado no disponible";
  const currentPlanLabel = currentSubscription?.plan
    ? planLabels[String(currentSubscription.plan).toLowerCase()] ?? "Plan actual"
    : "Plan actual";
  const selectedStarterWithStripe = stripeEnabled && form.plan_code === "starter";
  const currentPlanCode = String(currentSubscription?.plan ?? "");
  const trialAvailable = currentSubscription?.trial_available === true;
  const selectionUnavailable = !form.start_trial && form.plan_code !== currentPlanCode;

  return (
    <StepCard title="Elección de suscripción" status={status}>
      {currentSubscription && (
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          Estado de la suscripción: <strong>{currentStatusLabel}</strong> · Plan actual:{" "}
          <strong>{currentPlanLabel}</strong>
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        {plans.map((plan) => (
          <label
            key={plan.code}
            className={`rounded-lg border p-4 ${
              form.plan_code === plan.code ? "border-brand-500 bg-brand-50" : "border-slate-200"
            } ${plan.code === "pro" && trialAvailable ? "cursor-pointer" : plan.code === currentPlanCode ? "cursor-pointer" : "cursor-not-allowed opacity-70"}`}
          >
            <input
              type="radio"
              name="subscription-plan"
              aria-label={`Plan ${plan.name}, hasta ${plan.room_limit} habitaciones`}
              className="sr-only"
              disabled={!(plan.code === "pro" && trialAvailable) && plan.code !== currentPlanCode}
              checked={form.plan_code === plan.code}
              onChange={() =>
                setForm(
                  plan.code === "pro" && trialAvailable
                    ? { plan_code: "pro", start_trial: true }
                    : { plan_code: plan.code, start_trial: false }
                )
              }
            />
            <p className="text-sm font-semibold text-slate-900">{plan.name}</p>
            <p className="text-xs text-slate-600">
              {plan.room_limit} habitaciones · {plan.staff_limit ?? "-"} staff
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {plan.price_month != null ? `$${plan.price_month} / mes` : "Precio a definir"}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              {plan.code === "pro" && trialAvailable
                ? "Prueba única de 14 días"
                : plan.code === currentPlanCode
                  ? "Plan vigente; este paso no lo modifica"
                  : "Checkout todavía no disponible"}
            </p>
          </label>
        ))}
      </div>
      <p className="mt-4 rounded-lg bg-sky-50 px-4 py-3 text-sm text-sky-900">
        El plan Pro ofrece una prueba gratuita única de 14 días. Los planes pagos no se activan aquí: elegir un plan no
        genera un cobro ni cambia la suscripción sin checkout confirmado.
      </p>
      {!trialAvailable && currentPlanCode !== "pro" && (
        <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          La prueba ya fue utilizada y el checkout de pago aún no está disponible. Podés conservar el plan vigente;
          no se activará otro plan desde este paso.
        </p>
      )}
      {selectedStarterWithStripe && (
        <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Stripe requiere plan Pro o Ultra. Cambiá el plan o desactivá Stripe en el paso anterior.
        </p>
      )}
      <StepActions
        onSave={onSave}
        loading={loading}
        disabled={selectedStarterWithStripe || selectionUnavailable || (form.start_trial && !trialAvailable)}
      />
    </StepCard>
  );
}

function StaffStep({
  staff,
  setStaff,
  canAssignCoOwner,
  onSave,
  loading,
  status
}: {
  staff: StaffDraft[];
  setStaff: (data: StaffDraft[]) => void;
  canAssignCoOwner: boolean;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const update = (idx: number, field: keyof StaffPayload, value: string) => {
    setStaff(staff.map((member, index) => (index === idx ? { ...member, [field]: value } : member)));
  };

  const addMember = () => setStaff([...staff, createStaffDraft()]);

  return (
    <StepCard title="Staff inicial" status={status}>
      <div className="space-y-3">
        {staff.map((member, idx) => (
          <div key={member.clientKey} className="grid gap-3 md:grid-cols-4">
            <Field label="Nombre">
              <input
                className={inputClassName}
                placeholder="Ej: Juan Pérez"
                value={member.name}
                onChange={(event) => update(idx, "name", event.target.value)}
                required
              />
            </Field>
            <Field label="Rol">
              <select
                className={inputClassName}
                value={member.role || ""}
                onChange={(event) => update(idx, "role", event.target.value)}
                required
                aria-label="Rol"
              >
                <option value="manager">Gerencia</option>
                <option value="receptionist">Recepción</option>
                <option value="housekeeping">Limpieza</option>
                {canAssignCoOwner && <option value="co_owner">Copropietaria</option>}
              </select>
            </Field>
            <Field label="Email">
              <input
                className={inputClassName}
                placeholder="Ej: juan@hotel.test"
                value={member.email || ""}
                onChange={(event) => update(idx, "email", event.target.value)}
              />
            </Field>
            <div className="flex items-end">
              <button
                type="button"
                onClick={() => setStaff(staff.filter((_, index) => index !== idx))}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                aria-label={`Quitar ${member.name || `persona ${idx + 1}`}`}
              >
                Quitar
              </button>
            </div>
          </div>
        ))}
        <p className="text-xs text-slate-600">Se enviará una invitación por correo a cada persona que tenga email.</p>
        {!staff.length && <p className="text-sm text-amber-800" role="status">Agregá al menos una persona para completar este paso.</p>}
        <StepFooterButton label="+ Agregar staff" onClick={addMember} />
        <StepActions onSave={onSave} loading={loading} disabled={!staff.length} />
      </div>
    </StepCard>
  );
}

function FinishStep({
  status,
  isFetching,
  loading,
  currentSubscription,
  onFinish
}: {
  status?: StepStatus;
  isFetching: boolean;
  loading: boolean;
  currentSubscription?: OnboardingSubscription | null;
  onFinish: () => Promise<void>;
}) {
  return (
    <StepCard title="Checklist final" status={status}>
      <div className="space-y-4 text-sm text-slate-700">
        <p>Revisamos los nueve pasos del wizard y marcamos completado en `/api/onboarding/finish`.</p>
        <ul className="list-disc pl-5">
          <li>Owner y datos del hotel cargados</li>
          <li>Categorías y habitaciones creadas</li>
          <li>Política comercial definida</li>
          <li>Pagos, OTAs y suscripción configurados</li>
          <li>Staff inicial guardado</li>
        </ul>
        {currentSubscription && (
          <p className="rounded-lg bg-slate-50 px-4 py-3">
            Suscripción vigente: <strong>{String(currentSubscription.status ?? "-")}</strong> · Plan{" "}
            <strong>{String(currentSubscription.plan ?? "-")}</strong>
          </p>
        )}
        {status?.gates && !status.gates.can_finish && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
            <p className="font-semibold">Bloqueos pendientes</p>
            <ul className="mt-2 list-disc pl-5">
              {status.gates.missing.map((blocker) => (
                <li key={blocker}>{humanizeGate(blocker)}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
          onClick={onFinish}
          type="button"
          disabled={loading || isFetching || status?.gates?.can_finish === false}
        >
          {loading ? "Finalizando..." : "Marcar onboarding como completo"}
        </button>
      </div>
    </StepCard>
  );
}

function ProviderSetupGrid<T extends Record<string, OnboardingProviderSetup>>({
  title,
  providers,
  values,
  onChange
}: {
  title: string;
  providers: Array<{ key: keyof T; label: string }>;
  values: T;
  onChange: (next: T) => void;
}) {
  const updateEnabled = (providerKey: keyof T, enabled: boolean) => {
    onChange({
      ...values,
      [providerKey]: {
        ...values[providerKey],
        enabled
      }
    });
  };

  const updateCredential = (providerKey: keyof T, field: string, value: string) => {
    const currentProvider = values[providerKey];
    onChange({
      ...values,
      [providerKey]: {
        ...currentProvider,
        credentials: {
          ...(currentProvider.credentials ?? {}),
          [field]: value
        }
      }
    });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {providers.map((provider) => {
        const value = values[provider.key];
        return (
          <div key={String(provider.key)} className="rounded-lg border border-slate-200 p-4">
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <input
                type="checkbox"
                checked={Boolean(value.enabled)}
                onChange={(event) => updateEnabled(provider.key, event.target.checked)}
              />
              {provider.label}
            </label>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Field label="Identificador / usuario">
                <input
                  className={inputClassName}
                  value={value.credentials?.account_id || ""}
                  onChange={(event) => updateCredential(provider.key, "account_id", event.target.value)}
                  placeholder="Opcional"
                />
              </Field>
              <Field label="Secret / token">
                <input
                  className={inputClassName}
                  value={value.credentials?.secret || ""}
                  onChange={(event) => updateCredential(provider.key, "secret", event.target.value)}
                  placeholder="Opcional"
                />
              </Field>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StepActions({
  onSave,
  loading,
  disabled,
  helpText
}: {
  onSave: () => Promise<void>;
  loading: boolean;
  disabled?: boolean;
  helpText?: string;
}) {
  return (
    <div className="mt-4 flex items-center justify-between">
      <span className="text-xs text-slate-500">{helpText ?? "Guardamos este paso y avanzamos al siguiente."}</span>
      <button
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
        onClick={onSave}
        type="button"
        disabled={loading || disabled}
      >
        {loading ? "Guardando..." : "Guardar y seguir"}
      </button>
    </div>
  );
}

function StepFooterButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button className="text-sm text-brand-700 hover:underline" type="button" onClick={onClick}>
      {label}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
      {label}
      {children}
    </label>
  );
}

function StepCard({
  title,
  children,
  status
}: {
  title: string;
  children: React.ReactNode;
  status?: StepStatus;
}) {
  const completedNonFinishSteps = status
    ? Object.entries(status.steps || {}).filter(([key, value]) => key !== "finish" && value).length
    : 0;

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-700">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {status && (
            <p className="text-xs text-slate-500">
              Progreso: {status.completed ? "Completado" : status.missing_steps.length ? "Incompleto" : "En progreso"}
            </p>
          )}
        </div>
        {status && (
          <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
            Pasos OK: {completedNonFinishSteps}/9
          </div>
        )}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function humanizeGate(blocker: string): string {
  const labels: Record<string, string> = {
    owner_role: "La finalización requiere un owner.",
    hotel_identity: "Falta completar la identidad del hotel.",
    categories: "Debe existir al menos una categoría.",
    rooms: "Debe existir al menos una habitación.",
    staff: "Debe existir al menos un miembro de staff.",
    subscription_status: "La suscripción debe estar operativa.",
    policy: "Falta definir la política comercial.",
    payments: "Falta configurar métodos de pago.",
    ota: "Falta configurar los canales OTA.",
    subscription_choice: "Falta guardar la elección de suscripción."
  };
  return labels[blocker] ?? blocker;
}
