// STUB — Subplan 03 scaffold entry. The shell (rail, top bar, routing)
// lands in Subplan 05; this file only proves the client builds and
// typechecks. Keep the QueryClientProvider + hatch-space-root wrapper:
// the SDK styles select on them (see the git repo viewer's main.tsx).
import { spaceQueryClient } from "@hatch/space-sdk/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const rootEl = document.querySelector<HTMLElement>("[data-generated-space-root]");
if (!rootEl) {
  throw new Error("missing generated space root element");
}

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={spaceQueryClient}>
      <div className="hatch-space-root" data-hatch-space-root>
        <App />
      </div>
    </QueryClientProvider>
  </StrictMode>,
);
