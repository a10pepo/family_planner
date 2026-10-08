import { useEffect, useState } from "react";
import { DateTime } from "luxon";

export function useCurrentTime(zone: string) {
  const [now, setNow] = useState(() => DateTime.now().setZone(zone));
  useEffect(() => {
    const update = () => setNow(DateTime.now().setZone(zone));
    const timer = window.setInterval(update, 15000);
    window.addEventListener("focus", update);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", update);
    };
  }, [zone]);
  return now;
}

export function CurrentTime({ now, day }: { now: DateTime; day: string }) {
  if (now.toISODate() !== day) return null;
  const minute = now.hour * 60 + now.minute + now.second / 60;
  return (
    <div
      className="current-time-line"
      role="img"
      aria-label={`Hora actual: ${now.toFormat("HH:mm")}`}
      data-time={now.toFormat("HH:mm")}
      style={{ top: `${1 + (minute * 56) / 60}px` }}
    >
      <span>{now.toFormat("HH:mm")}</span>
    </div>
  );
}
