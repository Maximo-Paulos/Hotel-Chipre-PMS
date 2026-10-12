export const REALTIME_STREAM_STABLE_CONNECTION_MS = 60_000;

const BASE_RETRY_DELAY_MS = 1_000;
const MAX_RETRY_DELAY_MS = 60_000;
const MAX_FAILURE_COUNT = 10;

export type RealtimeRetryPlan = {
  failureCount: number;
  delayMs: number;
};

/** Keep exponential backoff across short-lived HTTP 200 event streams. */
export const nextRealtimeRetryPlan = (
  previousFailures: number,
  connectionDurationMs: number | null,
  randomValue: number
): RealtimeRetryPlan => {
  const connectionWasStable =
    connectionDurationMs !== null &&
    Number.isFinite(connectionDurationMs) &&
    connectionDurationMs >= REALTIME_STREAM_STABLE_CONNECTION_MS;
  const failureCount = connectionWasStable
    ? 1
    : Math.min(MAX_FAILURE_COUNT, Math.max(0, Math.floor(previousFailures)) + 1);
  const exponentialDelay = Math.min(
    MAX_RETRY_DELAY_MS,
    BASE_RETRY_DELAY_MS * 2 ** (failureCount - 1)
  );
  const jitterLimit = Math.max(250, exponentialDelay * 0.2);
  const boundedRandom = Number.isFinite(randomValue)
    ? Math.min(1, Math.max(0, randomValue))
    : 0;

  return {
    failureCount,
    delayMs: exponentialDelay + Math.floor(boundedRandom * jitterLimit)
  };
};
