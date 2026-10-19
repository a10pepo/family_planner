import type { NoticeInput, TaskInput } from "./api";
import type { IconName } from "./visuals";
import backpackImage from "./assets/task-icons/backpack.jpg";
import bedImage from "./assets/task-icons/bed.jpg";
import homeworkImage from "./assets/task-icons/homework.jpg";
import schoolImage from "./assets/task-icons/school.jpg";
import teethImage from "./assets/task-icons/teeth.jpg";
import uniformImage from "./assets/task-icons/uniform.jpg";

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
  { label: string; icon: IconName; image?: string }
> = {
  school: { label: "Ir al colegio", icon: "school", image: schoolImage },
  homework: {
    label: "Hacer los deberes",
    icon: "other",
    image: homeworkImage,
  },
  uniform: {
    label: "Preparar el uniforme",
    icon: "uniform",
    image: uniformImage,
  },
  tooth: { label: "Lavarse los dientes", icon: "tooth", image: teethImage },
  backpack: {
    label: "Hacer la mochila",
    icon: "backpack",
    image: backpackImage,
  },
  bed: { label: "Hacer la cama", icon: "bed", image: bedImage },
  other: { label: "Otra tarea", icon: "other" },
};
