import { API_BASE } from "./client";

export type PublicPricingPlan = {
  code: string;
  name: string;
  /** Null until the owner publishes a price from the master-admin console. */
  price_amount: string | null;
  currency: string | null;
  billing_period: string;
  headline: string | null;
  description: string | null;
  features: string[];
  room_limit: number | null;
  staff_limit: number | null;
  cta_label: string | null;
  cta_kind: string;
  highlight: boolean;
};

export type PublicPricing = {
  plans: PublicPricingPlan[];
  trial_days: number;
};

export type LeadPayload = {
  email: string;
  name?: string;
  hotel_name?: string;
  rooms_estimate?: number;
  city?: string;
  phone?: string;
  source?: string;
  utm?: Record<string, string>;
  /** Honeypot. Anything here means the submission was a bot. */
  company_website?: string;
};

// These two are the only unauthenticated calls the site makes, so they skip
// apiFetch and its session handling entirely.
export async function fetchPublicPricing(signal?: AbortSignal): Promise<PublicPricing> {
  const response = await fetch(`${API_BASE}/public/pricing`, { signal });
  if (!response.ok) throw new Error(`pricing ${response.status}`);
  return response.json();
}

export async function submitLead(payload: LeadPayload): Promise<void> {
  const response = await fetch(`${API_BASE}/public/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (response.status === 429) {
    throw new Error("rate_limited");
  }
  if (!response.ok) {
    throw new Error(`lead ${response.status}`);
  }
}
