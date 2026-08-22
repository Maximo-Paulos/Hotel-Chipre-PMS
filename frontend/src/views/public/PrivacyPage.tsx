import type { ReactNode } from "react";

import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { ALLOW_INDEXING } from "../../config/publicUrls";

const ULTIMA_ACTUALIZACION = "22 de agosto de 2026";

export function PrivacyPage() {
  return (
    <MarketingShell>
      <Seo
        title="Política de Privacidad | Hotel Chipre PMS"
        description="Cómo Hotel Chipre PMS recolecta, usa y protege los datos personales de usuarios y huéspedes."
        canonicalPath="/privacy"
        noindex={!ALLOW_INDEXING}
      />
      <article className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Legal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
          Política de Privacidad
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Última actualización: {ULTIMA_ACTUALIZACION}
        </p>

        <Section title="1. Responsable del tratamiento">
          <p>
            Esta Política de Privacidad describe cómo{" "}
            <strong>Paulos Francisco José A. (CUIT 20-20569548-7)</strong>, con domicilio
            legal en <strong>[Domicilio legal pendiente de completar]</strong>{" "}
            (&laquo;nosotros&raquo;), trata los datos personales en el marco de Hotel
            Chipre PMS (&laquo;el Servicio&raquo;), disponible en{" "}
            <a className="text-brand-700 underline" href="https://hotels-pms.com">
              hotels-pms.com
            </a>
            .
          </p>
        </Section>

        <Section title="2. Dos roles distintos frente a los datos">
          <p>
            Distinguimos dos categorías de datos, porque nuestro rol legal es distinto en
            cada una:
          </p>
          <ul className="ml-5 list-disc space-y-1">
            <li>
              <strong>Datos de tu cuenta</strong> (vos, como usuario del Servicio): acá
              somos <strong>responsables del tratamiento</strong>.
            </li>
            <li>
              <strong>Datos de huéspedes</strong> que cargás en el Servicio: acá vos sos
              el responsable y nosotros actuamos como{" "}
              <strong>encargados del tratamiento</strong>, únicamente según tus
              instrucciones y lo descripto en nuestros{" "}
              <a className="text-brand-700 underline" href="/terms">
                Términos y Condiciones
              </a>
              .
            </li>
          </ul>
        </Section>

        <Section title="3. Datos de tu cuenta que recolectamos">
          <ul className="ml-5 list-disc space-y-1">
            <li>Datos de registro: nombre, correo electrónico y contraseña (con hash).</li>
            <li>
              Si iniciás sesión con &laquo;Continuar con Google&raquo; o &laquo;Continuar
              con Apple&raquo;: el identificador único que nos entrega ese proveedor
              (`google_sub` / `apple_sub`) y los datos básicos de perfil que autoricés
              (nombre, correo).
            </li>
            <li>
              Datos de uso y sesión: dirección IP, tipo de dispositivo, registros de
              acceso y actividad dentro del Servicio, con fines de seguridad y auditoría.
            </li>
            <li>
              Datos de facturación necesarios para procesar el pago de tu suscripción.
            </li>
          </ul>
        </Section>

        <Section title="4. Base legal y finalidad">
          <p>
            Tratamos tus datos de cuenta para prestarte el Servicio (ejecución del
            contrato), para cumplir obligaciones legales y fiscales, y para proteger la
            seguridad de la plataforma (interés legítimo). No usamos tus datos de cuenta
            con fines de publicidad de terceros.
          </p>
        </Section>

        <Section title="5. Encargados y proveedores que usamos">
          <p>
            Para operar el Servicio, compartimos datos con proveedores que actúan como
            encargados de tratamiento, bajo instrucciones nuestras y acuerdos de
            confidencialidad:
          </p>
          <ul className="ml-5 list-disc space-y-1">
            <li>Hosting del frontend (entrega de la aplicación web).</li>
            <li>Hosting del backend (procesamiento de la aplicación y la API).</li>
            <li>Base de datos (almacenamiento de la información del Servicio).</li>
            <li>DNS y red de distribución de contenido.</li>
            <li>Envío de correo transaccional (verificación, recuperación de cuenta, notificaciones).</li>
            <li>
              Procesadores de pago (MercadoPago, PayPal o Stripe, según el método que
              elijas) para gestionar el cobro de tu suscripción; no almacenamos los datos
              completos de tu tarjeta.
            </li>
          </ul>
          <p>
            Parte de estos proveedores puede procesar datos en servidores fuera de
            Argentina. En esos casos, exigimos que ofrezcan garantías de protección
            equivalentes a las de la normativa aplicable.
          </p>
        </Section>

        <Section title="6. Plazos de conservación">
          <ul className="ml-5 list-disc space-y-1">
            <li>
              Datos de cuenta: mientras la cuenta esté activa. Al cerrarla, quedan
              disponibles para exportación durante <strong>30 días</strong>, conforme a
              nuestros{" "}
              <a className="text-brand-700 underline" href="/terms">
                Términos y Condiciones
              </a>
              .
            </li>
            <li>
              Registros de auditoría y seguridad: <strong>24 meses</strong>.
            </li>
            <li>
              Datos que debamos conservar por obligación legal (por ejemplo, fiscal): el
              plazo que exija esa norma.
            </li>
          </ul>
        </Section>

        <Section title="7. Tus derechos">
          <p>
            Podés pedirnos acceso, rectificación, actualización o supresión de tus datos
            de cuenta, así como oponerte a un tratamiento puntual, escribiendo a{" "}
            <a className="text-brand-700 underline" href="mailto:privacy@hotels-pms.com">
              privacy@hotels-pms.com
            </a>
            . Vamos a responder en un plazo razonable y conforme a la normativa aplicable.
          </p>
          <p>
            Si sos huésped de un hotel que usa el Servicio, el responsable de tus datos es
            ese hotel: contactalo directamente a vos, o escribinos a{" "}
            <a className="text-brand-700 underline" href="mailto:privacy@hotels-pms.com">
              privacy@hotels-pms.com
            </a>{" "}
            y te derivamos al hotel correspondiente.
          </p>
        </Section>

        <Section title="8. Seguridad de la información">
          <p>
            Aplicamos medidas técnicas y organizativas razonables (cifrado en tránsito,
            contraseñas con hash, controles de acceso por rol) para proteger los datos
            que tratamos. Ningún sistema es 100% infalible; si detectás una
            vulnerabilidad, reportala a{" "}
            <a className="text-brand-700 underline" href="mailto:security@hotels-pms.com">
              security@hotels-pms.com
            </a>
            .
          </p>
        </Section>

        <Section title="9. Cookies y almacenamiento local">
          <p>
            Usamos almacenamiento local del navegador únicamente para mantener tu sesión
            iniciada y tus preferencias del Servicio. No usamos cookies de publicidad ni
            de rastreo de terceros.
          </p>
        </Section>

        <Section title="10. Menores de edad">
          <p>
            El Servicio no está dirigido a menores de 18 años y no recolectamos a
            sabiendas datos de menores como titulares de cuenta.
          </p>
        </Section>

        <Section title="11. Cambios en esta política">
          <p>
            Podemos actualizar esta política. Si el cambio es sustancial, te avisaremos
            con al menos 30 días de anticipación por correo o desde el propio sistema,
            igual que en nuestros{" "}
            <a className="text-brand-700 underline" href="/terms">
              Términos y Condiciones
            </a>
            .
          </p>
        </Section>

        <Section title="12. Contacto">
          <p>
            Privacidad:{" "}
            <a className="text-brand-700 underline" href="mailto:privacy@hotels-pms.com">
              privacy@hotels-pms.com
            </a>
            <br />
            Seguridad:{" "}
            <a className="text-brand-700 underline" href="mailto:security@hotels-pms.com">
              security@hotels-pms.com
            </a>
            <br />
            Soporte:{" "}
            <a className="text-brand-700 underline" href="mailto:support@hotels-pms.com">
              support@hotels-pms.com
            </a>
          </p>
        </Section>
      </article>
    </MarketingShell>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-slate-700">
        {children}
      </div>
    </section>
  );
}
