import Keycloak from "keycloak-js";

export interface AppConfig {
  timezone: string;
  oauth_url: string;
  realm: string;
  client_id: string;
}

export async function initializeAuth() {
  const response = await fetch("/api/v1/config");
  if (!response.ok) throw new Error("No se puede conectar con la aplicación.");
  const config: AppConfig = await response.json();
  const auth = new Keycloak({
    url: config.oauth_url,
    realm: config.realm,
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
