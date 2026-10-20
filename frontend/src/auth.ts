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
  user_pool_id?: string;
  aws_region?: string;
}

export interface AuthClient {
  authenticated?: boolean;
  token?: string;
  onAuthLogout?: (() => void) | undefined;
  clearRemoteSession?(): void;
  updateToken(minValidity: number): Promise<boolean>;
  clearToken(): void;
  login(options?: { redirectUri?: string }): void | Promise<void>;
  logout(options?: { redirectUri?: string }): void | Promise<void>;
  signUp?(email: string, password: string): Promise<void>;
  confirmSignUp?(email: string, code: string): Promise<void>;
  resendSignUpCode?(email: string): Promise<void>;
  signIn?(email: string, password: string): Promise<void>;
  forgotPassword?(email: string): Promise<void>;
  confirmForgotPassword?(
    email: string,
    code: string,
    password: string,
  ): Promise<void>;
}

class CognitoAuth implements AuthClient {
  authenticated = false;
  token?: string;
  onAuthLogout?: () => void;
  private readonly pendingUsernames = new Map<string, string>();

  constructor(private config: AppConfig) {}

  async updateToken(minValidity: number) {
    if (this.token && this.expiresAt - Date.now() > minValidity * 1000)
      return false;
    try {
      const result = await this.sessionRequest("/api/v1/auth/refresh");
      this.setAccessToken(result.access_token, result.expires_in);
      return true;
    } catch (error) {
      this.clearToken();
      if (error instanceof Error && error.message === "SESSION_EXPIRED") {
        throw new Error("La sesión ha caducado. Vuelve a iniciar sesión.", {
          cause: error,
        });
      }
      throw error;
    }
  }

  clearToken() {
    this.token = undefined;
    this.authenticated = false;
    this.onAuthLogout?.();
  }

  login() {
    throw new Error("Introduce el correo y la contraseña en esta pantalla.");
  }

  async signUp(email: string, password: string) {
    const username = `family-${crypto.randomUUID()}`;
    await this.call("SignUp", {
      ClientId: this.config.client_id,
      // Cognito rejects email-shaped usernames when email is configured as an alias.
      Username: username,
      Password: password,
      UserAttributes: [{ Name: "email", Value: email }],
    });
    this.pendingUsernames.set(email.trim().toLowerCase(), username);
  }

  async confirmSignUp(email: string, code: string) {
    await this.call("ConfirmSignUp", {
      ClientId: this.config.client_id,
      Username: this.pendingUsername(email),
      ConfirmationCode: code,
    });
    this.pendingUsernames.delete(email.trim().toLowerCase());
  }

  async resendSignUpCode(email: string) {
    await this.call("ResendConfirmationCode", {
      ClientId: this.config.client_id,
      Username: this.pendingUsername(email),
    });
  }

  private pendingUsername(email: string) {
    return (
      this.pendingUsernames.get(email.trim().toLowerCase()) ?? email.trim()
    );
  }

  async signIn(email: string, password: string) {
    const result = await this.call("InitiateAuth", {
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: this.config.client_id,
      AuthParameters: { USERNAME: email, PASSWORD: password },
    });
    if (!result.AuthenticationResult?.AccessToken) {
      throw new Error("No se pudo completar el inicio de sesión.");
    }
    const refreshToken = result.AuthenticationResult.RefreshToken;
    if (!refreshToken)
      throw new Error("No se pudo establecer una sesión duradera.");
    const session = await this.sessionRequest("/api/v1/auth/session", {
      refresh_token: refreshToken,
    });
    this.setAccessToken(session.access_token, session.expires_in);
  }

  async forgotPassword(email: string) {
    await this.call("ForgotPassword", {
      ClientId: this.config.client_id,
      Username: email,
    });
  }

  async confirmForgotPassword(email: string, code: string, password: string) {
    await this.call("ConfirmForgotPassword", {
      ClientId: this.config.client_id,
      Username: email,
      ConfirmationCode: code,
      Password: password,
    });
  }

  async logout() {
    const response = await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("No se pudo cerrar la sesión.");
    this.clearToken();
  }

  clearRemoteSession() {
    void this.logout().catch(() => this.clearToken());
  }

  private expiresAt = 0;

  private async call(target: string, body: object) {
    const response = await fetch(
      `https://cognito-idp.${this.config.aws_region}.amazonaws.com/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-amz-json-1.1",
          "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
        },
        body: JSON.stringify(body),
      },
    );
    const result = await response.json();
    if (!response.ok) {
      const type =
        String(result.__type ?? "")
          .split("#")
          .at(-1) ?? "";
      const messages: Record<string, string> = {
        UsernameExistsException: "Ya existe una cuenta con este correo.",
        AliasExistsException:
          "Ya existe una cuenta con este correo. Inicia sesión o recupera la contraseña.",
        UserNotConfirmedException:
          "Confirma tu correo con el código que te enviamos.",
        CodeMismatchException:
          "El código no es correcto. Usa el código más reciente.",
        ExpiredCodeException:
          "El código ha caducado. Pulsa «Enviar un código nuevo».",
        NotAuthorizedException: "Correo o contraseña incorrectos.",
        InvalidPasswordException:
          "La contraseña no cumple los requisitos de seguridad.",
        LimitExceededException:
          "Se han hecho demasiados intentos. Prueba más tarde.",
      };
      throw new Error(messages[type] ?? "No se pudo completar la solicitud.");
    }
    return result;
  }

  private async sessionRequest(
    path: string,
    body?: { refresh_token: string },
  ): Promise<{ access_token: string; expires_in: number }> {
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (response.status === 401) throw new Error("SESSION_EXPIRED");
    if (!response.ok) throw new Error("No se pudo recuperar la sesión.");
    return response.json();
  }

  async restoreSession() {
    try {
      const result = await this.sessionRequest("/api/v1/auth/refresh");
      this.setAccessToken(result.access_token, result.expires_in);
    } catch {
      this.clearToken();
    }
  }

  private setAccessToken(accessToken: string, expiresIn: number) {
    this.token = accessToken;
    this.expiresAt = Date.now() + expiresIn * 1000;
    this.authenticated = true;
  }
}

export async function initializeAuth(): Promise<{
  auth: AuthClient;
  config: AppConfig;
}> {
  const response = await fetch("/api/v1/config");
  if (!response.ok) throw new Error("No se puede conectar con la aplicación.");
  const config: AppConfig = await response.json();
  if (config.oauth_provider === "cognito") {
    const auth = new CognitoAuth(config);
    await auth.restoreSession();
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
