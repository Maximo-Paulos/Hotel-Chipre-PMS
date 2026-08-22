import type { ReactNode } from "react";

import { Seo } from "../../components/Seo";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { ALLOW_INDEXING } from "../../config/publicUrls";

const ULTIMA_ACTUALIZACION = "22 de agosto de 2026";

export function TermsPage() {
  return (
    <MarketingShell>
      <Seo
        title="Términos y Condiciones | Hotel Chipre PMS"
        description="Términos y condiciones del servicio Hotel Chipre PMS: cuentas, datos de huéspedes, planes, facturación y responsabilidad."
        canonicalPath="/terms"
        noindex={!ALLOW_INDEXING}
      />
      <article className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Legal</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
          Términos y Condiciones del Servicio
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Última actualización: {ULTIMA_ACTUALIZACION}
        </p>

        <Section title="1. Aceptación">
          <p>
            Estos términos regulan el uso de Hotel Chipre PMS (&laquo;el
            Servicio&raquo;), disponible en{" "}
            <a className="text-brand-700 underline" href="https://hotels-pms.com">
              hotels-pms.com
            </a>
            . Al crear una cuenta o utilizar el Servicio, aceptás estos términos. Si los
            aceptás en representación de una empresa, declarás contar con facultades
            suficientes para obligarla.
          </p>
        </Section>

        <Section title="2. Qué es el Servicio">
          <p>
            Hotels PMS es un sistema de gestión hotelera que permite administrar
            reservas, habitaciones, tarifas, huéspedes, caja, stock y reportes. Se presta
            como software como servicio: no se entrega ni se licencia una copia del
            software.
          </p>
        </Section>

        <Section title="3. Cuentas y acceso">
          <ul className="ml-5 list-disc space-y-1">
            <li>
              Debés ser mayor de 18 años y suministrar información veraz al registrarte.
            </li>
            <li>
              Sos responsable de resguardar tus credenciales y de toda actividad
              realizada bajo tu cuenta.
            </li>
            <li>
              Podés acceder con correo y contraseña, con &laquo;Continuar con
              Google&raquo; o con &laquo;Continuar con Apple&raquo;. Si usás el mismo
              correo en distintos métodos, todos quedan vinculados a la misma cuenta.
            </li>
            <li>
              Recomendamos activar el segundo factor de autenticación (MFA) en las cuentas
              con permisos administrativos.
            </li>
            <li>
              Debés notificarnos de inmediato a{" "}
              <a className="text-brand-700 underline" href="mailto:security@hotels-pms.com">
                security@hotels-pms.com
              </a>{" "}
              ante cualquier uso no autorizado de tu cuenta.
            </li>
          </ul>
        </Section>

        <Section title="4. Tus obligaciones sobre los datos de huéspedes">
          <p>
            Respecto de los datos personales de huéspedes que cargues en el Servicio, vos
            actuás como responsable del tratamiento y nosotros como encargado. En
            consecuencia, te obligás a:
          </p>
          <ul className="ml-5 list-disc space-y-1">
            <li>
              contar con base legal suficiente para recolectar y tratar esos datos;
            </li>
            <li>informar a los huéspedes conforme la normativa aplicable;</li>
            <li>
              atender los pedidos de acceso, rectificación y supresión que recibas;
            </li>
            <li>
              cargar únicamente los datos necesarios para la operación hotelera y
              mantenerlos actualizados.
            </li>
          </ul>
          <p>
            Nosotros trataremos esos datos únicamente conforme a tus instrucciones y a lo
            descripto en nuestra{" "}
            <a className="text-brand-700 underline" href="/privacy">
              Política de Privacidad
            </a>
            .
          </p>
        </Section>

        <Section title="5. Uso aceptable">
          <p>No está permitido:</p>
          <ul className="ml-5 list-disc space-y-1">
            <li>
              usar el Servicio para actividades ilícitas o que vulneren derechos de
              terceros;
            </li>
            <li>
              intentar acceder a datos de otros hoteles o cuentas, ni eludir los controles
              de permisos;
            </li>
            <li>
              realizar ingeniería inversa, descompilar o extraer el código del Servicio;
            </li>
            <li>
              automatizar el acceso de forma que degrade el rendimiento, ni realizar
              pruebas de seguridad sin autorización escrita previa;
            </li>
            <li>revender o sublicenciar el Servicio sin acuerdo escrito.</li>
          </ul>
          <p>
            Si detectás una vulnerabilidad, te pedimos que la reportes de forma
            responsable a{" "}
            <a className="text-brand-700 underline" href="mailto:security@hotels-pms.com">
              security@hotels-pms.com
            </a>{" "}
            antes de divulgarla.
          </p>
        </Section>

        <Section title="6. Planes, facturación y cancelación">
          <ul className="ml-5 list-disc space-y-1">
            <li>
              Los precios, límites y funcionalidades de cada plan son los publicados en el
              Servicio al momento de la contratación.
            </li>
            <li>
              La suscripción se renueva automáticamente por períodos iguales, salvo
              cancelación previa a la fecha de renovación.
            </li>
            <li>
              Podés cancelar en cualquier momento. La cancelación surte efecto al final
              del período ya abonado; salvo disposición legal en contrario, no se
              reintegran períodos comenzados.
            </li>
            <li>
              Ante falta de pago podemos suspender el acceso, previa notificación y con un
              plazo razonable para regularizar.
            </li>
            <li>
              Podemos modificar los precios notificándote con al menos 30 días de
              anticipación. Si no aceptás el nuevo precio, podés cancelar antes de que
              entre en vigor.
            </li>
            <li>Los precios se expresan sin impuestos, salvo indicación en contrario.</li>
          </ul>
        </Section>

        <Section title="7. Disponibilidad y soporte">
          <p>
            Trabajamos para mantener el Servicio disponible de forma continua, pero no
            garantizamos un funcionamiento libre de interrupciones. Podemos realizar
            mantenimientos programados, avisando con antelación razonable cuando sea
            posible.
          </p>
          <p>
            El soporte se brinda por correo a{" "}
            <a className="text-brand-700 underline" href="mailto:support@hotels-pms.com">
              support@hotels-pms.com
            </a>
            , en días hábiles.
          </p>
        </Section>

        <Section title="8. Propiedad intelectual">
          <p>
            El Servicio, su software, marcas, diseño y documentación son de nuestra
            titularidad o de nuestros licenciantes. Los datos que cargues siguen siendo
            tuyos: solo los usamos para prestarte el Servicio y para lo previsto en la
            Política de Privacidad.
          </p>
        </Section>

        <Section title="9. Exportación y devolución de datos">
          <p>
            Podés exportar tus datos operativos mientras la cuenta esté activa. Al cerrar
            la cuenta, mantendremos los datos disponibles para exportación durante{" "}
            <strong>30 días</strong>; transcurrido ese plazo procederemos a su eliminación
            o anonimización, salvo lo que debamos conservar por obligación legal.
          </p>
        </Section>

        <Section title="10. Limitación de responsabilidad">
          <p>
            El Servicio se presta &laquo;tal cual&raquo;, sin garantías implícitas de
            adecuación a un fin determinado. En la máxima medida permitida por la ley, no
            respondemos por lucro cesante, pérdida de datos, pérdida de oportunidades
            comerciales ni daños indirectos o consecuentes.
          </p>
          <p>
            Nuestra responsabilidad total acumulada frente a cualquier reclamo derivado
            del Servicio se limita al monto efectivamente abonado por vos en los{" "}
            <strong>12 meses</strong> anteriores al hecho que originó el reclamo.
          </p>
          <p>
            Estas limitaciones no aplican en casos de dolo o culpa grave, ni cuando la ley
            aplicable no admita su exclusión. Si sos consumidor final, conservás los
            derechos que te reconoce la normativa de defensa del consumidor.
          </p>
        </Section>

        <Section title="11. Copias de seguridad">
          <p>
            Realizamos copias de seguridad periódicas como parte de la operación del
            Servicio. Aun así, te recomendamos exportar tu información con regularidad: no
            garantizamos la recuperación de datos eliminados por vos o por usuarios de tu
            organización.
          </p>
        </Section>

        <Section title="12. Suspensión y terminación">
          <p>
            Podemos suspender o dar de baja una cuenta ante incumplimientos graves de
            estos términos, falta de pago o uso que comprometa la seguridad o estabilidad
            del Servicio. Salvo urgencia de seguridad, te notificaremos antes y te daremos
            oportunidad de subsanar el incumplimiento.
          </p>
        </Section>

        <Section title="13. Cambios en los términos">
          <p>
            Podemos actualizar estos términos. Si el cambio es sustancial, te avisaremos
            con al menos 30 días de anticipación por correo o desde el propio sistema. El
            uso del Servicio con posterioridad a la entrada en vigor implica aceptación.
          </p>
        </Section>

        <Section title="14. Ley aplicable y jurisdicción">
          <p>
            Estos términos se rigen por las leyes de la República Argentina. Para
            cualquier controversia, las partes se someten a los tribunales ordinarios
            competentes de la Ciudad Autónoma de Buenos Aires, sin perjuicio del fuero que
            corresponda cuando la contraparte revista el carácter de consumidor.
          </p>
        </Section>

        <Section title="15. Contacto">
          <p>
            Soporte:{" "}
            <a className="text-brand-700 underline" href="mailto:support@hotels-pms.com">
              support@hotels-pms.com
            </a>
            <br />
            Seguridad:{" "}
            <a className="text-brand-700 underline" href="mailto:security@hotels-pms.com">
              security@hotels-pms.com
            </a>
            <br />
            Facturación:{" "}
            <a className="text-brand-700 underline" href="mailto:billing@hotels-pms.com">
              billing@hotels-pms.com
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
