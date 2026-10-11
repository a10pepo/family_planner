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
  private refreshToken?: string;

  constructor(private config: AppConfig) {}

  async updateToken(minValidity: number) {
    if (this.token && this.expiresAt - Date.now() > minValidity * 1000)
      return false;
    if (!this.refreshToken) {
      this.clearToken();
      return false;
    }
    try {
      const result = await this.call("InitiateAuth", {
        AuthFlow: "REFRESH_TOKEN_AUTH",
        ClientId: this.config.client_id,
        AuthParameters: { REFRESH_TOKEN: this.refreshToken },
      });
      this.setTokens(result.AuthenticationResult);
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

  login() {
    throw new Error("Introduce el correo y la contraseña en esta pantalla.");
  }

  async signUp(email: string, password: string) {
    await this.call("SignUp", {
      ClientId: this.config.client_id,
      // Cognito rejects email-shaped usernames when email is configured as an alias.
      // Users still sign in and confirm with the email alias.
      Username: `family-${crypto.randomUUID()}`,
      Password: password,
      UserAttributes: [{ Name: "email", Value: email }],
    });
  }

  async confirmSignUp(email: string, code: string) {
    await this.call("ConfirmSignUp", {
      ClientId: this.config.client_id,
      Username: email,
      ConfirmationCode: code,
    });
  }

  async resendSignUpCode(email: string) {
    await this.call("ResendConfirmationCode", {
      ClientId: this.config.client_id,
      Username: email,
    });
  }

  async signIn(email: string, password: string) {
    const result = await this.call("InitiateAuth", {
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: this.config.client_id,
      AuthParameters: { USERNAME: email, PASSWORD: password },
    });
    if (!result.AuthenticationResult) {
      throw new Error("No se pudo completar el inicio de sesión.");
    }
    this.setTokens(result.AuthenticationResult);
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

  logout() {
    this.clearToken();
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

  private setTokens(tokens: {
    AccessToken: string;
    RefreshToken?: string;
    ExpiresIn: number;
  }) {
    this.token = tokens.AccessToken;
    this.refreshToken = tokens.RefreshToken ?? this.refreshToken;
    this.expiresAt = Date.now() + tokens.ExpiresIn * 1000;
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
