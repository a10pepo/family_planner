import { useMemo, useRef } from "react";
import FullCalendar from "@fullcalendar/react";
import timeGrid from "@fullcalendar/timegrid";
import interaction from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import es from "@fullcalendar/core/locales/es";
import type { EventDropArg } from "@fullcalendar/core";
import type { EventResizeDoneArg } from "@fullcalendar/interaction";
import { DateTime } from "luxon";
import type { CalendarEvent, FamilyEvent, Member } from "../api";
import { categories, type Category } from "../categories";
import { Avatar } from "../visuals";
import { CustomSymbol } from "./IconCatalog";
import { familyIcons } from "./FamilyEvents";

export function WeekCalendar({
  date,
  zone,
  now,
  members,
  events,
  familyEvents,
  hidden,
  toggle,
  addEvent,
  editEvent,
  editFamilyEvent,
  move,
  cancelOccurrence,
  busy,
  calendarMode = "week",
}: {
  date: DateTime;
  zone: string;
  now: DateTime;
  members: Member[];
  events: CalendarEvent[];
  familyEvents: FamilyEvent[];
  hidden: string[];
  toggle: (id: string) => void;
  addEvent: (memberId: string, start: string, end: string) => void;
  editEvent: (event: CalendarEvent) => void;
  editFamilyEvent: (day: string, event?: FamilyEvent) => void;
  move: (info: EventDropArg | EventResizeDoneArg) => void;
  cancelOccurrence: (event: CalendarEvent) => void;
  busy: boolean;
  calendarMode?: "day" | "week";
}) {
  const visible = members.filter((member) => !hidden.includes(member.id));
  const start =
    calendarMode === "day"
      ? date.toISODate()!
      : date.startOf("week").toISODate()!;
  const appointments = useMemo(
    () =>
      events.filter((event) =>
        members.some(
          (member) =>
            member.id === event.member_id && !hidden.includes(member.id),
        ),
      ),
    [events, members, hidden],
  );
  const calendarEvents = useMemo(
    () => [
      ...appointments.map((event) => ({
        id: event.id,
        title: event.title,
        start: event.starts_at,
        end: event.ends_at,
        backgroundColor: categories[event.category].color,
        textColor: categories[event.category].ink,
        borderColor: members.find((member) => member.id === event.member_id)!
          .color,
        extendedProps: {
          category: event.category,
          member_id: event.member_id,
          custom_icon_id: event.custom_icon_id,
          recurring_series_id: event.recurring_series_id,
          occurrence_date: event.occurrence_date,
          occurrence_time: event.occurrence_time,
        },
        editable: !event.recurring_series_id,
      })),
      ...familyEvents.map((event) => ({
        id: `family-${event.id}`,
        title: event.title,
        start: event.day,
        end: DateTime.fromISO(event.day, { zone })
          .plus({ days: 1 })
          .toISODate()!,
        allDay: true,
        editable: false,
        backgroundColor: "#f8e8da",
        textColor: "#896c53",
        borderColor: "#f8e8da",
        extendedProps: {
          family: true,
          icon: event.icon,
          custom_icon_id: event.custom_icon_id,
        },
      })),
    ],
    [appointments, familyEvents, members, zone],
  );
  const scroll = useRef(7 * 56);
  // Refresh FullCalendar when its feed changes; its option updates can retain
  // the previous array. Capture the scroll so edits and filters keep the hour.
  const calendarKey = `${calendarMode}-${start}-${JSON.stringify(calendarEvents)}`;
  return (
    <>
      <div
        className={`week-member-filters ${calendarMode === "day" ? "mobile-day-member-filters" : ""}`}
        role="group"
        aria-label={`Integrantes visibles ${calendarMode === "day" ? "en el día" : "en la semana"}`}
      >
        {members.map((member) => (
          <button
            key={member.id}
            className={`week-member-filter ${calendarMode === "day" ? "mobile-day-member-filter" : ""} ${hidden.includes(member.id) ? "hidden-member" : ""}`}
            aria-pressed={!hidden.includes(member.id)}
            aria-label={`Mostrar eventos de ${member.name}`}
            title={`${hidden.includes(member.id) ? "Mostrar" : "Ocultar"} eventos de ${member.name}`}
            onClick={() => toggle(member.id)}
          >
            <Avatar
              name={member.name}
              color={member.color}
              photo={member.photo_data}
            />
            <span>{member.name.split(/\s*[()]\s*/)[0]}</span>
          </button>
        ))}
      </div>
      {!visible.length && (
        <p className="week-filter-note" role="status">
          Todos los integrantes están ocultos. Toca una cara para mostrar sus
          eventos.
        </p>
      )}
      <div
        className={`week-viewport ${calendarMode === "day" ? "mobile-day-viewport" : ""}`}
      >
        <div
          className={`week-calendar ${calendarMode === "day" ? "mobile-day-calendar-grid" : ""}`}
          aria-label={
            calendarMode === "day"
              ? "Eventos del día"
              : "Semana de lunes a domingo"
          }
          onScrollCapture={(event) => {
            const target = event.target as HTMLElement;
            if (target.classList.contains("fc-scroller-liquid-absolute"))
              scroll.current = target.scrollTop;
          }}
        >
          <FullCalendar
            key={calendarKey}
            plugins={[timeGrid, interaction, luxonPlugin]}
            locale={es}
            timeZone={zone}
            initialDate={start}
            initialView={
              calendarMode === "day" ? "timeGridDay" : "timeGridWeek"
            }
            firstDay={1}
            weekends
            headerToolbar={false}
            height="100%"
            scrollTime={{ seconds: (scroll.current / 56) * 3600 }}
            allDaySlot
            allDayText="Todo el día"
            dayHeaderFormat={{ weekday: "short", day: "numeric" }}
            nowIndicator
            now={now.toISO()!}
            slotDuration="00:30:00"
            slotLabelInterval="01:00:00"
            slotLabelFormat={{
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }}
            eventTimeFormat={{
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }}
            editable={!busy}
            selectable={!busy && !!visible.length}
            selectMirror
            longPressDelay={350}
            eventMinHeight={44}
            events={calendarEvents}
            dateClick={(info) => {
              if (info.allDay) editFamilyEvent(info.dateStr);
              else if (visible[0])
                addEvent(
                  visible[0].id,
                  info.dateStr,
                  DateTime.fromISO(info.dateStr).plus({ hours: 1 }).toISO()!,
                );
            }}
            select={(info) => {
              if (info.allDay)
                editFamilyEvent(
                  DateTime.fromJSDate(info.start, { zone }).toISODate()!,
                );
              else if (visible[0])
                addEvent(visible[0].id, info.startStr, info.endStr);
              info.view.calendar.unselect();
            }}
            eventDrop={move}
            eventResize={move}
            eventClick={(info) => {
              if (info.event.extendedProps.family) {
                const family = familyEvents.find(
                  (event) => `family-${event.id}` === info.event.id,
                );
                if (family) editFamilyEvent(family.day, family);
              } else {
                if (info.event.extendedProps.recurring_series_id) {
                  const occurrence = events.find(
                    (event) => event.id === info.event.id,
                  );
                  if (occurrence) cancelOccurrence(occurrence);
                  return;
                }
                const event = events.find(
                  (event) => event.id === info.event.id,
                );
                if (event) editEvent(event);
              }
            }}
            eventContent={(info) => {
              const family = info.event.extendedProps.family;
              const person = members.find(
                (member) => member.id === info.event.extendedProps.member_id,
              );
              const symbol = family
                ? familyIcons[
                    info.event.extendedProps.icon as FamilyEvent["icon"]
                  ]
                : categories[info.event.extendedProps.category as Category];
              return (
                <div
                  className={`event-content week-event-content ${family ? "family-week-event" : ""}`}
                  title={`${info.event.title}${person ? ` · ${person.name}` : " · Toda la familia"}`}
                >
                  {!family && (
                    <span className="event-time">{info.timeText}</span>
                  )}
                  <strong>{info.event.title}</strong>
                  <span className="event-person">
                    {person ? person.name.split(/\s*[()]\s*/)[0] : "Familia"}
                  </span>
                  <span
                    className="event-category"
                    role="img"
                    aria-label={symbol.label}
                  >
                    <CustomSymbol
                      id={info.event.extendedProps.custom_icon_id}
                      fallback={symbol.icon}
                    />
                  </span>
                </div>
              );
            }}
          />
        </div>
      </div>
    </>
  );
}
