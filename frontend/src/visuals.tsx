import type { CSSProperties } from "react";

export type IconName =
  | "calendar"
  | "people"
  | "logout"
  | "school"
  | "activities"
  | "medical"
  | "friends"
  | "other";

const paths: Record<IconName, React.ReactNode> = {
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

export function Avatar({ name, color }: { name: string; color: string }) {
  const first = name.split(/[\s(]/)[0];
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
