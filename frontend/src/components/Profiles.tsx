import { useRef, useState, type FormEvent } from "react";
import { Api, type Member } from "../api";
import { Avatar } from "../visuals";
import { preparePhoto } from "../photos";
import { Dialog } from "./Dialog";

export function Profiles({
  members,
  api,
  saved,
}: {
  members: Member[];
  api: Api;
  saved: () => void;
}) {
  const [editing, setEditing] = useState<Member | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function change(member: Member, restore = false) {
    setBusy(true);
    setError("");
    try {
      if (restore) await api.restoreMember(member.id);
      else await api.archiveMember(member.id);
      setRemoving(null);
      saved();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "No se pudo cambiar el integrante.",
      );
    } finally {
      setBusy(false);
    }
  }
  const active = members.filter((member) => member.active !== false);
  const archived = members.filter((member) => member.active === false);
  return (
    <section className="management-panel" aria-label="Configuración">
      <header className="management-heading">
        <h1>Configuración</h1>
        <p className="muted">Un nombre y una cara para cada uno.</p>
      </header>
      <div className="profile-grid">
        {active.map((member) => (
          <article className="profile-card" key={member.id}>
            <Avatar
              name={member.name}
              color={member.color}
              photo={member.photo_data}
            />
            <h2>{member.name}</h2>
            <button
              className="secondary"
              aria-label={`Editar perfil de ${member.name}`}
              onClick={() => setEditing(member)}
            >
              Editar perfil
            </button>
            <button
              className="delete-button"
              aria-label={`Retirar integrante ${member.name}`}
              disabled={busy}
              onClick={() => {
                setError("");
                setRemoving(member);
              }}
            >
              Retirar integrante
            </button>
          </article>
        ))}
      </div>
      {!active.length && (
        <p className="empty-note">
          Añade primero a los integrantes desde el icono de personas.
        </p>
      )}
      {!removing && error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!!archived.length && (
        <section
          className="archived-members"
          aria-label="Integrantes archivados"
        >
          <h2>Integrantes archivados</h2>
          {archived.map((member) => (
            <div className="archived-member" key={member.id}>
              <span>{member.name}</span>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => change(member, true)}
                aria-label={`Restaurar integrante ${member.name}`}
              >
                Restaurar
              </button>
            </div>
          ))}
        </section>
      )}
      {removing && (
        <Dialog
          title="Retirar integrante"
          close={() => setRemoving(null)}
          busy={busy}
        >
          <p>
            ¿Retirar a <strong>{removing.name}</strong> del calendario?
          </p>
          <p className="muted">
            Su columna y sus actividades dejarán de mostrarse. Conservaremos sus
            eventos y marcas de tareas; podrás restaurarlos desde Configuración.
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
              onClick={() => setRemoving(null)}
            >
              Conservar integrante
            </button>
            <button
              className="danger"
              disabled={busy}
              onClick={() => change(removing)}
            >
              Confirmar retiro
            </button>
          </div>
        </Dialog>
      )}
      {editing && (
        <ProfileEditor
          key={editing.id}
          member={editing}
          api={api}
          close={() => setEditing(null)}
          saved={() => {
            setEditing(null);
            saved();
          }}
        />
      )}
    </section>
  );
}

function ProfileEditor({
  member,
  api,
  close,
  saved,
}: {
  member: Member;
  api: Api;
  close: () => void;
  saved: () => void;
}) {
  const [name, setName] = useState(member.name);
  const [photo, setPhoto] = useState<string | null>(member.photo_data ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.updateMember(member.id, {
        name: name.trim(),
        photo_data: photo,
      });
      saved();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "No se pudo guardar el perfil.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Editar perfil" close={close} busy={busy}>
      <form onSubmit={submit}>
        <div className="photo-editor">
          <Avatar
            name={name || member.name}
            color={member.color}
            photo={photo}
          />
          <div>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => file.current?.click()}
            >
              Elegir foto
            </button>
            {photo && (
              <button
                type="button"
                className="delete-button"
                disabled={busy}
                onClick={() => setPhoto(null)}
              >
                Quitar foto
              </button>
            )}
          </div>
          <input
            ref={file}
            type="file"
            aria-label="Foto del integrante"
            accept="image/jpeg,image/png,image/webp"
            hidden
            disabled={busy}
            onChange={async (event) => {
              const input = event.currentTarget,
                selected = input.files?.[0];
              if (!selected) return;
              setBusy(true);
              setError("");
              try {
                setPhoto(await preparePhoto(selected));
              } catch (error) {
                setError(
                  error instanceof Error
                    ? error.message
                    : "No se pudo abrir la foto.",
                );
              } finally {
                setBusy(false);
                input.value = "";
              }
            }}
          />
          <p className="muted small">
            JPG, PNG o WebP, hasta 5 MB. Se recorta al centro.
          </p>
        </div>
        <label>
          Nombre
          <input
            required
            maxLength={80}
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
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
          <button disabled={busy || !name.trim()}>
            {busy ? "Guardando…" : "Guardar perfil"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
