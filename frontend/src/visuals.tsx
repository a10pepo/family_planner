import type { CSSProperties } from "react";

export type IconName =
  | "birthday"
  | "settings"
  | "tasks"
  | "uniform"
  | "tracksuit"
  | "trip"
  | "tooth"
  | "backpack"
  | "bed"
  | "check"
  | "calendar"
  | "people"
  | "logout"
  | "repeat"
  | "school"
  | "activities"
  | "medical"
  | "friends"
  | "other";

const paths: Record<IconName, React.ReactNode> = {
  birthday: (
    <>
      <path d="M4 12h16v9H4zM4 16c2 2 3-2 5 0s3-2 5 0 3-2 6 0M8 12V8m4 4V7m4 5V8" />
      <path d="M8 5V3m4 1V2m4 3V3" />
    </>
  ),
  settings: (
    <>
      <path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 2 3h4l1-3 3-1 2-3-2-2 1-3-2-3-3 1-2-3H9Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  tasks: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="3" />
      <path d="m7 8 1 1 2-2m3 1h4m-10 6 1 1 2-2m3 1h4" />
    </>
  ),
  uniform: (
    <>
      <path d="m8 3-6 4 3 5 3-2v11h8V10l3 2 3-5-6-4-4 3-4-3Z" />
      <path d="m10 5 2 4 2-4m-2 4v6" />
    </>
  ),
  tracksuit: (
    <>
      <path d="m8 3-6 4 3 5 3-2v11h8V10l3 2 3-5-6-4H8Z" />
      <path d="M12 3v18m-3-8h2m2 0h2" />
    </>
  ),
  trip: (
    <>
      <rect x="4" y="3" width="16" height="16" rx="3" />
      <path d="M4 11h16m-8-8v8m-4 4h1m6 0h1M7 19v2m10-2v2" />
    </>
  ),
  tooth: (
    <>
      <path d="M12 5c-2-3-8-4-9 2-1 5 3 14 5 14 2 0 1-7 4-7s2 7 4 7c2 0 6-9 5-14-1-6-7-5-9-2Z" />
      <path d="M9 4c0 2 2 3 5 3" />
    </>
  ),
  backpack: (
    <>
      <rect x="5" y="6" width="14" height="15" rx="4" />
      <path d="M9 6V4a3 3 0 0 1 6 0v2M5 11H3v7h2m14-7h2v7h-2" />
      <rect x="8" y="13" width="8" height="5" rx="1" />
    </>
  ),
  bed: (
    <>
      <path d="M3 20V8m18 12V10H3m0 7h18" />
      <path d="M7 10V5h10v5M4 17v-3a3 3 0 0 1 3-3h10a4 4 0 0 1 4 4v2" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2" />
    </>
  ),
  people: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m3 10v-3a6 6 0 0 0-3-5" />
    </>
  ),
  logout: (
    <>
      <path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5m4-12 4 4-4 4m-6-4h13" />
    </>
  ),
  repeat: (
    <>
      <path d="M17 2l4 4-4 4" />
      <path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4" />
      <path d="M21 13v2a3 3 0 0 1-3 3H3" />
    </>
  ),
  school: (
    <>
      <path d="m2 8 10-5 10 5-10 5-10-5Zm4 3v6c4 3 8 3 12 0v-6m4-3v9" />
    </>
  ),
  activities: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m12 7 4 3-2 5h-4l-2-5 4-3ZM4 7l4 3m8 0 4-3M6 19l4-4m4 0 4 4M12 3v4" />
    </>
  ),
  medical: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <path d="M12 7v10m-5-5h10" />
    </>
  ),
  friends: (
    <>
      <path d="M20 4a5 5 0 0 0-8 2 5 5 0 0 0-8-2c-5 4 1 10 8 16 7-6 13-12 8-16Z" />
    </>
  ),
  other: (
    <>
      <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-3-5.5 3 1-6.2L3 9.6l6.2-.9L12 3Z" />
    </>
  ),
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export function Avatar({
  name,
  color,
  photo,
}: {
  name: string;
  color: string;
  photo?: string | null;
}) {
  const first = name.split(/[\s(]/)[0];
  if (photo)
    return <img className="face-avatar" src={photo} alt={`Foto de ${first}`} />;
  const kind =
    first === "Laura"
      ? "long"
      : first === "Pedro"
        ? "beard"
        : first === "Lucía"
          ? "pigtails"
          : "short";
  const hair =
    kind === "beard" ? "#56463e" : kind === "pigtails" ? "#775241" : "#624637";
  const style = { "--avatar-color": color } as CSSProperties;
  return (
    <svg
      className="face-avatar"
      style={style}
      viewBox="0 0 100 100"
      role="img"
      aria-label={`Cara ilustrada de ${first}`}
    >
      <circle cx="50" cy="50" r="49" fill={color} />
      {kind === "long" && (
        <path d="M25 77V43c0-34 50-34 50 0v34Z" fill={hair} />
      )}
      {kind === "pigtails" && (
        <>
          <ellipse cx="23" cy="61" rx="10" ry="20" fill={hair} />
          <ellipse cx="77" cy="61" rx="10" ry="20" fill={hair} />
          <circle cx="24" cy="47" r="5" fill="#dd9baa" />
          <circle cx="76" cy="47" r="5" fill="#dd9baa" />
        </>
      )}
      <path
        d="M17 100c2-22 14-28 33-28s31 6 33 28"
        fill={
          kind === "long"
            ? "#8ca999"
            : kind === "beard"
              ? "#8299bb"
              : kind === "pigtails"
                ? "#b097bd"
                : "#d0ad74"
        }
      />
      <rect x="43" y="62" width="14" height="17" rx="7" fill="#e9b68f" />
      <ellipse cx="50" cy="46" rx="25" ry="29" fill={hair} />
      <ellipse cx="27" cy="50" rx="5" ry="7" fill="#f3c8a4" />
      <ellipse cx="73" cy="50" rx="5" ry="7" fill="#f3c8a4" />
      <path d="M29 40c0-24 42-24 42 0v16c0 28-42 28-42 0Z" fill="#f3c8a4" />
      <path
        d={
          kind === "short"
            ? "M27 43V31c3-23 44-18 46 9-9-2-14-6-18-13-6 11-16 14-28 16Z"
            : "M27 43V32c2-21 45-21 46 7-17 1-27-5-30-13-3 9-8 14-16 17Z"
        }
        fill={hair}
      />
      {kind === "beard" && (
        <path
          d="M30 56c8 7 10 3 20 3s12 4 20-3c-2 28-38 28-40 0Z"
          fill={hair}
          opacity=".9"
        />
      )}
      <circle cx="40" cy="47" r="2.1" fill="#443a34" />
      <circle cx="60" cy="47" r="2.1" fill="#443a34" />
      <path
        d="M48 49v7h4"
        stroke="#d99c78"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M43 62q7 6 14 0"
        stroke={kind === "beard" ? "#f3c8a4" : "#b47466"}
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      {kind !== "beard" && (
        <>
          <ellipse cx="35" cy="56" rx="4" ry="2" fill="#e9a998" opacity=".6" />
          <ellipse cx="65" cy="56" rx="4" ry="2" fill="#e9a998" opacity=".6" />
        </>
      )}
    </svg>
  );
}
