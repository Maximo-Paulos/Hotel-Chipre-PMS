import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { Seo } from "../../components/Seo";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/reset-password", { replace: true });
  }, [navigate]);
  return <Seo title="Recuperar acceso | Hotel Chipre PMS" description="Recupera tu acceso al sistema." noindex />;
}
