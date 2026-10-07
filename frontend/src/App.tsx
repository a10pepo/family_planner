import {
  useCallback,
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

const colors = [
  "#367d68",
  "#4775be",
  "#b55d77",
  "#a87525",
  "#8068b6",
  "#498c9e",
];
const initials = (name: string) =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
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
  const [memberId, setMemberId] = useState(
    editor.event?.member_id ?? selected ?? members[0]?.id ?? "",
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
      const data = { title: title.trim(), starts_at, ends_at };
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
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [range, setRange] = useState<{ start: string; end: string } | null>(
    null,
  );
  const [heading, setHeading] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [moving, setMoving] = useState(false);
  const [memberForm, setMemberForm] = useState(false);
  const [editor, setEditor] = useState<Editor | null>(null);
  const calendar = useRef<FullCalendar>(null);

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
    if (!authenticated || !range) return;
    let active = true;
    api
      .events(range.start, range.end, selected)
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
  }, [api, authenticated, range, selected, refresh]);

  const addEvent = useCallback(
    (start?: string, end?: string) => {
      const date = DateTime.now()
        .setZone(config.timezone)
        .plus({ hours: 1 })
        .startOf("hour");
      setEditor({
        start: start ?? date.toISO()!,
        end: end ?? date.plus({ hours: 1 }).toISO()!,
      });
    },
    [config.timezone],
  );

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
        <div className="brand-mark">◷</div>
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

  const memberById = new Map(members.map((member) => [member.id, member]));
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <a href="/" className="brand">
          <span className="brand-mark">◷</span>
          <span>
            family
            <br />
            <strong>planner</strong>
          </span>
        </a>
        <div className="sidebar-main">
          <p className="eyebrow">NUESTRO ESPACIO</p>
          <div className="nav-active">
            <span aria-hidden="true">▦</span> Calendario
          </div>
          <button
            className="add-event"
            disabled={!members.length || loading}
            onClick={() => addEvent()}
          >
            ＋ Añadir evento
          </button>
          <button className="sidebar-link" onClick={() => setMemberForm(true)}>
            ＋ Añadir integrante
          </button>
        </div>
        <div className="sidebar-bottom">
          <p>
            Pequeños planes.
            <br />
            <strong>Grandes momentos.</strong>
          </p>
          <button
            className="sidebar-link"
            onClick={() =>
              auth.logout({ redirectUri: `${window.location.origin}/` })
            }
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="workspace">
        <header className="page-heading">
          <div>
            <p className="eyebrow">TODO EN SU SITIO</p>
            <h1>
              Nuestro calendario<span className="heading-dot">.</span>
            </h1>
            <p className="muted">Cada uno con sus planes. Todos conectados.</p>
          </div>
          <div className="household-badge">
            <span aria-hidden="true">⌂</span> En familia
          </div>
        </header>
        <section className="family-bar" aria-label="Integrantes de la familia">
          <div className="family-label">
            <span className="eyebrow">LA FAMILIA</span>
            <span className="small muted">Elige de quién ver los planes</span>
          </div>
          <div className="member-list">
            <button
              className={`member-button ${selected === null ? "selected" : ""}`}
              aria-pressed={selected === null}
              onClick={() => setSelected(null)}
            >
              <span className="avatar all-avatar">⌂</span>
              <span>Todos</span>
            </button>
            {members.map((member) => (
              <button
                key={member.id}
                className={`member-button ${selected === member.id ? "selected" : ""}`}
                aria-pressed={selected === member.id}
                onClick={() =>
                  setSelected(selected === member.id ? null : member.id)
                }
              >
                <span
                  className="avatar"
                  style={{
                    background: `${member.color}17`,
                    color: member.color,
                    borderColor: member.color,
                  }}
                >
                  {initials(member.name)}
                </span>
                <span>{member.name}</span>
              </button>
            ))}
            <button
              className="member-button add-member"
              onClick={() => setMemberForm(true)}
            >
              <span className="avatar">＋</span>
              <span>Añadir</span>
            </button>
          </div>
        </section>
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
        {!loading && !members.length && (
          <div className="empty-note">
            <strong>El primer paso: añadir a vuestra familia.</strong>
            <span>Después podréis empezar a llenar el calendario.</span>
            <button className="secondary" onClick={() => setMemberForm(true)}>
              Añadir el primer integrante
            </button>
          </div>
        )}
        <section className="calendar-panel" aria-label="Calendario semanal">
          <div className="calendar-toolbar">
            <div className="calendar-period">
              <h2>{heading}</h2>
              <span className="small muted">
                {moving
                  ? "Guardando movimiento…"
                  : "Una semana, muchos momentos"}
              </span>
            </div>
            <div className="calendar-controls">
              <button
                className="secondary"
                onClick={() => calendar.current?.getApi().today()}
              >
                Hoy
              </button>
              <div className="arrows">
                <button
                  className="icon-button"
                  aria-label="Semana anterior"
                  onClick={() => calendar.current?.getApi().prev()}
                >
                  ‹
                </button>
                <button
                  className="icon-button"
                  aria-label="Semana siguiente"
                  onClick={() => calendar.current?.getApi().next()}
                >
                  ›
                </button>
              </div>
              <span className="view-badge">Semana</span>
              <button
                className="mobile-add"
                disabled={!members.length}
                onClick={() => addEvent()}
              >
                ＋ Evento
              </button>
            </div>
          </div>
          <div className="calendar-scroll">
            <FullCalendar
              ref={calendar}
              plugins={[timeGrid, interaction, luxonPlugin]}
              locale={es}
              timeZone={config.timezone}
              initialView="timeGridWeek"
              firstDay={1}
              headerToolbar={false}
              allDaySlot={false}
              nowIndicator
              height={700}
              slotMinTime="00:00:00"
              slotMaxTime="24:00:00"
              scrollTime="07:00:00"
              slotDuration="00:30:00"
              slotLabelInterval="01:00:00"
              editable={!moving && !editor}
              selectable={!!members.length}
              selectMirror
              longPressDelay={350}
              eventMinHeight={44}
              eventTimeFormat={{
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
              }}
              dayHeaderFormat={{ weekday: "short", day: "numeric" }}
              datesSet={(info) => {
                setHeading(info.view.title);
                setRange((previous) =>
                  previous?.start === info.startStr &&
                  previous.end === info.endStr
                    ? previous
                    : { start: info.startStr, end: info.endStr },
                );
              }}
              events={events.map((event) => ({
                id: event.id,
                title: event.title,
                start: event.starts_at,
                end: event.ends_at,
                backgroundColor: memberById.get(event.member_id)?.color,
                borderColor: memberById.get(event.member_id)?.color,
                extendedProps: {
                  member: memberById.get(event.member_id)?.name,
                },
              }))}
              select={(info) => {
                addEvent(info.startStr, info.endStr);
                calendar.current?.getApi().unselect();
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
                  <span className="event-member">
                    {info.event.extendedProps.member}
                  </span>
                </div>
              )}
            />
          </div>
          <footer className="calendar-footer">
            <span>
              <span className="status-dot" />{" "}
              {loading
                ? "Cargando familia…"
                : `${members.length} ${members.length === 1 ? "integrante" : "integrantes"} · ${events.length} ${events.length === 1 ? "evento" : "eventos"} esta semana`}
            </span>
            <span>
              Mantén pulsado un evento para moverlo · {config.timezone}
            </span>
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
            setSelected(member.id);
            setMemberForm(false);
          }}
        />
      )}
      {editor && (
        <EventForm
          api={api}
          members={members}
          selected={selected}
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
