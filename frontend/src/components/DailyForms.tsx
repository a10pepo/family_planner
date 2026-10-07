import { useState, type FormEvent } from "react";
import {
  Api,
  type Member,
  type Notice,
  type NoticeInput,
  type Task,
  type TaskInput,
} from "../api";
import { noticeIcons, taskIcons } from "../daily-icons";
import { CustomSymbol, IconPicker } from "./IconCatalog";
import { Dialog } from "./Dialog";

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo guardar el cambio.";

export function NoticeForm({
  api,
  member,
  day,
  notice,
  close,
  saved,
}: {
  api: Api;
  member: Member;
  day: string;
  notice?: Notice;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState(notice?.title ?? "Día de uniforme");
  const [icon, setIcon] = useState<NonNullable<NoticeInput["icon"]>>(
    notice?.icon ?? "uniform",
  );
  const [customIcon, setCustomIcon] = useState<string | null>(
    notice?.custom_icon_id ?? null,
  );
  const [date, setDate] = useState(notice?.day ?? day);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [confirm, setConfirm] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (notice)
        await api.updateNotice(notice.id, {
          day: date,
          title: title.trim(),
          icon,
          custom_icon_id: customIcon,
        });
      else
        await api.addNotice({
          member_id: member.id,
          day: date,
          title: title.trim(),
          icon,
          custom_icon_id: customIcon,
        });
      saved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={
        notice ? "Editar aviso de todo el día" : "Añadir aviso de todo el día"
      }
      close={close}
      busy={busy}
    >
      <form onSubmit={submit}>
        <p className="muted">Para {member.name}</p>
        <fieldset disabled={busy}>
          <legend>Icono del aviso</legend>
          <IconPicker
            options={noticeIcons}
            builtin={icon}
            selected={customIcon}
            busy={busy}
            setBusy={setBusy}
            onChange={(value, custom, label) => {
              setIcon(value as typeof icon);
              setCustomIcon(custom);
              if (
                !notice &&
                !custom &&
                Object.values(noticeIcons).some(
                  (details) => details.label === title,
                )
              )
                setTitle(label);
            }}
          />
        </fieldset>
        <label>
          Título del aviso
          <input
            required
            maxLength={80}
            value={title}
            disabled={busy}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label>
          Fecha del aviso
          <input
            type="date"
            required
            value={date}
            disabled={busy}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {confirm && notice && (
          <div className="delete-confirm">
            <p>¿Eliminar este aviso?</p>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.deleteNotice(notice.id);
                  saved();
                } catch (error) {
                  setError(errorMessage(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Confirmar eliminación del aviso
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Conservar aviso
            </button>
          </div>
        )}
        <div className="form-actions">
          {notice && !confirm && (
            <button
              type="button"
              className="delete-button"
              disabled={busy}
              onClick={() => setConfirm(true)}
            >
              Eliminar aviso
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
            {busy ? "Guardando…" : "Guardar aviso"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function TaskForm({
  api,
  members,
  day,
  task,
  close,
  saved,
}: {
  api: Api;
  members: Member[];
  day: string;
  task?: Task;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState(task?.title ?? "Lavarse los dientes");
  const [icon, setIcon] = useState<NonNullable<TaskInput["icon"]>>(
    task?.icon ?? "tooth",
  );
  const [customIcon, setCustomIcon] = useState<string | null>(
    task?.custom_icon_id ?? null,
  );
  const [frequency, setFrequency] = useState<
    NonNullable<TaskInput["frequency"]>
  >(task?.frequency ?? "daily");
  const [starts, setStarts] = useState(task?.starts_on ?? day);
  const [ids, setIds] = useState<string[]>(task?.member_ids ?? []);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data: TaskInput = {
      title: title.trim(),
      icon,
      custom_icon_id: customIcon,
      frequency,
      starts_on: starts,
      member_ids: ids,
    };
    try {
      if (task) await api.updateTask(task.id, data);
      else await api.addTask(data);
      saved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={task ? "Editar tarea" : "Nueva tarea"}
      close={close}
      busy={busy}
    >
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend>Icono de la tarea</legend>
          <IconPicker
            options={taskIcons}
            builtin={icon}
            selected={customIcon}
            busy={busy}
            setBusy={setBusy}
            onChange={(value, custom, label) => {
              setIcon(value as typeof icon);
              setCustomIcon(custom);
              if (
                !task &&
                !custom &&
                Object.values(taskIcons).some(
                  (details) => details.label === title,
                )
              )
                setTitle(label);
            }}
          />
        </fieldset>
        <label>
          Nombre de la tarea
          <input
            required
            maxLength={80}
            value={title}
            disabled={busy}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <fieldset disabled={busy}>
          <legend>¿Para quién?</legend>
          <div className="assignment-options">
            {members.map((member) => (
              <label key={member.id}>
                <input
                  type="checkbox"
                  checked={ids.includes(member.id)}
                  onChange={(event) =>
                    setIds((previous) =>
                      event.target.checked
                        ? [...previous, member.id]
                        : previous.filter((id) => id !== member.id),
                    )
                  }
                />
                {member.name}
              </label>
            ))}
          </div>
        </fieldset>
        <label>
          Repetir
          <select
            aria-label="Repetir"
            disabled={busy}
            value={frequency}
            onChange={(event) =>
              setFrequency(event.target.value as typeof frequency)
            }
          >
            <option value="daily">Todos los días</option>
            <option value="once">Solo un día</option>
          </select>
        </label>
        <label>
          {frequency === "daily" ? "Desde el día" : "Día de la tarea"}
          <input
            type="date"
            required
            disabled={busy}
            value={starts}
            onChange={(event) => setStarts(event.target.value)}
          />
        </label>
        <p className="muted small">
          Cada persona marca su propia tarea en el día del calendario. Puedes
          desmarcarla tocando de nuevo.
        </p>
        {error && (
          <p className="error" role="alert">
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
          <button disabled={busy || !title.trim() || !ids.length || !starts}>
            {busy ? "Guardando…" : "Guardar tarea"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function TasksPanel({
  tasks,
  members,
  api,
  day,
  saved,
}: {
  tasks: Task[];
  members: Member[];
  api: Api;
  day: string;
  saved: () => void;
}) {
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const [archiving, setArchiving] = useState<Task | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <section className="management-panel" aria-label="Tareas">
      <header className="management-heading">
        <div>
          <h1>Tareas</h1>
          <p className="muted">Pequeñas rutinas, un día a la vez.</p>
        </div>
        <button disabled={!members.length} onClick={() => setEditing("new")}>
          ＋ Crear tarea
        </button>
      </header>
      <p className="management-note">
        Los iconos aparecen bajo cada persona en el calendario. Pulsa uno cuando
        esté hecho.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="task-list">
        {tasks.map((task) => (
          <article className="task-card" key={task.id}>
            <span className="task-symbol">
              <CustomSymbol
                id={task.custom_icon_id}
                fallback={taskIcons[task.icon].icon}
              />
            </span>
            <div className="task-description">
              <h2>{task.title}</h2>
              <p>
                {task.member_ids
                  .map(
                    (id) =>
                      members.find((member) => member.id === id)?.name ??
                      "Integrante",
                  )
                  .join(" · ")}
              </p>
              <span className="small muted">
                {task.frequency === "daily"
                  ? "Todos los días desde"
                  : "Solo el"}{" "}
                {task.starts_on}
              </span>
            </div>
            <div className="task-actions">
              <button
                className="secondary"
                aria-label={`Editar tarea ${task.title}`}
                onClick={() => setEditing(task)}
              >
                Editar
              </button>
              <button
                className="delete-button"
                aria-label={`Archivar tarea ${task.title}`}
                onClick={() => setArchiving(task)}
              >
                Archivar
              </button>
            </div>
          </article>
        ))}
      </div>
      {!tasks.length && (
        <p className="empty-note">
          Crea vuestra primera rutina y asígnala a quienes tengan que hacerla.
        </p>
      )}
      {editing && (
        <TaskForm
          key={editing === "new" ? "new" : editing.id}
          api={api}
          members={members}
          day={day}
          task={editing === "new" ? undefined : editing}
          close={() => setEditing(null)}
          saved={() => {
            setEditing(null);
            saved();
          }}
        />
      )}
      {archiving && (
        <Dialog
          title="Archivar tarea"
          close={() => setArchiving(null)}
          busy={busy}
        >
          <p>
            «{archiving.title}» dejará de aparecer. Se conservarán las marcas de
            los días anteriores.
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setArchiving(null)}
            >
              Cancelar
            </button>
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api.archiveTask(archiving.id);
                  setArchiving(null);
                  saved();
                } catch (error) {
                  setError(errorMessage(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Confirmar archivo
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
