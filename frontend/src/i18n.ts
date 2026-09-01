import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enAppshell from "./locales/en/appshell.json";
import enAuth from "./locales/en/auth.json";
import enCommon from "./locales/en/common.json";
import enDashboard from "./locales/en/dashboard.json";
import enGuests from "./locales/en/guests.json";
import enReservations from "./locales/en/reservations.json";
import enRooms from "./locales/en/rooms.json";
import esAppshell from "./locales/es/appshell.json";
import esAuth from "./locales/es/auth.json";
import esCommon from "./locales/es/common.json";
import esDashboard from "./locales/es/dashboard.json";
import esGuests from "./locales/es/guests.json";
import esReservations from "./locales/es/reservations.json";
import esRooms from "./locales/es/rooms.json";

export type InterfaceLanguage = "es" | "en";

export const normalizeInterfaceLanguage = (value: unknown): InterfaceLanguage => (value === "en" ? "en" : "es");

export const interfaceLanguageToLocale = (language?: string | null): "es-AR" | "en-US" =>
  normalizeInterfaceLanguage(language) === "en" ? "en-US" : "es-AR";

// eslint-disable-next-line import/no-named-as-default-member -- i18next's documented init pattern
void i18n.use(initReactI18next).init({
  resources: {
    es: { auth: esAuth, common: esCommon, appshell: esAppshell, dashboard: esDashboard, guests: esGuests, rooms: esRooms, reservations: esReservations },
    en: { auth: enAuth, common: enCommon, appshell: enAppshell, dashboard: enDashboard, guests: enGuests, rooms: enRooms, reservations: enReservations }
  },
  lng: "es",
  fallbackLng: "es",
  supportedLngs: ["es", "en"],
  defaultNS: "common",
  ns: ["auth", "common", "appshell", "dashboard", "guests", "rooms", "reservations"],
  interpolation: { escapeValue: false },
  returnNull: false
});

export default i18n;
