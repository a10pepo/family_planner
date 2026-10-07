import type Keycloak from "keycloak-js";
import type { components } from "./api-schema";

export type CustomIcon = components["schemas"]["IconOutput"];
export type Member = components["schemas"]["MemberOutput"];
export type CalendarEvent = components["schemas"]["EventOutput"];
export type EventInput = components["schemas"]["EventInput"];
export type Notice = components["schemas"]["NoticeOutput"];
export type NoticeInput = components["schemas"]["NoticeInput"];
export type NoticeUpdate = components["schemas"]["NoticeUpdate"];
export type Task = components["schemas"]["TaskOutput"];
export type TaskInput = components["schemas"]["TaskInput"];
export type Occurrence = components["schemas"]["OccurrenceOutput"];
export type MemberUpdate = components["schemas"]["MemberUpdate"];
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

  icons() {
    return this.request<CustomIcon[]>("/icons");
  }
  addIcon(name: string, image_data: string) {
    return this.request<CustomIcon>("/icons", {
      method: "POST",
      body: JSON.stringify({ name, image_data }),
    });
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
  updateMember(id: string, data: MemberUpdate) {
    return this.request<Member>(`/members/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
  notices(day: string) {
    return this.request<Notice[]>(`/notices?day=${day}`);
  }
  addNotice(data: NoticeInput) {
    return this.request<Notice>("/notices", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
  updateNotice(id: string, data: NoticeUpdate) {
    return this.request<Notice>(`/notices/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
  deleteNotice(id: string) {
    return this.request<void>(`/notices/${id}`, { method: "DELETE" });
  }
  tasks() {
    return this.request<Task[]>("/tasks");
  }
  addTask(data: TaskInput) {
    return this.request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
  updateTask(id: string, data: TaskInput) {
    return this.request<Task>(`/tasks/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
  archiveTask(id: string) {
    return this.request<void>(`/tasks/${id}`, { method: "DELETE" });
  }
  occurrences(day: string) {
    return this.request<Occurrence[]>(`/task-occurrences?day=${day}`);
  }
  completeTask(occurrence: Occurrence, completed: boolean) {
    return this.request<Occurrence>(`/tasks/${occurrence.task_id}/completion`, {
      method: "PUT",
      body: JSON.stringify({
        member_id: occurrence.member_id,
        day: occurrence.day,
        completed,
      }),
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
