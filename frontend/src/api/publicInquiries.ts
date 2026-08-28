import { apiFetch } from "./client";

export type PublicInquiryPayload = {
  name: string;
  email: string;
  company_name?: string;
  phone?: string;
  message: string;
  source_path: string;
  privacy_consent: boolean;
  website?: string;
};

export type PublicInquiryResponse = {
  status: "accepted";
};

export function submitPublicInquiry(payload: PublicInquiryPayload) {
  return apiFetch<PublicInquiryResponse>("/api/public/inquiries", {
    method: "POST",
    data: payload
  });
}
