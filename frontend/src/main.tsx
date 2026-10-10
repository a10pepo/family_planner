import { createRoot } from "react-dom/client";
import { initializeAuth } from "./auth";
import App from "./App";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);
root.render(
  <main className="welcome">
    <div className="brand-mark">◷</div>
    <h1>Preparando vuestro calendario…</h1>
  </main>,
);

initializeAuth()
  .then(({ auth, config }) => root.render(<App auth={auth} config={config} />))
  .catch((error: unknown) => {
    console.error("No se pudo inicializar Family Planner.", error);
    root.render(
      <main className="welcome">
        <div className="brand-mark">◷</div>
        <h1>El calendario está arrancando</h1>
        <p>Espera unos segundos y vuelve a intentarlo.</p>
        <button onClick={() => window.location.reload()}>
          Volver a intentar
        </button>
      </main>,
    );
  });
