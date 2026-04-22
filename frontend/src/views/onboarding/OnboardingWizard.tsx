import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

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
  type OnboardingStatus,
  type OTAChannelsPayload,
  type OwnerPayload,
  type PaymentMethodsPayload,
  type RoomPayload,
  type StaffPayload,
  type SubscriptionChoicePayload
} from "../../api/onboarding";
import { onboardingStatusKey, useOnboardingStatus } from "../../hooks/useOnboardingStatus";
import { useSubscriptionPlans } from "../../hooks/useSubscription";
import { useSession } from "../../state/session";

const steps = [
  { path: "", label: "Owner" },
  { path: "identity", label: "Identidad" },
  { path: "categories", label: "Categorías" },
  { path: "rooms", label: "Habitaciones" },
  { path: "policy", label: "Política" },
  { path: "payments", label: "Pagos" },
  { path: "ota", label: "OTAs" },
  { path: "subscription", label: "Suscripción" },
  { path: "staff", label: "Staff" }
];

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
  plan_code: "starter",
  start_trial: false
};

const inputClassName =
  "rounded-lg border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500";

type StepStatus = Awaited<ReturnType<typeof getOnboardingStatus>>;

export function OnboardingWizard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSession();
  const plansQuery = useSubscriptionPlans();
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
  const [staff, setStaffState] = useState<StaffPayload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

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

    if (status.payment_methods && !hasEnabledProvider(paymentsForm)) {
      setPaymentsForm({
        mercado_pago: hydrateProvider(status.payment_methods.mercado_pago),
        paypal: hydrateProvider(status.payment_methods.paypal),
        stripe: hydrateProvider(status.payment_methods.stripe)
      });
    }

    if (status.ota_channels && !hasEnabledProvider(otaForm)) {
      setOtaForm({
        booking: hydrateProvider(status.ota_channels.booking),
        expedia: hydrateProvider(status.ota_channels.expedia),
        despegar: hydrateProvider(status.ota_channels.despegar)
      });
    }

    if (status.subscription_choice && subscriptionForm.plan_code === defaultSubscriptionForm.plan_code) {
      setSubscriptionForm({
        plan_code: String(status.subscription_choice.plan_code ?? defaultSubscriptionForm.plan_code),
        start_trial: Boolean(status.subscription_choice.start_trial)
      });
    } else if (status.current_subscription && subscriptionForm.plan_code === defaultSubscriptionForm.plan_code) {
      setSubscriptionForm({
        plan_code: String(status.current_subscription.plan ?? defaultSubscriptionForm.plan_code),
        start_trial: false
      });
    }

    if (status.staff?.length && !staff.length) {
      setStaffState(status.staff);
    }
  }, [
    categories.length,
    identityForm.name,
    otaForm,
    ownerForm.name,
    paymentsForm,
    policyForm.deposit_percentage,
    rooms.length,
    session.email,
    staff.length,
    status,
    subscriptionForm.plan_code
  ]);

  const refreshCache = (data: OnboardingStatus) =>
    queryClient.setQueryData(onboardingStatusKey(session.hotelId, session.userId), data);

  const runWithFeedback = async (action: () => Promise<OnboardingStatus>, successMessage: string) => {
    setError(null);
    setToast(null);
    try {
      const data = await action();
      refreshCache(data);
      setToast(successMessage);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar este paso.");
      throw err;
    }
  };

  const ownerMutation = useMutation({
    mutationFn: () => runWithFeedback(() => persistOwner(ownerForm, session), "Owner guardado.")
  });

  const identityMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setHotelIdentity(identityForm, session), "Identidad del hotel guardada.")
  });

  const categoriesMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setCategories(categories, session), "Categorías guardadas.")
  });

  const roomsMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setRooms(rooms, session), "Habitaciones guardadas.")
  });

  const policyMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setDepositPolicy(policyForm, session), "Política guardada.")
  });

  const paymentsMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setPaymentMethods(paymentsForm, session), "Pagos guardados.")
  });

  const otaMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setOtaChannels(otaForm, session), "Canales OTA guardados.")
  });

  const subscriptionMutation = useMutation({
    mutationFn: () =>
      runWithFeedback(() => setSubscriptionChoice(subscriptionForm, session), "Suscripción configurada.")
  });

  const staffMutation = useMutation({
    mutationFn: () => runWithFeedback(() => setStaff(staff, session), "Staff guardado.")
  });

  const finishMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      setToast(null);
      await refreshStatus(refetch);
      return runWithFeedback(() => finishOnboarding(session), "Onboarding finalizado.");
    },
    onSuccess: () => {
      navigate("/dashboard", { replace: true });
    }
  });

  const bannerText = useMemo(() => {
    if (!status || status.completed) return null;
    return `Falta: ${status.missing_steps.join(", ")}`;
  }, [status]);

  useEffect(() => {
    if (status?.completed) {
      navigate("/dashboard", { replace: true });
    }
  }, [status?.completed, navigate]);

  const currentSubscription = status?.current_subscription;
  const availablePlans = plansQuery.data ?? [];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Onboarding obligatorio</p>
          <h1 className="text-xl font-semibold text-slate-900">Configurá tu hotel</h1>
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
            to={step.path}
            className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700"
          >
            {idx + 1}. {step.label}
          </Link>
        ))}
        <Link
          to="finish"
          className="rounded-full border border-emerald-200 px-3 py-1 text-xs font-medium text-emerald-700 hover:border-emerald-400"
        >
          Finalizar
        </Link>
      </div>

      {error && <p className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      {toast && <p className="mt-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{toast}</p>}

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
                  navigate("/onboarding/rooms");
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
                  navigate("/onboarding/subscription");
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
                  navigate("/onboarding/staff");
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

const hasEnabledProvider = (payload: Record<string, OnboardingProviderSetup>) =>
  Object.values(payload).some((provider) => provider.enabled);

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
  onSave,
  loading,
  status
}: {
  form: HotelIdentityPayload;
  setForm: (payload: HotelIdentityPayload) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
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
          />
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
  status
}: {
  categories: CategoryPayload[];
  rooms: RoomPayload[];
  setRooms: (data: RoomPayload[]) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const update = (idx: number, field: keyof RoomPayload, value: string) => {
    const parsed = field === "floor" ? Number(value || 0) : value;
    setRooms(rooms.map((room, index) => (index === idx ? { ...room, [field]: parsed } : room)));
  };

  const addRoom = () => {
    const defaultCategory = categories[0]?.code || "STD";
    setRooms([
      ...rooms,
      { room_number: `${rooms.length + 101}`, floor: 1, category_code: rooms[rooms.length - 1]?.category_code || defaultCategory }
    ]);
  };

  return (
    <StepCard title="Habitaciones" status={status}>
      <div className="space-y-3">
        {rooms.map((room, idx) => (
          <div key={`${room.room_number}-${idx}`} className="grid gap-3 md:grid-cols-3">
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
  return (
    <StepCard title="Métodos de pago" status={status}>
      <ProviderSetupGrid
        title="Gateways"
        providers={[
          { key: "mercado_pago", label: "Mercado Pago" },
          { key: "paypal", label: "PayPal" },
          { key: "stripe", label: "Stripe (solo Pro / Ultra)" }
        ]}
        values={form}
        onChange={setForm}
      />
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
  currentSubscription?: Record<string, unknown> | null;
  stripeEnabled: boolean;
}) {
  const selectedStarterWithStripe = stripeEnabled && form.plan_code === "starter";

  return (
    <StepCard title="Elección de suscripción" status={status}>
      {currentSubscription && (
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          Estado actual: <strong>{String(currentSubscription.status ?? "-")}</strong> · Plan actual:{" "}
          <strong>{String(currentSubscription.plan ?? "-")}</strong>
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        {plans.map((plan) => (
          <label
            key={plan.code}
            className={`cursor-pointer rounded-lg border p-4 ${
              form.plan_code === plan.code ? "border-brand-500 bg-brand-50" : "border-slate-200"
            }`}
          >
            <input
              type="radio"
              name="subscription-plan"
              className="sr-only"
              checked={form.plan_code === plan.code}
              onChange={() => setForm({ ...form, plan_code: plan.code })}
            />
            <p className="text-sm font-semibold text-slate-900">{plan.name}</p>
            <p className="text-xs text-slate-600">
              {plan.room_limit} habitaciones · {plan.staff_limit ?? "-"} staff
            </p>
            {plan.price_month != null && <p className="mt-1 text-xs text-slate-500">${plan.price_month} / mes</p>}
          </label>
        ))}
      </div>
      <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={form.start_trial}
          onChange={(event) => setForm({ ...form, start_trial: event.target.checked })}
        />
        Iniciar prueba gratis del plan seleccionado
      </label>
      {selectedStarterWithStripe && (
        <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Stripe requiere plan Pro o Ultra. Cambiá el plan o desactivá Stripe en el paso anterior.
        </p>
      )}
      <StepActions onSave={onSave} loading={loading} disabled={selectedStarterWithStripe} />
    </StepCard>
  );
}

function StaffStep({
  staff,
  setStaff,
  onSave,
  loading,
  status
}: {
  staff: StaffPayload[];
  setStaff: (data: StaffPayload[]) => void;
  onSave: () => Promise<void>;
  loading: boolean;
  status?: StepStatus;
}) {
  const update = (idx: number, field: keyof StaffPayload, value: string) => {
    setStaff(staff.map((member, index) => (index === idx ? { ...member, [field]: value } : member)));
  };

  const addMember = () => setStaff([...staff, { name: "", role: "", email: "" }]);

  return (
    <StepCard title="Staff inicial" status={status}>
      <div className="space-y-3">
        {staff.map((member, idx) => (
          <div key={`${member.email || member.name}-${idx}`} className="grid gap-3 md:grid-cols-3">
            <Field label="Nombre">
              <input
                className={inputClassName}
                placeholder="Ej: Juan Pérez"
                value={member.name}
                onChange={(event) => update(idx, "name", event.target.value)}
              />
            </Field>
            <Field label="Rol">
              <input
                className={inputClassName}
                placeholder="Ej: Front Desk"
                value={member.role || ""}
                onChange={(event) => update(idx, "role", event.target.value)}
              />
            </Field>
            <Field label="Email">
              <input
                className={inputClassName}
                placeholder="Ej: juan@hotel.test"
                value={member.email || ""}
                onChange={(event) => update(idx, "email", event.target.value)}
              />
            </Field>
          </div>
        ))}
        <StepFooterButton label="+ Agregar staff" onClick={addMember} />
        <StepActions onSave={onSave} loading={loading} />
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
  currentSubscription?: Record<string, unknown> | null;
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
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-70"
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
