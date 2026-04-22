import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/reset-password", { replace: true });
  }, [navigate]);
  return null;
}
