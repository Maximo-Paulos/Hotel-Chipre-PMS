export type DepositPolicyRule = {
  /** Cumulative upper bound; null means this is the final open-ended band. */
  max_nights: number | null;
  calculation: "percentage" | "nights";
  value: number;
};

export type DepositPolicyRules = DepositPolicyRule[];
