import Keycloak from "keycloak-js";

export interface AppConfig {
  timezone: string;
  oauth_provider: "keycloak" | "cognito";
  oauth_url?: string;
  realm?: string;
  issuer?: string;
  authorization_endpoint?: string;
  token_endpoint?: string;
  logout_endpoint?: string;
  scopes?: string[];
  client_id: string;
}

export interface AuthClient {
  authenticated?: boolean;
  token?: string;
  onAuthLogout?: (() => void) | undefined;
  updateToken(minValidity: number): Promise<boolean>;
  clearToken(): void;
  login(options?: { redirectUri?: string }): void | Promise<void>;
  logout(options?: { redirectUri?: string }): void | Promise<void>;
}

class CognitoAuth implements AuthClient {
  authenticated = false;
  token?: string;
  onAuthLogout?: () => void;
  private refreshToken?: string;

  constructor(private config: AppConfig) {}

  async completeLogin() {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    if (!code) return;
    const state = url.searchParams.get("state");
    const expectedState = sessionStorage.getItem("cognito_state");
    const verifier = sessionStorage.getItem("cognito_verifier");
    sessionStorage.removeItem("cognito_state");
    sessionStorage.removeItem("cognito_verifier");
    if (!state || state !== expectedState || !verifier)
      throw new Error("La respuesta de inicio de sesión no es válida.");
    const tokens = await this.tokenRequest({
      grant_type: "authorization_code",
      code,
      redirect_uri: `${window.location.origin}/`,
      code_verifier: verifier,
    });
    this.setTokens(tokens);
    url.searchParams.delete("code");
    url.searchParams.delete("state");
    window.history.replaceState({}, document.title, url.pathname + url.hash);
  }

  async updateToken(minValidity: number) {
    if (this.token && this.expiresAt - Date.now() > minValidity * 1000)
      return false;
    if (!this.refreshToken) {
      this.clearToken();
      return false;
    }
    try {
      this.setTokens(
        await this.tokenRequest({
          grant_type: "refresh_token",
          refresh_token: this.refreshToken,
        }),
      );
      return true;
    } catch {
      this.clearToken();
      return false;
    }
  }

  clearToken() {
    this.token = undefined;
    this.refreshToken = undefined;
    this.authenticated = false;
    this.onAuthLogout?.();
  }

  async login() {
    const verifier = randomValue(64);
    const challenge = await sha256(verifier);
    const state = randomValue(32);
    sessionStorage.setItem("cognito_verifier", verifier);
    sessionStorage.setItem("cognito_state", state);
    const url = new URL(this.config.authorization_endpoint!);
    url.search = new URLSearchParams({
      response_type: "code",
      client_id: this.config.client_id,
      redirect_uri: `${window.location.origin}/`,
      scope: (this.config.scopes ?? []).join(" "),
      code_challenge_method: "S256",
      code_challenge: challenge,
      state,
    }).toString();
    window.location.assign(url);
  }

  logout() {
    this.clearToken();
    const url = new URL(this.config.logout_endpoint!);
    url.search = new URLSearchParams({
      client_id: this.config.client_id,
      logout_uri: `${window.location.origin}/`,
    }).toString();
    window.location.assign(url);
  }

  private expiresAt = 0;

  private async tokenRequest(params: Record<string, string>) {
    const response = await fetch(this.config.token_endpoint!, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        ...params,
        client_id: this.config.client_id,
      }),
    });
    if (!response.ok) throw new Error("No se pudo validar la sesión.");
    return response.json() as Promise<{
      access_token: string;
      refresh_token?: string;
      expires_in: number;
    }>;
  }

  private setTokens(tokens: {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
  }) {
    this.token = tokens.access_token;
    this.refreshToken = tokens.refresh_token ?? this.refreshToken;
    this.expiresAt = Date.now() + tokens.expires_in * 1000;
    this.authenticated = true;
  }
}

export async function initializeAuth() {
  const response = await fetch("/api/v1/config");
  if (!response.ok) throw new Error("No se puede conectar con la aplicación.");
  const config: AppConfig = await response.json();
  if (config.oauth_provider === "cognito") {
    const auth = new CognitoAuth(config);
    await auth.completeLogin();
    return { auth, config };
  }
  const auth = new Keycloak({
    url: config.oauth_url!,
    realm: config.realm!,
    clientId: config.client_id,
  });
  await auth.init({
    onLoad: "check-sso",
    pkceMethod: "S256",
    checkLoginIframe: false,
    responseMode: "query",
  });
  return { auth, config };
}

function randomValue(length: number) {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}
