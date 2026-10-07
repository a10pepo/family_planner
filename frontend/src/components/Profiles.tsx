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
  return (
    <section className="management-panel" aria-label="Configuración">
      <header className="management-heading">
        <h1>Configuración</h1>
        <p className="muted">Un nombre y una cara para cada uno.</p>
      </header>
      <div className="profile-grid">
        {members.map((member) => (
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
          </article>
        ))}
      </div>
      {!members.length && (
        <p className="empty-note">
          Añade primero a los integrantes desde el icono de personas.
        </p>
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
