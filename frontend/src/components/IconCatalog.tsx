import { createContext, useContext, useRef, useState } from "react";
import { Api, type CustomIcon } from "../api";
import { prepareIcon } from "../photos";
import { Icon, type IconName } from "../visuals";

export const IconCatalog = createContext<{
  api: Api;
  icons: CustomIcon[];
  added: (icon: CustomIcon) => void;
} | null>(null);

export function CustomSymbol({
  id,
  fallback,
}: {
  id?: string | null;
  fallback: IconName;
}) {
  const library = useContext(IconCatalog);
  const image = library?.icons.find((icon) => icon.id === id);
  return image ? (
    <img
      className="custom-symbol"
      src={image.image_data}
      alt=""
      aria-hidden="true"
    />
  ) : (
    <Icon name={fallback} />
  );
}

export function IconPicker({
  options,
  builtin,
  selected,
  onChange,
  busy,
  setBusy,
  allowUpload = true,
}: {
  options: Record<string, { label: string; icon: IconName }>;
  builtin: string;
  selected?: string | null;
  onChange: (builtin: string, selected: string | null, label: string) => void;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  allowUpload?: boolean;
}) {
  const library = useContext(IconCatalog);
  const file = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  if (!library) throw new Error("Falta el catálogo de iconos.");
  return (
    <>
      <div className="symbol-options">
        {Object.entries(options).map(([value, details]) => (
          <button
            key={value}
            type="button"
            className={`symbol-choice ${!selected && builtin === value ? "chosen" : ""}`}
            aria-label={details.label}
            title={details.label}
            aria-pressed={!selected && builtin === value}
            disabled={busy}
            onClick={() => onChange(value, null, details.label)}
          >
            <Icon name={details.icon} />
          </button>
        ))}
        {library.icons.map((icon) => (
          <button
            key={icon.id}
            type="button"
            className={`symbol-choice ${selected === icon.id ? "chosen" : ""}`}
            aria-label={`Icono ${icon.name}`}
            title={icon.name}
            aria-pressed={selected === icon.id}
            disabled={busy}
            onClick={() => onChange(builtin, icon.id, icon.name)}
          >
            <CustomSymbol id={icon.id} fallback="other" />
          </button>
        ))}
      </div>
      {allowUpload && (
        <div className="icon-upload">
          <label>
            Nombre del nuevo icono
            <input
              value={name}
              maxLength={80}
              disabled={busy}
              placeholder="Se usa el nombre del fichero"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => file.current?.click()}
          >
            Subir icono
          </button>
          <input
            type="file"
            hidden
            ref={file}
            aria-label="Archivo del icono"
            accept="image/png,image/jpeg,image/webp"
            disabled={busy}
            onChange={async (event) => {
              const input = event.currentTarget,
                selectedFile = input.files?.[0];
              if (!selectedFile) return;
              setBusy(true);
              setError("");
              try {
                const image = await prepareIcon(selectedFile);
                const title =
                  (
                    name.trim() || selectedFile.name.replace(/\.[^.]+$/, "")
                  ).slice(0, 80) || "Icono";
                const icon = await library.api.addIcon(title, image);
                library.added(icon);
                onChange(builtin, icon.id, icon.name);
                setName("");
              } catch (error) {
                setError(
                  error instanceof Error
                    ? error.message
                    : "No se pudo subir el icono.",
                );
              } finally {
                input.value = "";
                setBusy(false);
              }
            }}
          />
          <p className="small muted">
            JPG, PNG o WebP, hasta 5 MB. Una vez subido estará disponible en
            tareas, avisos y eventos.
          </p>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </div>
      )}
    </>
  );
}
