# OTA prepaid amounts keep their source currency

## Decision

Manual OTA prepayments store both the amount confirmed by the channel and the currency the channel paid in. The amount remains separate from PMS transactions and physical cash. Revenue reports group it by that source currency and do not convert it.

An external amount reduces a reservation balance only when its currency matches the reservation's billing currency. If they differ, the PMS keeps the confirmed amount visible in its original currency and leaves the canonical reservation balance unchanged until an explicit conversion/credit rule is authorized. The UI identifies this as a recorded amount not applied to the reservation balance.

## Compatibility and migration

Older clients may omit the external payment currency; manual entry then uses the reservation currency. The migration backfills existing external amounts to the reservation currency, preserving the previous interpretation without inventing an FX rate. OTA adapters currently provide a single pricing currency, so their paid amounts inherit that currency until a provider contract supplies a separate paid currency.

## Consequences

- External OTA collections stay out of cash and PMS transaction totals.
- Cross-currency amounts remain reportable without being mixed into local balances.
- Any future conversion must be explicit and carry its own authorization and FX evidence.
