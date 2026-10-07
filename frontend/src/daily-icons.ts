import type { NoticeInput, TaskInput } from "./api";
import type { IconName } from "./visuals";

export const noticeIcons: Record<
  NoticeInput["icon"] & string,
  { label: string; icon: IconName }
> = {
  uniform: { label: "Día de uniforme", icon: "uniform" },
  tracksuit: { label: "Día de chándal", icon: "tracksuit" },
  trip: { label: "Excursión", icon: "trip" },
  other: { label: "Otro aviso", icon: "other" },
};
export const taskIcons: Record<
  TaskInput["icon"] & string,
  { label: string; icon: IconName }
> = {
  tooth: { label: "Lavarse los dientes", icon: "tooth" },
  backpack: { label: "Hacer la mochila", icon: "backpack" },
  bed: { label: "Hacer la cama", icon: "bed" },
  other: { label: "Otra tarea", icon: "other" },
};
