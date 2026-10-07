import type { components } from "./api-schema";
import type { IconName } from "./visuals";

export type Category = components["schemas"]["Category"];
export const categories: Record<
  Category,
  { label: string; color: string; ink: string; icon: IconName }
> = {
  school: {
    label: "Colegio",
    color: "#dce8fa",
    ink: "#4f6b91",
    icon: "school",
  },
  activities: {
    label: "Extraescolares",
    color: "#faecd1",
    ink: "#8b7041",
    icon: "activities",
  },
  medical: {
    label: "Médicos",
    color: "#f5dfe4",
    ink: "#945e6c",
    icon: "medical",
  },
  friends: {
    label: "Amigos",
    color: "#e7def4",
    ink: "#786091",
    icon: "friends",
  },
  other: { label: "Otros", color: "#dcece3", ink: "#557864", icon: "other" },
};
