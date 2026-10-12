import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./src/hooks/useCollaborativeResource.ts", import.meta.url), "utf8");
const connectBlock = source.match(/const connect = async \(\) => \{([\s\S]*?)\n    \};/)?.[1] ?? "";

test("a collaboration ticket 503 stops automatic retry until the editor is reopened", () => {
  assert.ok(connectBlock, "the collaboration connection effect must remain defined");

  const unavailableBranch = connectBlock.match(
    /if \(cause instanceof ApiError && cause\.status === 503\) \{([\s\S]*?)\n\s*\}/
  );
  assert.ok(unavailableBranch, "ticket 503 must have a terminal unavailable branch");
  assert.match(unavailableBranch[1], /setStatus\("degraded"\)/);
  assert.match(unavailableBranch[1], /return;/);

  const retryScheduling = connectBlock.lastIndexOf("retryTimerRef.current = window.setTimeout");
  const unavailableReturn = connectBlock.indexOf("return;", unavailableBranch.index);
  assert.ok(retryScheduling > unavailableReturn, "503 must exit before retry scheduling");

  const socketClose = connectBlock.match(/socket\.onclose = \(event\) => \{([\s\S]*?)\n\s*\};/);
  assert.ok(socketClose, "WebSocket reconnect handling must remain defined");
  const terminalClose = socketClose[1].match(
    /if \(NON_RETRYABLE_COLLABORATION_CLOSE_CODES\.has\(event\.code\)\) \{([\s\S]*?)\n\s*\}/
  );
  assert.ok(terminalClose, "permanent WebSocket failures must not request another ticket");
  assert.match(terminalClose[1], /setStatus\("degraded"\)/);
  assert.match(terminalClose[1], /return;/);
  assert.match(socketClose[1], /retryTimerRef\.current = window\.setTimeout/);
  assert.match(source, /void Promise\.resolve\(\)\.then\(\(\) => \{/);
});

test("manual collaborative resource saves remain available when realtime is degraded", () => {
  const saveBlock = source.match(/const save = useCallback\(async \(\) => \{([\s\S]*?)\n  \}, \[/)?.[1] ?? "";

  assert.ok(saveBlock, "the manual save callback must remain defined");
  assert.match(saveBlock, /patchCollaborativeResource\(/);
  assert.doesNotMatch(saveBlock, /status === "degraded"/);
});
