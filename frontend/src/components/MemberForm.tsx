import { useState, type FormEvent } from "react";
import { Api, type Member } from "../api";
import { Dialog } from "./Dialog";

export const memberColors = [
  "#dcebe2",
  "#dce6f3",
  "#f4e7cf",
  "#eadff0",
  "#f5dfe3",
  "#dceeee",
];

export function MemberForm({
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
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "No se pudo añadir el integrante.",
      );
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
            {memberColors.map((value, index) => (
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
