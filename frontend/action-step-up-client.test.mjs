import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const clientSource = await readFile(new URL("./src/api/client.ts", import.meta.url), "utf8");

const session = {
  hotelId: 7,
  userId: "owner@example.test",
  accessToken: "test-access-token",
  csrfToken: "test-csrf-token"
};

function loadClient(fetchImpl) {
  const source = clientSource.replace("import.meta.env.VITE_API_URL", "undefined");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022
    }
  }).outputText;
  const module = { exports: {} };
  const locationAssignments = [];

  vm.runInNewContext(
    compiled,
    {
      module,
      exports: module.exports,
      require: () => ({ broadcastDomainChange() {} }),
      fetch: fetchImpl,
      Headers,
      URL,
      atob,
      window: {
        location: {
          pathname: "/reservations",
          assign(value) {
            locationAssignments.push(value);
          }
        }
      }
    },
    { filename: "frontend/src/api/client.ts" }
  );

  return { client: module.exports, locationAssignments };
}

const jsonResponse = (status, payload) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });

const stepUpRequired = (path, permissionCode = "reservation:cancel", method = "POST") =>
  jsonResponse(428, {
    detail: {
      code: "STEP_UP_REQUIRED",
      permission_code: permissionCode,
      method,
      path
    }
  });

const permissionAdminReadStepUpRequired = (path) =>
  stepUpRequired(path, "permissions:manage", "GET");

const tick = () => new Promise((resolve) => setImmediate(resolve));

const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (predicate()) return;
    await tick();
  }
  assert.fail("Timed out waiting for the action step-up queue");
}

test("a 401 received after logout neither refreshes, redirects, nor restores the old session", async () => {
  const delayed401 = deferred();
  let refreshCalls = 0;
  const protectedRequests = [];
  const { client, locationAssignments } = loadClient(async (url, init) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/session/refresh")) {
      refreshCalls += 1;
      return jsonResponse(200, {
        access_token: "stale-refreshed-token",
        hotel_id: 7,
        user: { id: 1, email: session.userId, role: "owner" }
      });
    }
    protectedRequests.push(new Headers(init.headers));
    return protectedRequests.length === 1 ? delayed401.promise : jsonResponse(200, { ok: true });
  });
  let authResponses = 0;
  client.setClientSession(session);
  client.setAuthResponseHandler(() => {
    authResponses += 1;
  });

  const pendingRequest = client.apiFetch("/api/reservations");
  await waitFor(() => protectedRequests.length === 1);
  client.setClientSession(null);
  delayed401.resolve(jsonResponse(401, { detail: "Access token expired" }));

  await assert.rejects(pendingRequest, (error) => error.status === 401);
  await client.apiFetch("/api/reservations");

  assert.equal(refreshCalls, 0);
  assert.equal(authResponses, 0);
  assert.deepEqual(locationAssignments, []);
  assert.equal(protectedRequests[1].get("Authorization"), null);
});

test("a late 401 from a prior account or hotel cannot refresh or replace the current session", async (t) => {
  const switchedSessions = [
    { name: "account switch", nextSession: { ...session, userId: "staff@example.test", accessToken: "staff-token" } },
    { name: "hotel switch", nextSession: { ...session, hotelId: 8, accessToken: "other-hotel-token" } }
  ];

  for (const { name, nextSession } of switchedSessions) {
    await t.test(name, async () => {
      const delayed401 = deferred();
      let refreshCalls = 0;
      const protectedRequests = [];
      const { client, locationAssignments } = loadClient(async (url, init) => {
        const pathname = new URL(String(url)).pathname;
        if (pathname.endsWith("/auth/session/refresh")) {
          refreshCalls += 1;
          return jsonResponse(200, {
            access_token: "stale-refreshed-token",
            hotel_id: 7,
            user: { id: 1, email: session.userId, role: "owner" }
          });
        }
        protectedRequests.push(new Headers(init.headers));
        return protectedRequests.length === 1 ? delayed401.promise : jsonResponse(200, { ok: true });
      });
      let authResponses = 0;
      client.setClientSession(session);
      client.setAuthResponseHandler(() => {
        authResponses += 1;
      });

      const pendingRequest = client.apiFetch("/api/reservations");
      await waitFor(() => protectedRequests.length === 1);
      client.setClientSession(nextSession);
      delayed401.resolve(jsonResponse(401, { detail: "Access token expired" }));

      await assert.rejects(pendingRequest, (error) => error.status === 401);
      await client.apiFetch("/api/reservations");

      assert.equal(refreshCalls, 0);
      assert.equal(authResponses, 0);
      assert.deepEqual(locationAssignments, []);
      assert.equal(protectedRequests[1].get("Authorization"), `Bearer ${nextSession.accessToken}`);
      assert.equal(protectedRequests[1].get("X-User-Id"), nextSession.userId);
      assert.equal(protectedRequests[1].get("X-Hotel-Id"), String(nextSession.hotelId));
    });
  }
});

test("a refresh finishing after logout cannot persist or replay its old response", async () => {
  const delayedRefresh = deferred();
  let refreshCalls = 0;
  const protectedRequests = [];
  const { client, locationAssignments } = loadClient(async (url, init) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/session/refresh")) {
      refreshCalls += 1;
      return delayedRefresh.promise;
    }
    protectedRequests.push(new Headers(init.headers));
    return protectedRequests.length === 1
      ? jsonResponse(401, { detail: "Access token expired" })
      : jsonResponse(200, { ok: true });
  });
  let authResponses = 0;
  client.setClientSession(session);
  client.setAuthResponseHandler(() => {
    authResponses += 1;
  });

  const pendingRequest = client.apiFetch("/api/reservations");
  await waitFor(() => refreshCalls === 1);
  client.setClientSession(null);
  delayedRefresh.resolve(
    jsonResponse(200, {
      access_token: "stale-refreshed-token",
      hotel_id: 7,
      user: { id: 1, email: session.userId, role: "owner" }
    })
  );

  await assert.rejects(pendingRequest, (error) => error.status === 401);
  await client.apiFetch("/api/reservations");

  assert.equal(refreshCalls, 1);
  assert.equal(protectedRequests.length, 2);
  assert.equal(authResponses, 0);
  assert.deepEqual(locationAssignments, []);
  assert.equal(protectedRequests[1].get("Authorization"), null);
});

test("a refresh finishing after an account or hotel switch cannot persist its old response", async (t) => {
  const switchedSessions = [
    { name: "account switch", nextSession: { ...session, userId: "staff@example.test", accessToken: "staff-token" } },
    { name: "hotel switch", nextSession: { ...session, hotelId: 8, accessToken: "other-hotel-token" } }
  ];

  for (const { name, nextSession } of switchedSessions) {
    await t.test(name, async () => {
      const delayedRefresh = deferred();
      let refreshCalls = 0;
      const protectedRequests = [];
      const { client, locationAssignments } = loadClient(async (url, init) => {
        const pathname = new URL(String(url)).pathname;
        if (pathname.endsWith("/auth/session/refresh")) {
          refreshCalls += 1;
          return delayedRefresh.promise;
        }
        protectedRequests.push(new Headers(init.headers));
        return protectedRequests.length === 1
          ? jsonResponse(401, { detail: "Access token expired" })
          : jsonResponse(200, { ok: true });
      });
      let authResponses = 0;
      client.setClientSession(session);
      client.setAuthResponseHandler(() => {
        authResponses += 1;
      });

      const pendingRequest = client.apiFetch("/api/reservations");
      await waitFor(() => refreshCalls === 1);
      client.setClientSession(nextSession);
      delayedRefresh.resolve(
        jsonResponse(200, {
          access_token: "stale-refreshed-token",
          hotel_id: 7,
          user: { id: 1, email: session.userId, role: "owner" }
        })
      );

      await assert.rejects(pendingRequest, (error) => error.status === 401);
      await client.apiFetch("/api/reservations");

      assert.equal(refreshCalls, 1);
      assert.equal(protectedRequests.length, 2);
      assert.equal(authResponses, 0);
      assert.deepEqual(locationAssignments, []);
      assert.equal(protectedRequests[1].get("Authorization"), `Bearer ${nextSession.accessToken}`);
      assert.equal(protectedRequests[1].get("X-User-Id"), nextSession.userId);
      assert.equal(protectedRequests[1].get("X-Hotel-Id"), String(nextSession.hotelId));
    });
  }
});

test("a failed refresh from the prior account does not redirect or clear the current account", async () => {
  const delayedRefresh = deferred();
  const nextSession = { ...session, userId: "staff@example.test", accessToken: "staff-token" };
  let refreshCalls = 0;
  const protectedRequests = [];
  const { client, locationAssignments } = loadClient(async (url, init) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/session/refresh")) {
      refreshCalls += 1;
      return delayedRefresh.promise;
    }
    protectedRequests.push(new Headers(init.headers));
    return protectedRequests.length === 1
      ? jsonResponse(401, { detail: "Access token expired" })
      : jsonResponse(200, { ok: true });
  });
  client.setClientSession(session);

  const pendingRequest = client.apiFetch("/api/reservations");
  await waitFor(() => refreshCalls === 1);
  client.setClientSession(nextSession);
  delayedRefresh.resolve(jsonResponse(401, { detail: "Refresh session expired" }));

  await assert.rejects(pendingRequest, (error) => error.status === 401);
  await client.apiFetch("/api/reservations");

  assert.equal(refreshCalls, 1);
  assert.deepEqual(locationAssignments, []);
  assert.equal(protectedRequests[1].get("Authorization"), `Bearer ${nextSession.accessToken}`);
  assert.equal(protectedRequests[1].get("X-User-Id"), nextSession.userId);
});

test("concurrent 401s for the same session share one refresh and both retry", async () => {
  let refreshCalls = 0;
  let protectedCalls = 0;
  const client = loadClient(async (url) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/session/refresh")) {
      refreshCalls += 1;
      return jsonResponse(200, {
        access_token: "refreshed-access-token",
        hotel_id: 7,
        user: { id: 1, email: session.userId, role: "owner" }
      });
    }
    protectedCalls += 1;
    return protectedCalls <= 2 ? jsonResponse(401, { detail: "Access token expired" }) : jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);

  const results = await Promise.all([
    client.apiFetch("/api/reservations/first"),
    client.apiFetch("/api/reservations/second")
  ]);

  assert.equal(refreshCalls, 1);
  assert.equal(protectedCalls, 4);
  assert.deepEqual(results.map((result) => result.ok), [true, true]);
});

test("a STEP_UP_REQUIRED response arriving after logout does not open a prompt", async () => {
  const delayedChallenge = deferred();
  let protectedCalls = 0;
  let promptCalls = 0;
  const client = loadClient(async () => {
    protectedCalls += 1;
    return delayedChallenge.promise;
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    promptCalls += 1;
    return "must-not-be-requested";
  });

  const pendingRequest = client.apiFetch("/api/reservations/42/cancel", { method: "POST" });
  await waitFor(() => protectedCalls === 1);
  client.setClientSession(null);
  delayedChallenge.resolve(stepUpRequired("/api/reservations/42/cancel"));

  await assert.rejects(
    pendingRequest,
    (error) => error.status === 428 && error.payload.detail.code === "STEP_UP_REQUIRED"
  );
  assert.equal(promptCalls, 0);
  assert.equal(protectedCalls, 1);
});

test("logout while the step-up prompt is open prevents retry even if its handler returns a ticket", async () => {
  const lateTicket = deferred();
  let protectedCalls = 0;
  let promptCalls = 0;
  const client = loadClient(async () => {
    protectedCalls += 1;
    return protectedCalls === 1
      ? stepUpRequired("/api/reservations/42/cancel")
      : jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    promptCalls += 1;
    return lateTicket.promise;
  });

  const pendingRequest = client.apiFetch("/api/reservations/42/cancel", { method: "POST" });
  await waitFor(() => promptCalls === 1);
  client.setClientSession(null);
  lateTicket.resolve("ticket-returned-after-logout");

  await assert.rejects(
    pendingRequest,
    (error) => error.status === 428 && error.payload.detail.code === "STEP_UP_REQUIRED"
  );
  assert.equal(promptCalls, 1);
  assert.equal(protectedCalls, 1);
});

test("a STEP_UP_REQUIRED response prompts once and retries only that request with its ticket", async () => {
  const requests = [];
  const client = loadClient(async (url, init) => {
    requests.push({ url: String(url), init, headers: new Headers(init.headers) });
    return requests.length === 1 ? stepUpRequired("/api/bookings/42/cancel") : jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);

  const challenges = [];
  client.setActionStepUpHandler(async (challenge, requestSession) => {
    challenges.push({ challenge, requestSession });
    return "signed-step-up-ticket";
  });

  const result = await client.apiFetch("/api/bookings/42/cancel", {
    method: "POST",
    data: { reason: "guest request" }
  });

  assert.equal(result.ok, true);
  assert.equal(challenges.length, 1);
  assert.equal(challenges[0].challenge.permissionCode, "reservation:cancel");
  assert.equal(challenges[0].challenge.method, "POST");
  assert.equal(challenges[0].challenge.path, "/api/bookings/42/cancel");
  assert.equal(challenges[0].requestSession.accessToken, session.accessToken);
  assert.equal(requests.length, 2);
  assert.equal(requests[0].headers.get("X-Action-Step-Up-Ticket"), null);
  assert.equal(requests[1].headers.get("X-Action-Step-Up-Ticket"), "signed-step-up-ticket");
  assert.equal(requests[0].init.body, requests[1].init.body);
  assert.equal(requests[1].headers.get("X-CSRF-Token"), session.csrfToken);
});

test("missing or canceled UI surfaces the original 428 without retrying", async (t) => {
  for (const mode of ["unmounted", "canceled"]) {
    await t.test(mode, async () => {
      let requests = 0;
      const client = loadClient(async () => {
        requests += 1;
        return stepUpRequired("/api/bookings/42/cancel");
      }).client;
      client.setClientSession(session);
      if (mode === "canceled") client.setActionStepUpHandler(async () => null);

      await assert.rejects(
        client.apiFetch("/api/bookings/42/cancel", { method: "POST" }),
        (error) => error.status === 428 && error.payload.detail.code === "STEP_UP_REQUIRED"
      );
      assert.equal(requests, 1);
    });
  }
});

test("concurrent challenges serialize prompts and never share tickets", async () => {
  const requests = [];
  const client = loadClient(async (url, init) => {
    const requestUrl = String(url);
    requests.push({ url: requestUrl, headers: new Headers(init.headers) });
    const pathname = new URL(requestUrl).pathname;
    const countForPath = requests.filter((request) => new URL(request.url).pathname === pathname).length;
    return countForPath === 1 ? stepUpRequired(pathname) : jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);

  const promptResolvers = [];
  const promptPaths = [];
  let activePrompts = 0;
  let maximumActivePrompts = 0;
  client.setActionStepUpHandler((challenge) => {
    promptPaths.push(challenge.path);
    activePrompts += 1;
    maximumActivePrompts = Math.max(maximumActivePrompts, activePrompts);
    return new Promise((resolve) => {
      promptResolvers.push((ticket) => {
        activePrompts -= 1;
        resolve(ticket);
      });
    });
  });

  const firstRequest = client.apiFetch("/api/bookings/first/cancel", { method: "POST" });
  const secondRequest = client.apiFetch("/api/bookings/second/cancel", { method: "POST" });
  await waitFor(() => promptResolvers.length === 1);
  assert.equal(maximumActivePrompts, 1);

  promptResolvers[0]("ticket-for-first");
  await waitFor(() => promptResolvers.length === 2);
  assert.deepEqual(promptPaths, ["/api/bookings/first/cancel", "/api/bookings/second/cancel"]);
  promptResolvers[1]("ticket-for-second");

  const results = await Promise.all([firstRequest, secondRequest]);
  assert.deepEqual(results.map((result) => result.ok), [true, true]);
  assert.equal(maximumActivePrompts, 1);
  const retries = requests.filter((request) => request.headers.has("X-Action-Step-Up-Ticket"));
  assert.deepEqual(
    retries.map((request) => [new URL(request.url).pathname, request.headers.get("X-Action-Step-Up-Ticket")]),
    [
      ["/api/bookings/first/cancel", "ticket-for-first"],
      ["/api/bookings/second/cancel", "ticket-for-second"]
    ]
  );
});

test("concurrent RBAC reads reuse one short read-only grant without weakening write step-up", async () => {
  const requests = [];
  const client = loadClient(async (url, init) => {
    const parsedUrl = new URL(String(url));
    const path = parsedUrl.pathname;
    const method = init.method;
    const ticket = new Headers(init.headers).get("X-Action-Step-Up-Ticket");
    requests.push({ path, method, ticket });

    if (path.startsWith("/api/permissions/") && method === "GET") {
      return ticket === "permission-admin-read-grant"
        ? jsonResponse(200, { path })
        : permissionAdminReadStepUpRequired(path);
    }
    if (path === "/api/permissions/override" && method === "PUT") {
      return ticket === "write-action-ticket"
        ? jsonResponse(200, { updated: true })
        : stepUpRequired(path, "permissions:manage", "PUT");
    }
    return jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);

  const challenges = [];
  client.setActionStepUpHandler(async (challenge) => {
    challenges.push(challenge);
    if (challenge.method === "GET") {
      return {
        ticket: "permission-admin-read-grant",
        scope: "permission_admin_read",
        expiresInSeconds: 120
      };
    }
    return "write-action-ticket";
  });

  const readPaths = [
    "/api/permissions/catalog",
    "/api/permissions/matrix",
    "/api/permissions/role-overrides",
    "/api/permissions/visibility-windows",
    "/api/permissions/user-overrides/20",
    "/api/permissions/effective/preview?user_id=20"
  ];
  const readResults = await Promise.all(readPaths.map((path) => client.apiFetch(path)));
  assert.equal(readResults.length, readPaths.length);
  assert.deepEqual(challenges.map(({ method }) => method), ["GET"]);

  await client.apiFetch("/api/users/");
  const ordinaryRead = requests.find(({ path }) => path === "/api/users/");
  assert.equal(ordinaryRead.ticket, null);

  await client.apiFetch("/api/permissions/override", {
    method: "PUT",
    data: { role: "manager", permission_code: "reservation:create", allowed: false }
  });
  const writeRetries = requests.filter(
    ({ path, method }) => path === "/api/permissions/override" && method === "PUT"
  );
  assert.deepEqual(writeRetries.map(({ ticket }) => ticket), [null, "write-action-ticket"]);
  assert.deepEqual(challenges.map(({ method }) => method), ["GET", "PUT"]);
  assert.equal(requests.some(({ method, ticket }) => method !== "GET" && ticket === "permission-admin-read-grant"), false);
});

test("an RBAC read grant is cleared when the active account or hotel changes", async (t) => {
  const nextSessions = [
    { name: "account change", session: { ...session, userId: "staff@example.test", accessToken: "staff-token" } },
    { name: "hotel change", session: { ...session, hotelId: 8, accessToken: "other-hotel-token" } }
  ];

  for (const { name, session: nextSession } of nextSessions) {
    await t.test(name, async () => {
      const requests = [];
      let issueCount = 0;
      const client = loadClient(async (url, init) => {
        const path = new URL(String(url)).pathname;
        const headers = new Headers(init.headers);
        const ticket = headers.get("X-Action-Step-Up-Ticket");
        const hotelId = headers.get("X-Hotel-Id");
        const userId = headers.get("X-User-Id");
        requests.push({ path, ticket, hotelId, userId });
        return ticket === `read-grant-${hotelId}`
          ? jsonResponse(200, { ok: true })
          : permissionAdminReadStepUpRequired(path);
      }).client;
      client.setClientSession(session);
      client.setActionStepUpHandler(async (_challenge, requestSession) => {
        issueCount += 1;
        return {
          ticket: `read-grant-${requestSession.hotelId}`,
          scope: "permission_admin_read",
          expiresInSeconds: 120
        };
      });

      // Populate the cache for the original identity, then switch contexts.
      await client.apiFetch("/api/permissions/catalog");
      client.setClientSession(nextSession);
      await client.apiFetch("/api/permissions/catalog");

      const switchedRequest = requests.find(({ userId }) => userId === nextSession.userId);
      assert.ok(switchedRequest);
      assert.equal(switchedRequest.ticket, null);
      assert.equal(issueCount, 2);
    });
  }
});

test("a rejected RBAC read grant is evicted without replaying the same prompt", async () => {
  const requests = [];
  let promptCount = 0;
  const client = loadClient(async (url, init) => {
    const path = new URL(String(url)).pathname;
    const ticket = new Headers(init.headers).get("X-Action-Step-Up-Ticket");
    requests.push(ticket);
    return ticket === "fresh-read-grant"
      ? jsonResponse(200, { ok: true })
      : permissionAdminReadStepUpRequired(path);
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    promptCount += 1;
    return {
      ticket: promptCount === 1 ? "stale-read-grant" : "fresh-read-grant",
      scope: "permission_admin_read",
      expiresInSeconds: 120
    };
  });

  await assert.rejects(client.apiFetch("/api/permissions/catalog"), (error) => error.status === 428);
  assert.equal(promptCount, 1);
  assert.deepEqual(requests, [null, "stale-read-grant"]);

  await client.apiFetch("/api/permissions/catalog");
  assert.equal(promptCount, 2);
  assert.deepEqual(requests, [null, "stale-read-grant", null, "fresh-read-grant"]);
});

test("an aborted queued request does not open a stale step-up prompt", async () => {
  const requests = [];
  const client = loadClient(async (url) => {
    const pathname = new URL(String(url)).pathname;
    requests.push(pathname);
    const countForPath = requests.filter((requestPath) => requestPath === pathname).length;
    return countForPath === 1 ? stepUpRequired(pathname) : jsonResponse(200, { ok: true });
  }).client;
  client.setClientSession(session);

  let releaseFirstPrompt;
  const prompts = [];
  client.setActionStepUpHandler((challenge) => {
    prompts.push(challenge.path);
    if (prompts.length > 1) return Promise.resolve("unexpected-second-ticket");
    return new Promise((resolve) => {
      releaseFirstPrompt = resolve;
    });
  });

  const firstRequest = client.apiFetch("/api/bookings/first/cancel", { method: "POST" });
  const controller = new AbortController();
  const secondRequest = client.apiFetch("/api/bookings/second/cancel", {
    method: "POST",
    signal: controller.signal
  });
  await waitFor(() => typeof releaseFirstPrompt === "function" && requests.length === 2);
  controller.abort();
  releaseFirstPrompt("ticket-for-first");

  assert.equal((await firstRequest).ok, true);
  await assert.rejects(secondRequest, (error) => error.status === 428);
  assert.deepEqual(prompts, ["/api/bookings/first/cancel"]);
});

test("a retried 428 does not reopen the prompt", async () => {
  let requests = 0;
  let prompts = 0;
  const client = loadClient(async () => {
    requests += 1;
    return stepUpRequired("/api/bookings/42/cancel");
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    prompts += 1;
    return "single-use-for-this-retry";
  });

  await assert.rejects(
    client.apiFetch("/api/bookings/42/cancel", { method: "POST" }),
    (error) => error.status === 428
  );
  assert.equal(prompts, 1);
  assert.equal(requests, 2);
});

test("401 refresh after the ticketed retry does not resend the ticket or reopen the prompt", async () => {
  const protectedCalls = [];
  let refreshCalls = 0;
  let prompts = 0;
  const client = loadClient(async (url, init) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/session/refresh")) {
      refreshCalls += 1;
      return jsonResponse(200, {
        access_token: "refreshed-access-token",
        hotel_id: 7,
        user: { id: 1, email: "owner@example.test", role: "owner" }
      });
    }
    const ticket = new Headers(init.headers).get("X-Action-Step-Up-Ticket");
    protectedCalls.push(ticket);
    if (protectedCalls.length === 1) return stepUpRequired("/api/bookings/42/cancel");
    if (protectedCalls.length === 2) return jsonResponse(401, { detail: "Access token expired" });
    return stepUpRequired("/api/bookings/42/cancel");
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    prompts += 1;
    return "ticket-for-one-request";
  });

  await assert.rejects(
    client.apiFetch("/api/bookings/42/cancel", { method: "POST" }),
    (error) => error.status === 428
  );
  assert.equal(refreshCalls, 1);
  assert.equal(prompts, 1);
  assert.deepEqual(protectedCalls, [null, "ticket-for-one-request", null]);
});

test("the step-up endpoint uses normal auth and CSRF headers without recursing", async () => {
  let request;
  let prompts = 0;
  const client = loadClient(async (url, init) => {
    request = { url: String(url), init, headers: new Headers(init.headers) };
    return jsonResponse(200, { ticket: "signed-ticket", permission_code: "reservation:cancel", expires_in: 120 });
  }).client;
  client.setClientSession(session);
  client.setActionStepUpHandler(async () => {
    prompts += 1;
    return null;
  });

  const result = await client.apiFetch("/api/auth/step-up", {
    method: "POST",
    data: {
      code: "123456",
      permission_code: "reservation:cancel",
      method: "POST",
      path: "/api/bookings/42/cancel"
    },
    session
  });

  assert.equal(result.ticket, "signed-ticket");
  assert.equal(prompts, 0);
  assert.match(request.url, /\/api\/auth\/step-up$/);
  assert.equal(request.headers.get("Authorization"), `Bearer ${session.accessToken}`);
  assert.equal(request.headers.get("X-CSRF-Token"), session.csrfToken);
});

test("an invalid TOTP does not trigger session refresh or logout", async () => {
  let requests = 0;
  const { client, locationAssignments } = loadClient(async () => {
    requests += 1;
    return jsonResponse(401, { detail: "Codigo MFA invalido o ya utilizado" });
  });
  client.setClientSession(session);

  await assert.rejects(
    client.apiFetch("/api/auth/step-up", { method: "POST", data: { code: "000000" }, session }),
    (error) => error.status === 401
  );
  assert.equal(requests, 1);
  assert.deepEqual(locationAssignments, []);
});
