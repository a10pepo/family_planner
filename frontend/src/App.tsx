import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import FullCalendar from "@fullcalendar/react";
import timeGrid from "@fullcalendar/timegrid";
import interaction from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import es from "@fullcalendar/core/locales/es";
import type { EventDropArg } from "@fullcalendar/core";
import type { EventResizeDoneArg } from "@fullcalendar/interaction";
import type Keycloak from "keycloak-js";
import { DateTime } from "luxon";
import { Api, type CalendarEvent, type Member } from "./api";
import type { AppConfig } from "./auth";
import { fromLocalInput, localInput } from "./dates";
import { Avatar, Icon } from "./visuals";
import { categories, type Category } from "./categories";

const colors = [
  "#dcebe2",
  "#dce6f3",
  "#f4e7cf",
  "#eadff0",
  "#f5dfe3",
  "#dceeee",
];
const message = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar el cambio.";

function Dialog({
  title,
  close,
  busy,
  children,
}: {
  title: string;
  close: () => void;
  busy: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) close();
      }}
      aria-labelledby="dialog-title"
    >
      <div className="dialog-heading">
        <h2 id="dialog-title">{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Cerrar"
          disabled={busy}
          onClick={close}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}

function MemberForm({
  api,
  initialColor,
  close,
  saved,
}: {
  api: Api;
  initialColor: string;
  close: () => void;
  saved: (member: Member) => void;
}) {
  const [name, setName] = useState("");
  const [color, setColor] = useState(initialColor);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      saved(await api.addMember(name.trim(), color));
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Añadir integrante" close={close} busy={busy}>
      <form onSubmit={submit}>
        <p className="muted">
          Un color y un nombre para encontrar su día de un vistazo.
        </p>
        <label>
          Nombre
          <input
            autoFocus
            required
            maxLength={80}
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={busy}
          />
        </label>
        <fieldset disabled={busy}>
          <legend>Color del integrante</legend>
          <div className="color-options">
            {colors.map((value, index) => (
              <label
                key={value}
                className="color-choice"
                style={{ background: value }}
              >
                <input
                  type="radio"
                  name="color"
                  value={value}
                  checked={color === value}
                  onChange={() => setColor(value)}
                  aria-label={`Color ${index + 1}`}
                />
                <span aria-hidden="true">{color === value ? "✓" : ""}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            Cancelar
          </button>
          <button disabled={busy || !name.trim()}>
            {busy ? "Guardando…" : "Guardar integrante"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

interface Editor {
  event?: CalendarEvent;
  memberId?: string;
  start: string;
  end: string;
}

function EventForm({
  api,
  members,
  selected,
  zone,
  editor,
  close,
  saved,
}: {
  api: Api;
  members: Member[];
  selected: string | null;
  zone: string;
  editor: Editor;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState(editor.event?.title ?? "");
  const [category, setCategory] = useState<Category>(
    editor.event?.category ?? "other",
  );
  const [memberId, setMemberId] = useState(
    editor.event?.member_id ??
      editor.memberId ??
      selected ??
      members[0]?.id ??
      "",
  );
  const [start, setStart] = useState(localInput(editor.start, zone));
  const [end, setEnd] = useState(localInput(editor.end, zone));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const starts_at = fromLocalInput(start, zone),
        ends_at = fromLocalInput(end, zone);
      if (Date.parse(ends_at) <= Date.parse(starts_at))
        throw new Error("El final debe ser posterior al inicio.");
      const data = { title: title.trim(), starts_at, ends_at, category };
      if (editor.event) await api.updateEvent(editor.event.id, data);
      else await api.addEvent({ ...data, member_id: memberId });
      saved();
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!editor.event) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteEvent(editor.event.id);
      saved();
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={editor.event ? "Editar evento" : "Nuevo evento"}
      close={close}
      busy={busy}
    >
      <form onSubmit={submit}>
        <label>
          Título
          <input
            autoFocus
            required
            maxLength={200}
            value={title}
            disabled={busy}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label>
          Integrante
          <select
            aria-label="Integrante"
            value={memberId}
            disabled={busy || !!editor.event}
            onChange={(event) => setMemberId(event.target.value)}
            required
          >
            {members.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Categoría
          <select
            aria-label="Categoría"
            value={category}
            disabled={busy}
            onChange={(event) => setCategory(event.target.value as Category)}
          >
            {Object.entries(categories).map(([value, details]) => (
              <option key={value} value={value}>
                {details.label}
              </option>
            ))}
          </select>
        </label>
        <div className="date-fields">
          <label>
            Inicio
            <input
              type="datetime-local"
              required
              value={start}
              disabled={busy}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label>
            Fin
            <input
              type="datetime-local"
              required
              value={end}
              disabled={busy}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
        </div>
        <p className="muted small">Hora de la familia · {zone}</p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {confirmDelete && (
          <div className="delete-confirm">
            <p>¿Eliminar este evento del calendario?</p>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={remove}
            >
              Confirmar eliminación
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setConfirmDelete(false)}
            >
              Conservar evento
            </button>
          </div>
        )}
        <div className="form-actions">
          {editor.event && !confirmDelete && (
            <button
              type="button"
              className="delete-button"
              disabled={busy}
              onClick={() => setConfirmDelete(true)}
            >
              Eliminar evento
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
          <button disabled={busy || !title.trim() || !memberId}>
            {busy ? "Guardando…" : "Guardar evento"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export default function App({
  auth,
  config,
}: {
  auth: Keycloak;
  config: AppConfig;
}) {
  const [authenticated, setAuthenticated] = useState(!!auth.authenticated);
  const api = useMemo(() => new Api(auth), [auth]);
  const [members, setMembers] = useState<Member[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [day, setDay] = useState(() =>
    DateTime.now().setZone(config.timezone).toISODate()!,
  );
  const date = useMemo(
    () => DateTime.fromISO(day, { zone: config.timezone }),
    [day, config.timezone],
  );
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [moving, setMoving] = useState(false);
  const [memberForm, setMemberForm] = useState(false);
  const [editor, setEditor] = useState<Editor | null>(null);
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
    auth.onAuthLogout = () => setAuthenticated(false);
    return () => {
      auth.onAuthLogout = undefined;
    };
  }, [auth]);

  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    api
      .members()
      .then((data) => {
        if (active) {
          setMembers(data);
          setLoading(false);
        }
      })
      .catch((error) => {
        if (active) {
          setError(message(error));
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [api, authenticated, refresh]);

  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    api
      .events(
        date.startOf("day").toISO()!,
        date.plus({ days: 1 }).startOf("day").toISO()!,
        null,
      )
      .then((data) => {
        if (active) {
          setEvents(data);
          setError("");
        }
      })
      .catch((error) => {
        if (active) setError(message(error));
      });
    return () => {
      active = false;
    };
  }, [api, authenticated, date, refresh]);

  useEffect(() => {
    if (viewport.current) viewport.current.scrollTop = 7 * 56;
  }, [loading, authenticated, day]);

  function addEvent(memberId: string, start?: string, end?: string) {
    const defaultStart = date.set({ hour: 9 });
    setEditor({
      memberId,
      start: start ?? defaultStart.toISO()!,
      end: end ?? defaultStart.plus({ hours: 1 }).toISO()!,
    });
  }

  async function move(info: EventDropArg | EventResizeDoneArg) {
    if (!info.event.start || !info.event.end) {
      info.revert();
      return;
    }
    setMoving(true);
    setError("");
    try {
      await api.updateEvent(info.event.id, {
        title: info.event.title,
        category: info.event.extendedProps.category as Category,
        starts_at: info.event.start.toISOString(),
        ends_at: info.event.end.toISOString(),
      });
      setRefresh((value) => value + 1);
    } catch (error) {
      info.revert();
      setError(message(error));
    } finally {
      setMoving(false);
    }
  }

  if (!authenticated)
    return (
      <main className="welcome">
        <div className="brand-mark">
          <Icon name="calendar" />
        </div>
        <p className="eyebrow">FAMILY PLANNER</p>
        <h1>
          Un lugar para
          <br />
          vuestros planes.
        </h1>
        <p>El calendario de toda la familia, siempre a mano.</p>
        <button
          onClick={() =>
            auth.login({ redirectUri: `${window.location.origin}/` })
          }
        >
          Entrar al calendario <span aria-hidden="true">→</span>
        </button>
        <p className="small muted">Accede con la cuenta familiar.</p>
      </main>
    );

  const gridStyle = {
    gridTemplateColumns: `56px repeat(${Math.max(members.length, 1)}, minmax(180px, 1fr))`,
  };
  return (
    <div className="app-layout">
      <aside className="sidebar" aria-label="Menú principal">
        <a
          href="/"
          className="brand-mark"
          aria-label="Family Planner"
          title="Family Planner"
        >
          <Icon name="calendar" />
        </a>
        <nav className="sidebar-main">
          <button
            className="rail-button active"
            aria-label="Calendario"
            aria-current="page"
            title="Calendario"
            onClick={() =>
              setDay(DateTime.now().setZone(config.timezone).toISODate()!)
            }
          >
            <Icon name="calendar" />
          </button>
          <button
            className="rail-button"
            aria-label="Añadir integrante"
            title="Añadir integrante"
            onClick={() => setMemberForm(true)}
          >
            <Icon name="people" />
          </button>
        </nav>
        <button
          className="rail-button sidebar-bottom"
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
          onClick={() =>
            auth.logout({ redirectUri: `${window.location.origin}/` })
          }
        >
          <Icon name="logout" />
        </button>
      </aside>
      <main className="workspace">
        <section
          className="calendar-panel"
          aria-label="Calendario diario por familiar"
        >
          <header className="calendar-toolbar">
            <div className="calendar-period">
              <span className="month-label">
                {date.setLocale("es").toFormat("LLLL yyyy")}
              </span>
              <h1>{date.setLocale("es").toFormat("cccc, d 'de' LLLL")}</h1>
            </div>
            <div className="calendar-controls">
              <button
                className="secondary"
                onClick={() =>
                  setDay(DateTime.now().setZone(config.timezone).toISODate()!)
                }
              >
                Hoy
              </button>
              <div className="arrows">
                <button
                  className="icon-button"
                  aria-label="Día anterior"
                  onClick={() => setDay(date.minus({ days: 1 }).toISODate()!)}
                >
                  ‹
                </button>
                <button
                  className="icon-button"
                  aria-label="Día siguiente"
                  onClick={() => setDay(date.plus({ days: 1 }).toISODate()!)}
                >
                  ›
                </button>
              </div>
              <span className="view-badge">
                <Icon name="calendar" /> Día
              </span>
            </div>
          </header>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button
                className="secondary"
                onClick={() => setRefresh((value) => value + 1)}
              >
                Reintentar
              </button>
            </div>
          )}
          {loading && (
            <p className="empty-note" role="status">
              Cargando calendario…
            </p>
          )}
          {!loading && !members.length && (
            <div className="empty-note">
              <span>Añade un integrante para empezar a planificar.</span>
              <button className="secondary" onClick={() => setMemberForm(true)}>
                Añadir integrante
              </button>
            </div>
          )}
          {!!members.length && (
            <div className="day-viewport" ref={viewport}>
              <div
                className="day-surface"
                style={{ minWidth: 56 + members.length * 180 }}
              >
                <div className="family-headings" style={gridStyle}>
                  <div className="time-heading" aria-hidden="true">
                    <span>24 h</span>
                  </div>
                  {members.map((member) => {
                    const [name, nickname] = member.name.split(/\s*[()]\s*/);
                    return (
                      <div className="person-heading" key={member.id}>
                        <Avatar name={member.name} color={member.color} />
                        <span className="person-name">{name}</span>
                        {nickname && (
                          <span className="person-nickname">{nickname}</span>
                        )}
                        <button
                          className="column-add"
                          aria-label={`Añadir evento para ${name}`}
                          title={`Añadir evento para ${name}`}
                          onClick={() => addEvent(member.id)}
                        >
                          ＋
                        </button>
                      </div>
                    );
                  })}
                </div>
                <div className="day-columns" style={gridStyle}>
                  <div className="time-scale" aria-hidden="true">
                    {Array.from({ length: 24 }, (_, hour) => (
                      <div className="hour-label" key={hour}>
                        <span>{`${String(hour).padStart(2, "0")}:00`}</span>
                      </div>
                    ))}
                  </div>
                  {members.map((member) => (
                    <div
                      className="member-calendar"
                      key={`${member.id}-${day}`}
                      aria-label={`Calendario de ${member.name}`}
                      data-member={member.name}
                    >
                      <FullCalendar
                        plugins={[timeGrid, interaction, luxonPlugin]}
                        locale={es}
                        timeZone={config.timezone}
                        initialDate={day}
                        initialView="timeGridDay"
                        headerToolbar={false}
                        dayHeaders={false}
                        allDaySlot={false}
                        nowIndicator
                        height="auto"
                        slotMinTime="00:00:00"
                        slotMaxTime="24:00:00"
                        slotDuration="00:30:00"
                        slotLabelContent={() => ""}
                        editable={!moving && !editor}
                        selectable
                        selectMirror
                        longPressDelay={350}
                        eventMinHeight={44}
                        eventTimeFormat={{
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false,
                        }}
                        events={events
                          .filter((event) => event.member_id === member.id)
                          .map((event) => ({
                            id: event.id,
                            title: event.title,
                            start: event.starts_at,
                            end: event.ends_at,
                            backgroundColor: categories[event.category].color,
                            textColor: categories[event.category].ink,
                            extendedProps: { category: event.category },
                            borderColor: categories[event.category].color,
                          }))}
                        dateClick={(info) =>
                          addEvent(
                            member.id,
                            info.dateStr,
                            DateTime.fromISO(info.dateStr)
                              .plus({ hours: 1 })
                              .toISO()!,
                          )
                        }
                        select={(info) => {
                          addEvent(member.id, info.startStr, info.endStr);
                          info.view.calendar.unselect();
                        }}
                        eventDrop={move}
                        eventResize={move}
                        eventClick={(info) => {
                          const event = events.find(
                            (event) => event.id === info.event.id,
                          );
                          if (event)
                            setEditor({
                              event,
                              start: event.starts_at,
                              end: event.ends_at,
                            });
                        }}
                        eventContent={(info) => (
                          <div className="event-content">
                            <span className="event-time">{info.timeText}</span>
                            <strong>{info.event.title}</strong>
                            <span className="event-category">
                              <Icon
                                name={
                                  categories[
                                    (info.event.extendedProps.category ??
                                      "other") as Category
                                  ].icon
                                }
                              />
                              {
                                categories[
                                  (info.event.extendedProps.category ??
                                    "other") as Category
                                ].label
                              }
                            </span>
                          </div>
                        )}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          <div className="category-legend" aria-label="Categorías de eventos">
            {Object.entries(categories).map(([value, details]) => (
              <span className="category-key" key={value}>
                <span
                  className="category-swatch"
                  style={{ background: details.color, color: details.ink }}
                >
                  <Icon name={details.icon} />
                </span>
                {details.label}
              </span>
            ))}
          </div>
          <footer className="calendar-footer">
            <span role="status">
              <span className="status-dot" />
              {moving
                ? "Guardando movimiento…"
                : `${events.length} ${events.length === 1 ? "plan" : "planes"} para hoy`}
            </span>
            <span>Toca una hora para añadir un plan · {config.timezone}</span>
          </footer>
        </section>
      </main>
      {memberForm && (
        <MemberForm
          api={api}
          initialColor={
            colors.find(
              (color) => !members.some((member) => member.color === color),
            ) ?? colors[members.length % colors.length]
          }
          close={() => setMemberForm(false)}
          saved={(member) => {
            setMembers((previous) => [...previous, member]);
            setMemberForm(false);
          }}
        />
      )}
      {editor && (
        <EventForm
          api={api}
          members={members}
          selected={null}
          zone={config.timezone}
          editor={editor}
          close={() => setEditor(null)}
          saved={() => {
            setEditor(null);
            setRefresh((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}
