import type Keycloak from "keycloak-js";
import type { components } from "./api-schema";

export type Member = components["schemas"]["MemberOutput"];
export type CalendarEvent = components["schemas"]["EventOutput"];
export type EventInput = components["schemas"]["EventInput"];
export type EventUpdate = components["schemas"]["EventUpdate"];

export class Api {
  constructor(private auth: Keycloak) {}

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    try {
      await this.auth.updateToken(30);
    } catch {
      this.auth.clearToken();
      throw new Error("La sesión ha caducado. Vuelve a iniciar sesión.");
    }
    const response = await fetch(`/api/v1${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.auth.token}`,
        ...init.headers,
      },
    });
    if (response.status === 401) this.auth.clearToken();
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : "No se pudo guardar el cambio. Comprueba los datos e inténtalo otra vez.",
      );
    }
    return response.status === 204 ? (undefined as T) : response.json();
  }

  members() {
    return this.request<Member[]>("/members");
  }
  addMember(name: string, color: string) {
    return this.request<Member>("/members", {
      method: "POST",
      body: JSON.stringify({ name, color }),
    });
  }
  events(start: string, end: string, memberId: string | null) {
    const query = new URLSearchParams({ start, end });
    if (memberId) query.set("member_id", memberId);
    return this.request<CalendarEvent[]>(`/events?${query}`);
  }
  addEvent(data: EventInput) {
    return this.request<CalendarEvent>("/events", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
  updateEvent(id: string, data: EventUpdate) {
    return this.request<CalendarEvent>(`/events/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
  deleteEvent(id: string) {
    return this.request<void>(`/events/${id}`, { method: "DELETE" });
  }
}
