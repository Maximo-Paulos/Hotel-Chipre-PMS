export type DashboardStats = {
  occupancy: number;
  adr: number;
  revenue: number;
  arrivalsToday: number;
  departuresToday: number;
};

export type Reservation = {
  id: string;
  guest: string;
  room: string;
  checkIn: string;
  checkOut: string;
  status: "confirmada" | "check-in" | "checkout" | "no-show" | "cancelada";
  channel: "Directo" | "OTA" | "Agencia";
  amount: number;
};

export type Room = {
  number: string;
  category: string;
  floor: number;
  status: "Libre" | "Ocupada" | "Limpieza";
  note?: string;
};

export type Activity = {
  time: string;
  description: string;
  tone?: "info" | "warning";
};

export const dashboardStats: DashboardStats = {
  occupancy: 82,
  adr: 95,
  revenue: 18250,
  arrivalsToday: 7,
  departuresToday: 5
};

export const mockReservations: Reservation[] = [
  {
    id: "R-1045",
    guest: "Ana Torres",
    room: "204",
    checkIn: "2026-03-31",
    checkOut: "2026-04-03",
    status: "check-in",
    channel: "Directo",
    amount: 450
  },
  {
    id: "R-1046",
    guest: "Luciano Pérez",
    room: "305",
    checkIn: "2026-03-31",
    checkOut: "2026-04-02",
    status: "confirmada",
    channel: "OTA",
    amount: 320
  },
  {
    id: "R-1047",
    guest: "Mariana Sosa",
    room: "101",
    checkIn: "2026-04-01",
    checkOut: "2026-04-04",
    status: "confirmada",
    channel: "Agencia",
    amount: 520
  },
  {
    id: "R-1048",
    guest: "Josefina Campos",
    room: "401",
    checkIn: "2026-03-30",
    checkOut: "2026-04-01",
    status: "checkout",
    channel: "Directo",
    amount: 260
  },
  {
    id: "R-1049",
    guest: "Martin Molina",
    room: "207",
    checkIn: "2026-03-31",
    checkOut: "2026-04-05",
    status: "check-in",
    channel: "OTA",
    amount: 650
  }
];

export const mockRooms: Room[] = [
  { number: "101", category: "Standard Doble", floor: 1, status: "Ocupada", note: "Salida 12:00" },
  { number: "102", category: "Standard Doble", floor: 1, status: "Limpieza", note: "Solicita toallas" },
  { number: "103", category: "Standard Twin", floor: 1, status: "Libre", note: "Vista interna" },
  { number: "201", category: "Suite", floor: 2, status: "Libre", note: "Vista al río" },
  { number: "204", category: "Superior", floor: 2, status: "Ocupada", note: "Late checkout" },
  { number: "301", category: "Suite Premium", floor: 3, status: "Ocupada", note: "VIP welcome" }
];

export const mockActivities: Activity[] = [
  { time: "09:15", description: "Check-in de Ana Torres en 204" },
  { time: "09:40", description: "Se asignó limpieza a 102", tone: "warning" },
  { time: "10:05", description: "Cobro de estadía de Martin Molina (R-1049)" },
  { time: "10:22", description: "Checkout confirmado de Josefina Campos (401)" }
];
