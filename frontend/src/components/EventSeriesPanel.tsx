import { useEffect, useState, type FormEvent } from "react";
import { DateTime } from "luxon";
import {
  Api,
  type CalendarEvent,
  type EventSeries,
  type EventSeriesInput,
  type Member,
} from "../api";
import { categories, type Category } from "../categories";
import { IconPicker } from "./IconCatalog";
import { Dialog } from "./Dialog";
import { localInput } from "../dates";

const weekdays = ["L", "M", "X", "J", "V", "S", "D"];
const displayDays = (values: number[]) =>
  values.map((day) => weekdays[day]).join(", ");
const timeAfter = (start: string, duration: number) => {
  const [hours, minutes] = start.split(":").map(Number);
  const total = (hours * 60 + minutes + duration) % (24 * 60);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
};

export function EventOccurrenceForm({
  api,
  event,
  zone,
  close,
  saved,
}: {
  api: Api;
  event: CalendarEvent;
  zone: string;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState(event.title);
  const [start, setStart] = useState(
    localInput(event.starts_at, zone).slice(11),
  );
  const [end, setEnd] = useState(localInput(event.ends_at, zone).slice(11));
  const [category, setCategory] = useState<Category>(event.category);
  const [iconId, setIconId] = useState<string | null>(
    event.custom_icon_id ?? null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(cancelled: boolean) {
    if (
      !event.recurring_series_id ||
      !event.occurrence_date ||
      !event.occurrence_time
    )
      return;
    if (
      cancelled &&
      !window.confirm(
        `¿Cancelar solo «${event.title}» del ${event.occurrence_date}?`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      let duration = 60;
      if (!cancelled) {
        const startDateTime = DateTime.fromFormat(start, "HH:mm", {
          zone: "utc",
        });
        let endDateTime = DateTime.fromFormat(end, "HH:mm", { zone: "utc" });
        if (endDateTime <= startDateTime)
          endDateTime = endDateTime.plus({ days: 1 });
        duration = endDateTime.diff(startDateTime, "minutes").minutes;
        if (!Number.isFinite(duration) || duration < 1)
          throw new Error("La hora de fin debe ser posterior al inicio.");
      }
      await api.saveEventException(event.recurring_series_id, {
        occurrence_date: event.occurrence_date,
        occurrence_time: event.occurrence_time,
        cancelled,
        has_icon_override: !cancelled,
        ...(cancelled
          ? {}
          : {
              override_start_time: `${start}:00`,
              override_duration_minutes: duration,
              override_title: title.trim(),
              override_category: category,
              override_custom_icon_id: iconId,
            }),
      });
      saved();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo guardar la excepción.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Editar esta ocurrencia" close={close} busy={busy}>
      <form
        className="series-form"
        onSubmit={(formEvent) => {
          formEvent.preventDefault();
          void save(false);
        }}
      >
        <p className="muted">
          Los cambios se aplican solo al {event.occurrence_date}; el resto de la
          repetición permanece igual.
        </p>
        <label>
          Título
          <input
            required
            maxLength={200}
            value={title}
            onChange={(input) => setTitle(input.target.value)}
            disabled={busy}
          />
        </label>
        <div className="date-fields">
          <label>
            Hora de inicio
            <input
              type="time"
              value={start}
              onChange={(input) => setStart(input.target.value)}
              disabled={busy}
              required
            />
          </label>
          <label>
            Hora de fin
            <input
              type="time"
              value={end}
              onChange={(input) => setEnd(input.target.value)}
              disabled={busy}
              required
            />
          </label>
        </div>
        <label>
          Categoría
          <select
            value={category}
            onChange={(input) => setCategory(input.target.value as Category)}
            disabled={busy}
          >
            {Object.entries(categories).map(([value, details]) => (
              <option key={value} value={value}>
                {details.label}
              </option>
            ))}
          </select>
        </label>
        <fieldset disabled={busy}>
          <legend>Icono</legend>
          <IconPicker
            options={categories}
            builtin={category}
            selected={iconId}
            busy={busy}
            setBusy={setBusy}
            allowUpload={false}
            onChange={(value, icon) => {
              setCategory(value as Category);
              setIconId(icon);
            }}
          />
        </fieldset>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="delete-button"
            disabled={busy}
            onClick={() => void save(true)}
          >
            Cancelar solo esta ocurrencia
          </button>
          <button
            type="button"
            className="secondary"
            onClick={close}
            disabled={busy}
          >
            Cerrar
          </button>
          <button disabled={busy || !title.trim()}>
            {busy ? "Guardando…" : "Guardar ocurrencia"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function SeriesForm({
  api,
  members,
  zone,
  initial,
  close,
  saved,
}: {
  api: Api;
  members: Member[];
  zone: string;
  initial?: EventSeries;
  close: () => void;
  saved: () => void;
}) {
  const today = DateTime.now().setZone(zone);
  const [title, setTitle] = useState(initial?.title ?? "");
  const [memberId, setMemberId] = useState(
    initial?.member_id ?? members[0]?.id ?? "",
  );
  const [startDate, setStartDate] = useState(
    initial?.start_date ?? today.toISODate()!,
  );
  const [startTime, setStartTime] = useState(
    initial?.start_time.slice(0, 5) ?? "09:00",
  );
  const [endTime, setEndTime] = useState(() => {
    if (!initial) return "10:00";
    return timeAfter(initial.start_time, initial.duration_minutes);
  });
  const [frequency, setFrequency] = useState<EventSeriesInput["frequency"]>(
    initial?.frequency ?? "weekly",
  );
  const [interval, setInterval] = useState(initial?.interval ?? 1);
  const [selectedDays, setSelectedDays] = useState<number[]>(
    initial?.weekdays ?? [today.weekday - 1],
  );
  const [endMode, setEndMode] = useState<EventSeriesInput["end_mode"]>(
    initial?.end_mode ?? "never",
  );
  const [endDate, setEndDate] = useState(
    initial?.end_date ?? today.plus({ months: 1 }).toISODate()!,
  );
  const [count, setCount] = useState(initial?.occurrence_count ?? 10);
  const [category, setCategory] = useState<Category>(
    initial?.category ?? "other",
  );
  const [iconId, setIconId] = useState<string | null>(
    initial?.custom_icon_id ?? null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const start = DateTime.fromFormat(startTime, "HH:mm");
      let end = DateTime.fromFormat(endTime, "HH:mm");
      if (!start.isValid || !end.isValid)
        throw new Error("Indica horas válidas.");
      if (end <= start) end = end.plus({ days: 1 });
      const data: EventSeriesInput = {
        member_id: memberId,
        title: title.trim(),
        start_date: startDate,
        start_time: `${startTime}:00`,
        duration_minutes: end.diff(start, "minutes").minutes,
        timezone: zone,
        frequency,
        interval,
        weekdays: frequency === "weekly" ? selectedDays : [],
        end_mode: endMode,
        end_date: endMode === "date" ? endDate : null,
        occurrence_count: endMode === "count" ? count : null,
        category,
        custom_icon_id: iconId,
      };
      if (!data.weekdays?.length && frequency === "weekly")
        throw new Error("Selecciona al menos un día de la semana.");
      if (initial) await api.updateEventSeries(initial.id, data);
      else await api.addEventSeries(data);
      saved();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo guardar la serie.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      title={initial ? "Editar repetición" : "Nuevo evento recurrente"}
      close={close}
      busy={busy}
    >
      <form onSubmit={submit} className="series-form">
        <label>
          Título
          <input
            required
            autoFocus
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={busy}
          />
        </label>
        <label>
          Integrante
          <select
            value={memberId}
            onChange={(event) => setMemberId(event.target.value)}
            disabled={busy}
            required
          >
            {members.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <div className="date-fields">
          <label>
            Empieza el
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              required
              disabled={busy}
            />
          </label>
          <label>
            Hora de inicio
            <input
              type="time"
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
              required
              disabled={busy}
            />
          </label>
          <label>
            Hora de fin
            <input
              type="time"
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
              required
              disabled={busy}
            />
          </label>
        </div>
        <fieldset disabled={busy}>
          <legend>Repetir</legend>
          <div className="series-repeat-row">
            <label>
              Frecuencia
              <select
                value={frequency}
                onChange={(event) =>
                  setFrequency(
                    event.target.value as EventSeriesInput["frequency"],
                  )
                }
              >
                <option value="daily">Diariamente</option>
                <option value="weekly">Semanalmente</option>
                <option value="monthly">Mensualmente</option>
              </select>
            </label>
            <label>
              Cada
              <input
                type="number"
                min={1}
                max={365}
                value={interval}
                onChange={(event) => setInterval(Number(event.target.value))}
              />
            </label>
            <span>
              {frequency === "daily"
                ? "día(s)"
                : frequency === "weekly"
                  ? "semana(s)"
                  : "mes(es)"}
            </span>
          </div>
          {frequency === "weekly" && (
            <div
              className="series-weekdays"
              role="group"
              aria-label="Días de la semana"
            >
              {weekdays.map((label, index) => (
                <button
                  key={index}
                  type="button"
                  className={selectedDays.includes(index) ? "selected" : ""}
                  aria-pressed={selectedDays.includes(index)}
                  onClick={() =>
                    setSelectedDays((previous) =>
                      previous.includes(index)
                        ? previous.filter((day) => day !== index)
                        : [...previous, index].sort(),
                    )
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          {frequency === "monthly" && (
            <p className="small muted">
              Se repetirá el mismo día del mes; los meses que no tengan ese día
              se omiten.
            </p>
          )}
        </fieldset>
        <fieldset disabled={busy}>
          <legend>Finaliza</legend>
          <div className="series-end-options">
            <label>
              <input
                type="radio"
                name="series-end"
                checked={endMode === "never"}
                onChange={() => setEndMode("never")}
              />{" "}
              Nunca
            </label>
            <label>
              <input
                type="radio"
                name="series-end"
                checked={endMode === "date"}
                onChange={() => setEndMode("date")}
              />{" "}
              El día
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                disabled={endMode !== "date"}
              />
            </label>
            <label>
              <input
                type="radio"
                name="series-end"
                checked={endMode === "count"}
                onChange={() => setEndMode("count")}
              />{" "}
              Después de
              <input
                type="number"
                min={1}
                max={10000}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                disabled={endMode !== "count"}
              />{" "}
              eventos
            </label>
          </div>
        </fieldset>
        <label>
          Categoría
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value as Category)}
            disabled={busy}
          >
            {Object.entries(categories).map(([value, details]) => (
              <option key={value} value={value}>
                {details.label}
              </option>
            ))}
          </select>
        </label>
        <fieldset disabled={busy}>
          <legend>Icono</legend>
          <IconPicker
            options={categories}
            builtin={category}
            selected={iconId}
            busy={busy}
            setBusy={setBusy}
            allowUpload={false}
            onChange={(value, icon) => {
              setCategory(value as Category);
              setIconId(icon);
            }}
          />
        </fieldset>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="secondary"
            onClick={close}
            disabled={busy}
          >
            Cancelar
          </button>
          <button disabled={busy || !title.trim() || !memberId}>
            {busy ? "Guardando…" : "Guardar repetición"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function EventSeriesPanel({
  api,
  members,
  zone,
  savedKey,
  saved,
}: {
  api: Api;
  members: Member[];
  zone: string;
  savedKey: number;
  saved: () => void;
}) {
  const [series, setSeries] = useState<EventSeries[]>([]);
  const [editing, setEditing] = useState<EventSeries | null | undefined>(
    undefined,
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api
      .eventSeries()
      .then((items) => {
        if (active) setSeries(items);
      })
      .catch((caught) => {
        if (active)
          setError(
            caught instanceof Error
              ? caught.message
              : "No se pudieron cargar las repeticiones.",
          );
      });
    return () => {
      active = false;
    };
  }, [api, savedKey]);
  async function remove(item: EventSeries) {
    if (
      !window.confirm(
        `¿Eliminar la repetición «${item.title}» y sus excepciones?`,
      )
    )
      return;
    setBusyId(item.id);
    try {
      await api.deleteEventSeries(item.id);
      saved();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No se pudo eliminar.",
      );
    } finally {
      setBusyId(null);
    }
  }
  return (
    <section className="series-panel" aria-label="Eventos recurrentes">
      <header className="series-panel-header">
        <div>
          <p className="eyebrow">CALENDARIO FAMILIAR</p>
          <h1>Eventos</h1>
          <p className="muted">
            Crea planes que se repiten y elige cuándo terminan.
          </p>
        </div>
        <button onClick={() => setEditing(null)}>＋ Nuevo evento</button>
      </header>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {!series.length ? (
        <div className="empty-note">Todavía no hay eventos recurrentes.</div>
      ) : (
        <div className="series-list">
          {series.map((item) => {
            const member = members.find(
              (person) => person.id === item.member_id,
            );
            const cadence =
              item.frequency === "daily"
                ? `Cada ${item.interval} día(s)`
                : item.frequency === "weekly"
                  ? `Cada ${item.interval} semana(s) · ${displayDays(item.weekdays ?? [])}`
                  : `Cada ${item.interval} mes(es), el día ${Number(item.start_date.slice(-2))}`;
            const ending =
              item.end_mode === "never"
                ? "Sin fecha final"
                : item.end_mode === "date"
                  ? `Hasta ${item.end_date}`
                  : `${item.occurrence_count} veces`;
            return (
              <article className="series-card" key={item.id}>
                <div>
                  <h2>{item.title}</h2>
                  <p>
                    {member?.name ?? "Integrante archivado"} · {cadence}
                  </p>
                  <p className="muted">
                    Desde {item.start_date}, {item.start_time.slice(0, 5)} ·{" "}
                    {ending}
                  </p>
                </div>
                <div className="series-actions">
                  <button
                    className="secondary"
                    onClick={() => setEditing(item)}
                  >
                    Editar
                  </button>
                  <button
                    className="delete-button"
                    disabled={busyId === item.id}
                    onClick={() => void remove(item)}
                  >
                    Eliminar
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {editing !== undefined && (
        <SeriesForm
          api={api}
          members={members}
          zone={zone}
          initial={editing ?? undefined}
          close={() => setEditing(undefined)}
          saved={() => {
            setEditing(undefined);
            saved();
          }}
        />
      )}
    </section>
  );
}
