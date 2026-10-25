import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveFxRoundingPolicy,
  roundFxAmount,
  suggestFxTenderSettlement
} from "./src/utils/fxRounding.mjs";

test("FX policy preserves two minor digits by default", () => {
  assert.equal(roundFxAmount(56.4), 56.4);
  assert.equal(roundFxAmount(65.145), 65.15);
  assert.equal(roundFxAmount(65.144), 65.14);
  assert.equal(roundFxAmount(18.93, "exact"), 18.93);
});

test("FX whole-unit policies round in the configured direction", () => {
  assert.equal(roundFxAmount(56.4, "round_up"), 57);
  assert.equal(roundFxAmount(56, "round_up"), 56);
  assert.equal(roundFxAmount(56.9, "round_down"), 56);
  assert.equal(roundFxAmount(56.5, "nearest_ten"), 60);
  assert.equal(roundFxAmount(54.9, "nearest_ten"), 50);
});

test("rounding only suggests cash tender; all payment methods retain the exact converted charge", () => {
  for (const policy of ["round_up", "round_down", "nearest_ten"]) {
    assert.equal(resolveFxRoundingPolicy("cash", policy), policy);
    for (const paymentMethod of ["credit_card", "debit_card", "bank_transfer"]) {
      assert.equal(resolveFxRoundingPolicy(paymentMethod, policy), "exact");
    }
  }

  const balance = 84600;
  const rate = 1500;
  const cash = suggestFxTenderSettlement(balance, rate, resolveFxRoundingPolicy("cash", "round_up"));
  const card = suggestFxTenderSettlement(balance, rate, resolveFxRoundingPolicy("credit_card", "round_up"));
  const transfer = suggestFxTenderSettlement(balance, rate, resolveFxRoundingPolicy("bank_transfer", "round_down"));

  assert.equal(cash?.tenderAmount, 56.4);
  assert.equal(cash?.suggestedTenderAmount, 57);
  assert.equal(card?.tenderAmount, 56.4);
  assert.equal(card?.suggestedTenderAmount, 56.4);
  assert.equal(transfer?.tenderAmount, 56.4);
  assert.equal(transfer?.suggestedTenderAmount, 56.4);
});

test("FX tender suggestions preserve the exact due and never create a rounding credit", () => {
  assert.deepEqual(suggestFxTenderSettlement(84650, 1500, "round_down"), {
    exactTenderAmount: 56.43,
    tenderAmount: 56.43,
    suggestedTenderAmount: 56,
    appliedAmount: 84645,
    remainingDue: 5,
    creditAmount: 0,
    isPartial: true
  });
  assert.deepEqual(suggestFxTenderSettlement(84650, 1500, "keep_remainder"), {
    exactTenderAmount: 56.43,
    tenderAmount: 56.43,
    suggestedTenderAmount: 56.43,
    appliedAmount: 84645,
    remainingDue: 5,
    creditAmount: 0,
    isPartial: true
  });
  assert.deepEqual(suggestFxTenderSettlement(321.83, 17, "exact"), {
    exactTenderAmount: 18.93,
    tenderAmount: 18.93,
    suggestedTenderAmount: 18.93,
    appliedAmount: 321.81,
    remainingDue: 0.02,
    creditAmount: 0,
    isPartial: true
  });
  assert.deepEqual(suggestFxTenderSettlement(321.83, 17, "keep_remainder"), {
    exactTenderAmount: 18.93,
    tenderAmount: 18.93,
    suggestedTenderAmount: 18.93,
    appliedAmount: 321.81,
    remainingDue: 0.02,
    creditAmount: 0,
    isPartial: true
  });
  assert.deepEqual(suggestFxTenderSettlement(84650, 1500, "round_up"), {
    exactTenderAmount: 56.43,
    tenderAmount: 56.43,
    suggestedTenderAmount: 57,
    appliedAmount: 84645,
    remainingDue: 5,
    creditAmount: 0,
    isPartial: true
  });
});

test("FX tender suggestion lowers a rounded cent value that would exceed the reservation balance", () => {
  assert.deepEqual(suggestFxTenderSettlement(321.8, 17, "round_up"), {
    exactTenderAmount: 18.93,
    tenderAmount: 18.92,
    suggestedTenderAmount: 19,
    appliedAmount: 321.64,
    remainingDue: 0.16,
    creditAmount: 0,
    isPartial: true
  });
});

test("invalid FX settlement inputs do not produce a payment suggestion", () => {
  assert.equal(suggestFxTenderSettlement(100, 0), null);
  assert.equal(suggestFxTenderSettlement(Number.NaN, 10), null);
});
