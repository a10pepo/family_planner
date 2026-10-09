import type { Member, Notice, Occurrence } from "../api";
import { noticeIcons, taskIcons } from "../daily-icons";
import { Avatar, Icon } from "../visuals";
import { CustomSymbol } from "./IconCatalog";

export function MemberHeading({
  member,
  notices,
  tasks,
  busy,
  addEvent,
  editNotice,
  complete,
}: {
  member: Member;
  notices: Notice[];
  tasks: Occurrence[];
  busy: boolean;
  addEvent: () => void;
  editNotice: (notice?: Notice) => void;
  complete: (task: Occurrence) => void;
}) {
  const [name, nickname] = member.name.split(/\s*[()]\s*/);
  return (
    <div className="person-heading">
      <div className="member-head-main">
        <div
          className="task-strip"
          role="group"
          aria-label={`Tareas de ${name}`}
          style={{
            gridTemplateRows: `repeat(${Math.max(3, Math.ceil(tasks.length / 2))}, 68px)`,
          }}
        >
          {tasks.map((item) => (
            <button
              className={`task-token ${item.completed ? "done" : ""}`}
              key={item.task_id}
              aria-label={`${item.title}, ${name}`}
              aria-pressed={item.completed}
              title={`${item.title} · ${item.completed ? "Hecha" : "Pendiente"}`}
              disabled={busy}
              onClick={() => complete(item)}
            >
              <CustomSymbol
                id={item.custom_icon_id}
                fallback={taskIcons[item.icon].icon}
              />
              {item.completed && (
                <span className="task-tick">
                  <Icon name="check" />
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="person-identity">
          <Avatar
            name={member.name}
            color={member.color}
            photo={member.photo_data}
          />
          <span className="person-name">{name}</span>
          {nickname && <span className="person-nickname">{nickname}</span>}
          <button
            className="column-add"
            aria-label={`Añadir evento para ${name}`}
            title={`Añadir evento para ${name}`}
            onClick={addEvent}
          >
            ＋
          </button>
        </div>
      </div>
      <div
        className="notice-strip"
        role="group"
        aria-label={`Avisos de todo el día de ${name}`}
      >
        {notices.map((notice) => (
          <button
            className="notice-token"
            key={notice.id}
            aria-label={`${notice.title}, editar aviso de ${name}`}
            title={notice.title}
            onClick={() => editNotice(notice)}
          >
            <CustomSymbol
              id={notice.custom_icon_id}
              fallback={noticeIcons[notice.icon].icon}
            />
          </button>
        ))}
        <button
          className="daily-add"
          aria-label={`Añadir aviso de todo el día para ${name}`}
          title="Añadir aviso de todo el día"
          onClick={() => editNotice()}
        >
          ＋
        </button>
      </div>
    </div>
  );
}
