import { describe, expect, it, vi } from "vitest";
import { initializeAuth } from "./auth";

describe("custom Cognito family access", () => {
  it("uses the public user pool API for registration, verification, login, and recovery", async () => {
    const requests: { url: string; headers: HeadersInit; body: string }[] = [];
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
    expect(auth.token).toBe("access-token");
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
    const signUpBody = JSON.parse(requests[0].body);
    expect(signUpBody.Username).toMatch(/^family-[0-9a-f-]{36}$/);
    expect(signUpBody.Username).not.toBe("family@example.com");
    expect(signUpBody.UserAttributes).toEqual([
      { Name: "email", Value: "family@example.com" },
    ]);
    expect(
      requests.some((request) => request.body.includes("client_secret")),
    ).toBe(false);

    auth.clearToken();
    expect(auth.authenticated).toBe(false);
    expect(auth.token).toBeUndefined();
    vi.unstubAllGlobals();
  });
});
