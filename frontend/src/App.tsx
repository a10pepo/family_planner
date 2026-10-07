import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import FullCalendar from "@fullcalendar/react";
import timeGrid from "@fullcalendar/timegrid";
import interaction from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import es from "@fullcalendar/core/locales/es";
import type { EventDropArg } from "@fullcalendar/core";
import type { EventResizeDoneArg } from "@fullcalendar/interaction";
import type Keycloak from "keycloak-js";
import { DateTime } from "luxon";
import {
  Api,
  type CalendarEvent,
  type CustomIcon,
  type Member,
  type Notice,
  type Task,
  type Occurrence,
} from "./api";
import type { AppConfig } from "./auth";
import { fromLocalInput, localInput } from "./dates";
import { Avatar, Icon } from "./visuals";
import { categories, type Category } from "./categories";
import { Dialog } from "./components/Dialog";
import {
  IconCatalog,
  IconPicker,
  CustomSymbol,
} from "./components/IconCatalog";
import { Profiles } from "./components/Profiles";
import { NoticeForm, TasksPanel } from "./components/DailyForms";
import { noticeIcons, taskIcons } from "./daily-icons";

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
  const [customIcon, setCustomIcon] = useState<string | null>(
    editor.event?.custom_icon_id ?? null,
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
      const data = {
        title: title.trim(),
        starts_at,
        ends_at,
        category,
        custom_icon_id: customIcon,
      };
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
        <fieldset disabled={busy}>
          <legend>Icono del evento</legend>
          <IconPicker
            options={categories}
            builtin={category}
            selected={customIcon}
            busy={busy}
            setBusy={setBusy}
            onChange={(value, custom) => {
              setCategory(value as Category);
              setCustomIcon(custom);
            }}
          />
        </fieldset>
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
  const [customIcons, setCustomIcons] = useState<CustomIcon[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [view, setView] = useState<"calendar" | "settings" | "tasks">(
    "calendar",
  );
  const [notices, setNotices] = useState<Notice[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [noticeEditor, setNoticeEditor] = useState<{
    memberId: string;
    notice?: Notice;
  } | null>(null);
  const [completing, setCompleting] = useState<string | null>(null);
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
    Promise.all([
      api.members(),
      api.tasks(),
      api.events(
        date.startOf("day").toISO()!,
        date.plus({ days: 1 }).startOf("day").toISO()!,
        null,
      ),
      api.notices(day),
      api.occurrences(day),
      api.icons(),
    ])
      .then(([people, routines, appointments, alerts, daily, icons]) => {
        if (active) {
          setCustomIcons(icons);
          setMembers(people);
          setTasks(routines);
          setEvents(appointments);
          setNotices(alerts);
          setOccurrences(daily);
          setLoading(false);
          setError("");
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
  }, [api, authenticated, date, day, refresh]);

  useEffect(() => {
    if (viewport.current) viewport.current.scrollTop = 7 * 56;
  }, [loading, authenticated, day, view]);

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

  async function complete(occurrence: Occurrence) {
    setCompleting(`${occurrence.task_id}-${occurrence.member_id}`);
    setError("");
    try {
      const updated = await api.completeTask(occurrence, !occurrence.completed);
      setOccurrences((previous) =>
        previous.map((item) =>
          item.task_id === updated.task_id &&
          item.member_id === updated.member_id &&
          item.day === updated.day
            ? updated
            : item,
        ),
      );
    } catch (error) {
      setError(message(error));
    } finally {
      setCompleting(null);
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
    <IconCatalog.Provider
      value={{
        api,
        icons: customIcons,
        added: (icon) => setCustomIcons((previous) => [...previous, icon]),
      }}
    >
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
              className={`rail-button ${view === "calendar" ? "active" : ""}`}
              aria-label="Calendario"
              aria-current={view === "calendar" ? "page" : undefined}
              title="Calendario"
              onClick={() => setView("calendar")}
            >
              <Icon name="calendar" />
            </button>
            <button
              className={`rail-button ${view === "tasks" ? "active" : ""}`}
              aria-label="Tareas"
              title="Tareas"
              aria-current={view === "tasks" ? "page" : undefined}
              onClick={() => setView("tasks")}
            >
              <Icon name="tasks" />
            </button>
            <button
              className={`rail-button ${view === "settings" ? "active" : ""}`}
              aria-label="Configuración"
              title="Configuración"
              aria-current={view === "settings" ? "page" : undefined}
              onClick={() => setView("settings")}
            >
              <Icon name="settings" />
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
          {view !== "calendar" && error && (
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
          {view === "settings" && (
            <Profiles
              members={members}
              api={api}
              saved={() => setRefresh((value) => value + 1)}
            />
          )}
          {view === "tasks" && (
            <TasksPanel
              tasks={tasks}
              members={members}
              api={api}
              day={day}
              saved={() => setRefresh((value) => value + 1)}
            />
          )}
          {view === "calendar" && (
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
                      setDay(
                        DateTime.now().setZone(config.timezone).toISODate()!,
                      )
                    }
                  >
                    Hoy
                  </button>
                  <div className="arrows">
                    <button
                      className="icon-button"
                      aria-label="Día anterior"
                      onClick={() =>
                        setDay(date.minus({ days: 1 }).toISODate()!)
                      }
                    >
                      ‹
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Día siguiente"
                      onClick={() =>
                        setDay(date.plus({ days: 1 }).toISODate()!)
                      }
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
                  <button
                    className="secondary"
                    onClick={() => setMemberForm(true)}
                  >
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
                        const [name, nickname] =
                          member.name.split(/\s*[()]\s*/);
                        return (
                          <div className="person-heading" key={member.id}>
                            <div className="person-identity">
                              <Avatar
                                name={member.name}
                                color={member.color}
                                photo={member.photo_data}
                              />
                              <span className="person-name">{name}</span>
                              {nickname && (
                                <span className="person-nickname">
                                  {nickname}
                                </span>
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
                            <div
                              className="notice-strip"
                              role="group"
                              aria-label={`Avisos de todo el día de ${name}`}
                            >
                              {notices
                                .filter(
                                  (notice) =>
                                    notice.member_id === member.id &&
                                    notice.day === day,
                                )
                                .map((notice) => (
                                  <button
                                    className="notice-token"
                                    key={notice.id}
                                    aria-label={`${notice.title}, editar aviso de ${name}`}
                                    title={notice.title}
                                    onClick={() =>
                                      setNoticeEditor({
                                        memberId: member.id,
                                        notice,
                                      })
                                    }
                                  >
                                    <CustomSymbol
                                      id={notice.custom_icon_id}
                                      fallback={noticeIcons[notice.icon].icon}
                                    />
                                  </button>
                                ))}
                              <button
                                className="daily-add"
                                aria-label={`Añadir aviso de todo el día para ${name}`}
                                title="Añadir aviso de todo el día"
                                onClick={() =>
                                  setNoticeEditor({ memberId: member.id })
                                }
                              >
                                ＋
                              </button>
                            </div>
                            <div
                              className="task-strip"
                              role="group"
                              aria-label={`Tareas de ${name}`}
                            >
                              {occurrences
                                .filter(
                                  (item) =>
                                    item.member_id === member.id &&
                                    item.day === day,
                                )
                                .map((item) => (
                                  <button
                                    className={`task-token ${item.completed ? "done" : ""}`}
                                    key={item.task_id}
                                    aria-label={`${item.title}, ${name}`}
                                    aria-pressed={item.completed}
                                    title={`${item.title} · ${item.completed ? "Hecha" : "Pendiente"}`}
                                    disabled={completing !== null}
                                    onClick={() => complete(item)}
                                  >
                                    <CustomSymbol
                                      id={item.custom_icon_id}
                                      fallback={taskIcons[item.icon].icon}
                                    />
                                    {item.completed && (
                                      <span className="task-tick">
                                        <Icon name="check" />
                                      </span>
                                    )}
                                  </button>
                                ))}
                              {!occurrences.some(
                                (item) =>
                                  item.member_id === member.id &&
                                  item.day === day,
                              ) && (
                                <span className="small muted no-tasks">
                                  Sin tareas para hoy
                                </span>
                              )}
                            </div>
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
                                backgroundColor:
                                  categories[event.category].color,
                                textColor: categories[event.category].ink,
                                extendedProps: {
                                  category: event.category,
                                  custom_icon_id: event.custom_icon_id,
                                },
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
                              <div
                                className="event-content"
                                title={info.event.title}
                              >
                                <span className="event-time">
                                  {info.timeText}
                                </span>
                                <strong>{info.event.title}</strong>
                                <span
                                  className="event-category"
                                  role="img"
                                  aria-label={
                                    categories[
                                      (info.event.extendedProps.category ??
                                        "other") as Category
                                    ].label
                                  }
                                  title={
                                    categories[
                                      (info.event.extendedProps.category ??
                                        "other") as Category
                                    ].label
                                  }
                                >
                                  <CustomSymbol
                                    id={info.event.extendedProps.custom_icon_id}
                                    fallback={
                                      categories[
                                        (info.event.extendedProps.category ??
                                          "other") as Category
                                      ].icon
                                    }
                                  />
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
              <div
                className="category-legend"
                aria-label="Categorías de eventos"
              >
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
                <span>
                  Toca una hora para añadir un plan · {config.timezone}
                </span>
              </footer>
            </section>
          )}
        </main>
        {noticeEditor &&
          members.find((member) => member.id === noticeEditor.memberId) && (
            <NoticeForm
              api={api}
              member={members.find(
                (member) => member.id === noticeEditor.memberId,
              )!}
              day={day}
              notice={noticeEditor.notice}
              close={() => setNoticeEditor(null)}
              saved={() => {
                setNoticeEditor(null);
                setRefresh((value) => value + 1);
              }}
            />
          )}
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
    </IconCatalog.Provider>
  );
}
