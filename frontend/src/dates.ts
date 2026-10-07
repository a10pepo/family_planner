import { DateTime } from "luxon";

export function localInput(iso: string, zone: string): string {
  return DateTime.fromISO(iso, { zone }).toFormat("yyyy-MM-dd'T'HH:mm");
}

export function fromLocalInput(value: string, zone: string): string {
  const date = DateTime.fromISO(value, { zone });
  if (!date.isValid || date.toFormat("yyyy-MM-dd'T'HH:mm") !== value) {
    throw new Error(
      "Esta hora no existe en la zona familiar. Elige otra hora.",
    );
  }
  if (date.getPossibleOffsets().length > 1) {
    throw new Error(
      "Esta hora se repite por el cambio horario. Elige una hora fuera de ese intervalo.",
    );
  }
  return date.toUTC().toISO()!;
}
