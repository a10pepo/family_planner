import { useState, type FormEvent } from "react";
import { Api, type FamilyEvent } from "../api";
import { Dialog } from "./Dialog";
import { IconPicker, CustomSymbol } from "./IconCatalog";
import type { IconName } from "../visuals";

export const familyIcons: Record<
  FamilyEvent["icon"],
  { label: string; icon: IconName }
> = {
  birthday: { label: "Cumpleaños", icon: "birthday" },
  celebration: { label: "Celebración", icon: "friends" },
  trip: { label: "Excursión familiar", icon: "trip" },
  other: { label: "Otro evento familiar", icon: "other" },
};

export function FamilyEvents({
  events,
  add,
  edit,
}: {
  events: FamilyEvent[];
  add: () => void;
  edit: (event: FamilyEvent) => void;
}) {
  return (
    <div
      className="family-event-strip"
      role="group"
      aria-label="Eventos familiares de todo el día"
    >
      {events.map((event) => (
        <button
          className="family-event-token"
          key={event.id}
          title={`${event.title} · Todo el día`}
          aria-label={`Editar evento familiar ${event.title}`}
          onClick={() => edit(event)}
        >
          <CustomSymbol
            id={event.custom_icon_id}
            fallback={familyIcons[event.icon].icon}
          />
          <span>{event.title}</span>
        </button>
      ))}
      <button
        className="daily-add"
        aria-label="Añadir evento familiar de todo el día"
        title="Añadir evento familiar de todo el día"
        onClick={add}
      >
        ＋
      </button>
    </div>
  );
}

export function FamilyEventForm({
  api,
  day,
  event,
  close,
  saved,
}: {
  api: Api;
  day: string;
  event?: FamilyEvent;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState(event?.title ?? "");
  const [date, setDate] = useState(event?.day ?? day);
  const [icon, setIcon] = useState<FamilyEvent["icon"]>(
    event?.icon ?? "birthday",
  );
  const [custom, setCustom] = useState<string | null>(
    event?.custom_icon_id ?? null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = {
        title: title.trim(),
        day: date,
        icon,
        custom_icon_id: custom,
      };
      if (event) await api.updateFamilyEvent(event.id, data);
      else await api.addFamilyEvent(data);
      saved();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No se pudo guardar el evento familiar.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!event) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteFamilyEvent(event.id);
      saved();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No se pudo eliminar el evento familiar.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={event ? "Editar evento familiar" : "Nuevo evento familiar"}
      close={close}
      busy={busy}
    >
      <form onSubmit={submit}>
        <p className="muted">Para toda la familia · Todo el día</p>
        <label>
          Título del evento familiar
          <input
            autoFocus
            required
            maxLength={80}
            value={title}
            disabled={busy}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Fecha del evento familiar
          <input
            type="date"
            required
            value={date}
            disabled={busy}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <fieldset disabled={busy}>
          <legend>Icono del evento familiar</legend>
          <IconPicker
            options={familyIcons}
            builtin={icon}
            selected={custom}
            busy={busy}
            setBusy={setBusy}
            onChange={(value, image) => {
              setIcon(value as FamilyEvent["icon"]);
              setCustom(image);
            }}
          />
        </fieldset>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {confirm && (
          <div className="delete-confirm">
            <p>¿Eliminar este evento familiar?</p>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={remove}
            >
              Confirmar eliminación del evento familiar
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Conservar evento familiar
            </button>
          </div>
        )}
        <div className="form-actions">
          {event && !confirm && (
            <button
              type="button"
              className="delete-button"
              disabled={busy}
              onClick={() => setConfirm(true)}
            >
              Eliminar evento familiar
            </button>
          )}
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            Cancelar
          </button>
          <button disabled={busy || !title.trim() || !date}>
            {busy ? "Guardando…" : "Guardar evento familiar"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
