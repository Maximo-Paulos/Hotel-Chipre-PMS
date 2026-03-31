import { apiFetch, type SessionLike } from "./client";

export type Category = {
  id: number;
  name: string;
  code: string;
  base_price_per_night: number;
  max_occupancy: number;
};

export const listCategories = (session?: SessionLike) =>
  apiFetch<Category[]>("/api/rooms/categories", { session });
