import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  finishOnboarding,
  getOnboardingStatus,
  setCategories,
  setOwner as persistOwner,
  setRooms,
  setStaff,
  type OnboardingStatus,
  type CategoryPayload,
  type OwnerPayload,
  type RoomPayload,
  type StaffPayload
} from "../../api/onboarding";
import { inviteUser } from "../../api/users";
import { onboardingStatusKey, useOnboardingStatus } from "../../hooks/useOnboardingStatus";
import { useSession } from "../../state/session";

const steps = [
  { path: "", label: "Hotel" },
  { path: "categories", label: "Categorías" },
  { path: "rooms", label: "Habitaciones" },
  { path: "staff", label: "Staff" },
  { path: "finish", label: "Finalizar" }
];

export function OnboardingWizard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSession();

  const { data: status, isFetching, refetch } = useOnboardingStatus();

  const [ownerForm, setOwnerForm] = useState<OwnerPayload>({
    name: "",
    email: session.email || "",
    phone: "",
    role: "Owner"
  });
  const [categories, setCategoriesState] = useState<CategoryPayload[]>([]);
  const [rooms, setRoomsState] = useState<RoomPayload[]>([]);
  const [staff, setStaffState] = useState<StaffPayload[]>([]);

  // Pre-cargar datos previos si el backend los devuelve
  useEffect(() => {
    const anyStatus = status as any;
    if (anyStatus?.categories && !categories.length) setCategoriesState(anyStatus.categories as CategoryPayload[]);
    if (anyStatus?.rooms && !rooms.length) setRoomsState(anyStatus.rooms as RoomPayload[]);
    if (anyStatus?.staff && !staff.length) setStaffState(anyStatus.staff as StaffPayload[]);
  }, [status, categories.length, rooms.length, staff.length]);

  useEffect(() => {
    if (
      status?.owner &&
      !ownerForm.email &&
      typeof status.owner === "object" &&
      status.owner !== null &&
      "email" in status.owner
    ) {
      const ownerEmail = status.owner.email as string | undefined;
      setOwnerForm((prev) => ({ ...prev, email: ownerEmail ?? prev.email }));
    }
  }, [ownerForm.email, status?.owner]);

  const refreshCache = (data: OnboardingStatus) =>
    queryClient.setQueryData(onboardingStatusKey(session.hotelId, session.userId), data);

  const ownerMutation = useMutation({
    mutationFn: (payload: OwnerPayload) => persistOwner(payload, session),
    onSuccess: (data) => refreshCache(data)
  });

  const categoriesMutation = useMutation({
    mutationFn: (payload: CategoryPayload[]) => setCategories(payload, session),
    onSuccess: (data) => refreshCache(data)
  });

  const roomsMutation = useMutation({
    mutationFn: (payload: RoomPayload[]) => setRooms(payload, session),
    onSuccess: (data) => refreshCache(data)
  });

  const staffMutation = useMutation({
    mutationFn: (payload: StaffPayload[]) => setStaff(payload, session),
    onSuccess: (data) => refreshCache(data)
  });

  const finishMutation = useMutation({
    mutationFn: () => finishOnboarding(session),
    onSuccess: (data) => {
      refreshCache(data);
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
        {steps.map((s, idx) => (
          <Link
            key={s.path}
            to={s.path}
            className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700"
          >
            {idx + 1}. {s.label}
          </Link>
        ))}
      </div>
      <div className="mt-6">
        <Routes>
          <Route
            index
            element={
              <OwnerStep
                form={ownerForm}
                setForm={setOwnerForm}
                onSave={async () => {
                  const data = await ownerMutation.mutateAsync(ownerForm);
                  refreshCache(data);
                  navigate("/onboarding/categories");
                }}
                loading={ownerMutation.isPending}
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
                  const data = await categoriesMutation.mutateAsync(categories);
                  refreshCache(data);
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
                  const data = await roomsMutation.mutateAsync(rooms);
                  refreshCache(data);
                  navigate("/onboarding/staff");
                }}
                loading={roomsMutation.isPending}
                status={status}
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
                  const data = await staffMutation.mutateAsync(staff);
                  refreshCache(data);
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
                onFinish={async () => {
                  await refreshStatus(refetch);
                  await finishMutation.mutateAsync();
                }}
                loading={finishMutation.isPending}
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

type StepProps = {
  status?: Awaited<ReturnType<typeof getOnboardingStatus>>;
};

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
  status?: StepProps["status"];
}) {
  const handleChange = (field: keyof OwnerPayload, value: string) => setForm({ ...form, [field]: value });

  return (
    <StepCard title="Datos del hotel" status={status}>
      <form className="space-y-3" onSubmit={(e) => e.preventDefault()}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Nombre completo
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              placeholder="Ej: Hotel Chipre Sucursal Centro"
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={form.email}
              onChange={(e) => handleChange("email", e.target.value)}
              placeholder="Ej: admin@hotel.test"
              required
            />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Teléfono
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={form.phone || ""}
              placeholder="Ej: +54 9 11 5555 1234"
              onChange={(e) => handleChange("phone", e.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Rol
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={form.role || ""}
              placeholder="Ej: Owner / Manager"
              onChange={(e) => handleChange("role", e.target.value)}
            />
          </label>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">Guarda owner en /api/onboarding/owner</span>
          <button
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            onClick={onSave}
            type="button"
            disabled={loading}
          >
            {loading ? "Guardando..." : "Guardar y seguir"}
          </button>
        </div>
      </form>
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
  status?: StepProps["status"];
}) {
  const update = (idx: number, field: keyof CategoryPayload, value: string) => {
    const parsedValue =
      field === "base_price_per_night" || field === "max_occupancy" ? Number(value || 0) : value;
    setCategories(
      categories.map((cat, i) => (i === idx ? { ...cat, [field]: parsedValue } as CategoryPayload : cat))
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
        {categories.map((cat, idx) => (
          <div key={idx} className="rounded-lg border border-slate-200 p-4">
            <div className="grid gap-3 md:grid-cols-3">
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Nombre de categoría
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: Standard Doble"
                  value={cat.name}
                  onChange={(e) => update(idx, "name", e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Código interno
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: STD"
                  value={cat.code}
                  onChange={(e) => update(idx, "code", e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Amenities
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: wifi,ac"
                  value={cat.amenities || ""}
                  onChange={(e) => update(idx, "amenities", e.target.value)}
                />
              </label>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Precio base por noche
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: 120"
                  type="number"
                  value={cat.base_price_per_night}
                  onChange={(e) => update(idx, "base_price_per_night", e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Ocupación máxima
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: 2"
                  type="number"
                  value={cat.max_occupancy}
                  onChange={(e) => update(idx, "max_occupancy", e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
                Descripción breve
                <input
                  className="rounded border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Ej: Vista al jardín"
                  value={cat.description || ""}
                  onChange={(e) => update(idx, "description", e.target.value)}
                />
              </label>
            </div>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <button className="text-sm text-brand-700 hover:underline" type="button" onClick={addCategory}>
            + Agregar Categoría
          </button>
          <button
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            onClick={onSave}
            type="button"
            disabled={loading}
          >
            {loading ? "Guardando..." : "Guardar y seguir"}
          </button>
        </div>
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
  status?: StepProps["status"];
}) {
  const update = (idx: number, field: keyof RoomPayload, value: string) => {
    const parsed = field === "floor" ? Number(value || 0) : value;
    setRooms(rooms.map((room, i) => (i === idx ? { ...room, [field]: parsed } as RoomPayload : room)));
  };

  const addRoom = () => {
    const defaultCat = categories[0]?.code || "STD";
    setRooms([
      ...rooms,
      { room_number: `${rooms.length + 101}`, floor: 1, category_code: rooms[rooms.length - 1]?.category_code || defaultCat }
    ]);
  };

  return (
    <StepCard title="Habitaciones" status={status}>
      <div className="space-y-3">
        {rooms.map((room, idx) => (
          <div key={idx} className="grid gap-3 md:grid-cols-4">
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Número de habitación
              <input
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                value={room.room_number}
                onChange={(e) => update(idx, "room_number", e.target.value)}
                placeholder="Ej: 101"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Piso
              <input
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                type="number"
                value={room.floor}
                onChange={(e) => update(idx, "floor", e.target.value)}
                placeholder="Ej: 1"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Código de categoría
              <select
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                value={room.category_code}
                onChange={(e) => update(idx, "category_code", e.target.value)}
              >
                <option value="">Seleccioná una categoría</option>
                {categories.map((cat) => (
                  <option key={cat.code} value={cat.code}>
                    {cat.name} ({cat.code})
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <button className="text-sm text-brand-700 hover:underline" type="button" onClick={addRoom}>
            + Agregar habitación
          </button>
          <button
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
            onClick={onSave}
            type="button"
            disabled={loading}
          >
            {loading ? "Guardando..." : "Guardar y seguir"}
          </button>
        </div>
      </div>
    </StepCard>
  );
}

function StaffStep({
  staff,
  setStaff,
  onSave,
  onSkip,
  loading,
  status
}: {
  staff: StaffPayload[];
  setStaff: (data: StaffPayload[]) => void;
  onSave: () => Promise<void>;
  onSkip?: () => void;
  loading: boolean;
  status?: StepProps["status"];
}) {
  const update = (idx: number, field: keyof StaffPayload, value: string) => {
    setStaff(staff.map((member, i) => (i === idx ? { ...member, [field]: value } as StaffPayload : member)));
  };

  const addMember = () => setStaff([...staff, { name: "", role: "", email: "" }]);

  return (
    <StepCard title="Staff inicial (opcional)" status={status}>
      <div className="space-y-3">
        {staff.map((member, idx) => (
          <div key={idx} className="grid gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Nombre
              <input
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                placeholder="Ej: Juan Pérez"
                value={member.name}
                onChange={(e) => update(idx, "name", e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Rol
              <input
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                placeholder="Ej: Front Desk"
                value={member.role || ""}
                onChange={(e) => update(idx, "role", e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
              Email
              <input
                className="rounded border border-slate-200 px-3 py-2 text-sm"
                placeholder="Ej: juan@hotel.test"
                value={member.email || ""}
                onChange={(e) => update(idx, "email", e.target.value)}
              />
            </label>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <button className="text-sm text-brand-700 hover:underline" type="button" onClick={addMember}>
            + Agregar staff
          </button>
          <div className="flex items-center gap-3">
            {onSkip && (
              <button
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-brand-400"
                onClick={onSkip}
                type="button"
                disabled={loading}
              >
                Saltar este paso
              </button>
            )}
            <button
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
              onClick={onSave}
              type="button"
              disabled={loading}
            >
              {loading ? "Guardando..." : "Guardar y seguir"}
            </button>
          </div>
        </div>
      </div>
    </StepCard>
  );
}

function FinishStep({
  status,
  isFetching,
  loading,
  onFinish
}: {
  status?: StepProps["status"];
  isFetching: boolean;
  loading: boolean;
  onFinish: () => Promise<void>;
}) {
  return (
    <StepCard title="Checklist final" status={status}>
      <div className="space-y-4 text-sm text-slate-700">
        <p>Revisamos los pasos y marcamos completado en /api/onboarding/finish.</p>
        <ul className="list-disc pl-5">
          <li>Owner cargado</li>
          <li>Categorías y habitaciones creadas</li>
          <li>Staff inicial guardado</li>
        </ul>
        <button
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-70"
          onClick={onFinish}
          type="button"
          disabled={loading || isFetching}
        >
          {loading ? "Finalizando..." : "Marcar onboarding como completo"}
        </button>
      </div>
    </StepCard>
  );
}

function StepCard({
  title,
  children,
  status
}: {
  title: string;
  children: React.ReactNode;
  status?: StepProps["status"];
}) {
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
            Pasos OK: {Object.values(status.steps || {}).filter(Boolean).length}/5
          </div>
        )}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}



