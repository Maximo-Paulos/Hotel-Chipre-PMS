export type IntegrationHelp = {
  provider: string;
  title: string;
  steps: string[];
  tips?: string[];
  docUrl?: string;
  copyUrlLabel?: string;
};

export const integrationHelp: IntegrationHelp[] = [
  {
    provider: "booking",
    title: "Booking.com (token-based)",
    steps: [
      "Desde tu cuenta de Booking Connectivity, genera un token JWT de machine account.",
      "En la tarjeta de Booking, pega el token en el campo API key y guarda.",
      "Pulsa Conectar para validar. Si falla, revisa que el token no haya expirado.",
    ],
    tips: [
      "Nunca compartas el token por chat o email.",
      "Si ves phishing que simula Booking, entra solo a https://admin.booking.com o al portal de conectividad oficial."
    ],
    docUrl: "https://developers.booking.com/connectivity/docs/token-based-authentication",
  },
  {
    provider: "expedia",
    title: "Expedia Rapid (firma SHA-512)",
    steps: [
      "En Expedia Partner Central crea API key y API secret.",
      "Ingresa key y secret en la tarjeta Expedia.",
      "Pulsa Conectar; las firmas SHA-512 se calculan automáticamente al usar la API."
    ],
    tips: [
      "Usa credenciales de sandbox si aún no estás en producción.",
      "Si recibes 401, verifica que la key/secret sigan activos."
    ],
    docUrl: "https://developers.expediagroup.com/rapid/setup",
  },
  {
    provider: "mercadopago",
    title: "MercadoPago (OAuth)",
    steps: [
      "Haz clic en Conectar para abrir la autorización de MercadoPago.",
      "Autoriza la app y copia el código que te muestra al finalizar.",
      "Pega el código en el campo 'Finalizar con código' y confirma."
    ],
    tips: [
      "Requiere client_id y client_secret configurados en el backend.",
      "Si ves 401, revisa que tu sesión siga activa."
    ],
    docUrl: "https://www.mercadopago.com.ar/developers/en/guides/online-payments/oauth",
    copyUrlLabel: "Abrir autorización MP"
  },
  {
    provider: "paypal",
    title: "PayPal (OAuth)",
    steps: [
      "Pulsa Conectar para abrir la pantalla de autorización de PayPal (sandbox o live según config).",
      "Inicia sesión en PayPal y acepta.",
      "Copia el código de autorización y pégalo en 'Finalizar con código'."
    ],
    tips: [
      "Asegúrate de que el redirect_uri configurado en PayPal coincide con el backend.",
      "Para pruebas usa sandbox; cámbialo a live sólo con credenciales de producción."
    ],
    docUrl: "https://developer.paypal.com/docs/api/overview/",
    copyUrlLabel: "Abrir autorización PayPal"
  },
  {
    provider: "gmail",
    title: "Gmail (OAuth, envío de correo)",
    steps: [
      "Haz clic en Conectar para abrir la autorización de Google.",
      "Elige la cuenta de Gmail y acepta los scopes de envío/lectura.",
      "Copia el código de autorización y pégalo en 'Finalizar con código'."
    ],
    tips: [
      "Usa scopes mínimos: gmail.send y gmail.readonly.",
      "La cuenta debe tener permitido el uso de aplicaciones propias (pantalla de consentimiento configurada)."
    ],
    docUrl: "https://developers.google.com/gmail/api",
    copyUrlLabel: "Abrir autorización Gmail"
  },
  {
    provider: "whatsapp",
    title: "WhatsApp Cloud (token largo)",
    steps: [
      "En el panel de Meta for Developers obtiene el bearer token y el phone_number_id y waba_id.",
      "Pega el token, phone_number_id y waba_id en la tarjeta y pulsa Conectar.",
      "Prueba enviando un mensaje de prueba desde el Graph API explorer."
    ],
    tips: [
      "El token de desarrollo expira a los 23 días; renueva y vuelve a pegarlo.",
      "No compartas el token; da acceso completo a tu WABA."
    ],
    docUrl: "https://developers.facebook.com/docs/whatsapp/",
  }
];
