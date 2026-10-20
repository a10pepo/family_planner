import { describe, expect, it, vi } from "vitest";
import { initializeAuth } from "./auth";

describe("custom Cognito family access", () => {
  it("restores a valid Cognito session before the app is rendered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/v1/config")
          return {
            ok: true,
            json: async () => ({
              timezone: "Europe/Madrid",
              oauth_provider: "cognito",
              client_id: "public-client",
              user_pool_id: "eu-west-1_pool",
              aws_region: "eu-west-1",
            }),
          } as Response;
        expect(url).toBe("/api/v1/auth/refresh");
        return {
          ok: true,
          json: async () => ({
            access_token: "restored-access-token",
            expires_in: 900,
          }),
        } as Response;
      }),
    );

    const { auth } = await initializeAuth();
    expect(auth.authenticated).toBe(true);
    expect(auth.token).toBe("restored-access-token");
    vi.unstubAllGlobals();
  });

  it("uses the public user pool API for registration, verification, login, and recovery", async () => {
    const requests: { url: string; headers: HeadersInit; body: string }[] = [];
    const sessionRequests: {
      url: string;
      body: string;
      credentials?: RequestCredentials;
    }[] = [];
    let signUpUsername = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/v1/config") {
          return {
            ok: true,
            json: async () => ({
              timezone: "Europe/Madrid",
              oauth_provider: "cognito",
              client_id: "public-client",
              user_pool_id: "eu-west-1_pool",
              aws_region: "eu-west-1",
            }),
          } as Response;
        }
        if (url.startsWith("/api/v1/auth/")) {
          sessionRequests.push({
            url,
            body: String(init?.body ?? ""),
            credentials: init?.credentials,
          });
          if (url.endsWith("/refresh"))
            return {
              ok: false,
              status: 401,
              json: async () => ({}),
            } as Response;
          if (url.endsWith("/session"))
            return {
              ok: true,
              status: 200,
              json: async () => ({
                access_token: "server-access-token",
                expires_in: 900,
              }),
            } as Response;
          return { ok: true, status: 204 } as Response;
        }
        requests.push({
          url,
          headers: init?.headers ?? {},
          body: String(init?.body),
        });
        const target = (init?.headers as Record<string, string>)[
          "X-Amz-Target"
        ];
        const requestBody = JSON.parse(String(init?.body));
        if (target?.endsWith("SignUp")) signUpUsername = requestBody.Username;
        const result =
          target?.endsWith("InitiateAuth") &&
          JSON.parse(String(init?.body)).AuthFlow === "USER_PASSWORD_AUTH"
            ? {
                AuthenticationResult: {
                  AccessToken: "access-token",
                  RefreshToken: "refresh-token",
                  ExpiresIn: 900,
                },
              }
            : {};
        return { ok: true, json: async () => result } as Response;
      }),
    );

    const { auth } = await initializeAuth();
    await auth.signUp?.("family@example.com", "A-strong-password-123!");
    await auth.resendSignUpCode?.("family@example.com");
    await auth.confirmSignUp?.("family@example.com", "654321");
    await auth.signIn?.("family@example.com", "A-strong-password-123!");
    await auth.forgotPassword?.("family@example.com");
    await auth.confirmForgotPassword?.(
      "family@example.com",
      "654321",
      "Another-strong-password-456!",
    );

    expect(auth.authenticated).toBe(true);
    expect(auth.token).toBe("server-access-token");
    expect(requests).toHaveLength(6);
    expect(
      requests.every((request) => request.url.endsWith("amazonaws.com/")),
    ).toBe(true);
    expect(
      requests.map((request) =>
        (request.headers as Record<string, string>)["X-Amz-Target"]
          .split(".")
          .at(-1),
      ),
    ).toEqual([
      "SignUp",
      "ResendConfirmationCode",
      "ConfirmSignUp",
      "InitiateAuth",
      "ForgotPassword",
      "ConfirmForgotPassword",
    ]);
    expect(JSON.parse(requests[1].body).Username).toBe(signUpUsername);
    expect(JSON.parse(requests[2].body).Username).toBe(signUpUsername);
    expect(requests[3].body).toContain("USER_PASSWORD_AUTH");
    expect(sessionRequests.map((request) => request.url)).toEqual([
      "/api/v1/auth/refresh",
      "/api/v1/auth/session",
    ]);
    expect(JSON.parse(sessionRequests[1].body)).toEqual({
      refresh_token: "refresh-token",
    });
    expect(
      sessionRequests.every((request) => request.credentials === "same-origin"),
    ).toBe(true);
    const signUpBody = JSON.parse(requests[0].body);
    expect(signUpBody.Username).toMatch(/^family-[0-9a-f-]{36}$/);
    expect(signUpBody.Username).not.toBe("family@example.com");
    expect(signUpBody.UserAttributes).toEqual([
      { Name: "email", Value: "family@example.com" },
    ]);
    expect(
      requests.some((request) => request.body.includes("client_secret")),
    ).toBe(false);

    await auth.logout();
    expect(auth.authenticated).toBe(false);
    expect(auth.token).toBeUndefined();
    expect(sessionRequests.at(-1)?.url).toBe("/api/v1/auth/logout");
    vi.unstubAllGlobals();
  });
});
