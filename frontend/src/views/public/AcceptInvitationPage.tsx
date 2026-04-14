import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { acceptInvitation, getInvitationInfo } from "../../api/auth";
import { normalizeRole, useSession } from "../../state/session";

export function AcceptInvitationPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const { login } = useSession();

  const [email, setEmail] = useState("");
  const [hotelName, setHotelName] = useState("");
  const [inviter, setInviter] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!token) {
        setError("Token de invitación inválido.");
        return;
      }
      try {
        const data = await getInvitationInfo(token);
        setEmail(data.email);
        setHotelName(data.hotel_name || "");
        setInviter(data.inviter_email || "");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Invitación inválida o expirada");
      }
    };
    load();
  }, [token]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("Token de invitación inválido.");
      return;
    }
    if (!password || password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      const res = await acceptInvitation(token, email, password);
      if (!res.hotel_id) {
        throw new ApiError(500, "La respuesta de invitación no devolvió un hotel válido.");
      }
      login({
        userId: res.user.email,
        email: res.user.email,
        hotelId: res.hotel_id,
        hotelIds: res.hotel_ids?.length ? res.hotel_ids : [res.hotel_id],
        role: normalizeRole(res.user.role),
        baseRole: normalizeRole(res.user.role),
        accessToken: res.access_token,
        isVerified: res.user.is_verified
      });
      setInfo("Cuenta creada. Redirigiendo...");
      setTimeout(() => navigate("/dashboard"), 800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo aceptar la invitación");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Aceptar invitación</h1>
        <p className="mb-4 text-sm text-slate-600">Creá tu contraseña para empezar a usar el sistema.</p>

        <div className="mb-4 space-y-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {hotelName && (
            <p>
              <strong>Hotel:</strong> {hotelName}
            </p>
          )}
          {inviter && (
            <p>
              <strong>Invitado por:</strong> {inviter}
            </p>
          )}
          {email && (
            <p>
              <strong>Email:</strong> <span className="text-slate-900">{email}</span>
            </p>
          )}
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              value={email}
              readOnly
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-800"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Nueva contraseña
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Mínimo 6 caracteres"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Confirmar contraseña
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="Repetí tu contraseña"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </label>
          <button
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            disabled={loading || !token}
            type="submit"
          >
            {loading ? "Guardando..." : "Crear cuenta"}
          </button>
        </form>

        {info && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">{info}</p>}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}

        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
