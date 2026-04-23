import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Seo } from "../../components/Seo";
import { register, requestVerification } from "../../api/auth";
import { setOwner } from "../../api/onboarding";
import { normalizeRole, useSession } from "../../state/session";

export function RegisterOwnerPage() {
  const navigate = useNavigate();
  const { login } = useSession();
  const [form, setForm] = useState({ name: "", lastName: "", email: "", password: "", phone: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const handleChange = (field: string, value: string) => setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);

    try {
      const res = await register(form.email, form.password, "owner");
      if (!res.hotel_id) {
        throw new ApiError(500, "La respuesta de registro no devolvió un hotel válido.");
      }
      const sessionData = {
        userId: res.user.email,
        email: res.user.email,
        hotelId: res.hotel_id,
        hotelIds: res.hotel_ids?.length ? res.hotel_ids : [res.hotel_id],
        role: normalizeRole(res.user.role) ?? "owner",
        baseRole: normalizeRole(res.user.role) ?? "owner",
        accessToken: res.access_token,
        isVerified: res.user.is_verified
      };
      login(sessionData);

      await setOwner(
        {
          name: `${form.name} ${form.lastName}`.trim(),
          email: form.email,
          phone: form.phone,
          role: "Owner"
        },
        sessionData
      );

      const codeResp = await requestVerification(form.email);
      if (codeResp.code) {
        setInfo(`Codigo generado: ${codeResp.code} (solo modo demo)`);
      }

      navigate("/verify-email", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("No se pudo crear la cuenta");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Seo title="Registrarte | Hotel Chipre PMS" description="Crea tu cuenta de dueño y empieza la prueba de 14 días." noindex />
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <img
              src="/brand/logo-full.png"
              alt="Hotel Chipre PMS"
              className="h-20 w-auto max-w-full object-contain"
            />
            <h1 className="text-2xl font-semibold text-slate-900">Crear cuenta de dueno</h1>
            <p className="text-sm text-slate-600">
              Guardamos el owner en /api/onboarding/owner y luego verificamos tu email.
            </p>
          </div>
          <Link to="/login" className="text-sm text-brand-700 hover:underline">
            Ya tengo cuenta
          </Link>
        </div>
        <form className="grid grid-cols-1 gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <label className="text-sm font-medium text-slate-700">
            Nombre
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Ej: Lucas"
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Apellido
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Ej: González"
              value={form.lastName}
              onChange={(e) => handleChange("lastName", e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Email corporativo
            <input
              type="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="dueño@hotel.com"
              value={form.email}
              onChange={(e) => handleChange("email", e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Teléfono
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Ej: +54 9 11 5555 1234"
              value={form.phone}
              onChange={(e) => handleChange("phone", e.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Contraseña
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Mínimo 6 caracteres"
              value={form.password}
              onChange={(e) => handleChange("password", e.target.value)}
              required
            />
          </label>
          {error && <p className="col-span-2 rounded-md bg-rose-50 p-3 text-rose-700">{error}</p>}
          {info && <p className="col-span-2 rounded-md bg-amber-50 p-3 text-amber-800">{info}</p>}
          <div className="col-span-2">
            <button
              className="mt-2 w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-70"
              disabled={loading}
              type="submit"
            >
              {loading ? "Creando..." : "Crear cuenta y verificar email"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
