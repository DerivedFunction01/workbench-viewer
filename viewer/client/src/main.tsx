// Shell entry (Subplan 05). Keep the QueryClientProvider +
// hatch-space-root wrapper exactly: the SDK styles select on
// them (see the git repo viewer's main.tsx). The themes entry
// is the generated token CSS (Subplan 02) — local @imports
// inlined at build time; fonts are bundled woff2, never a
// runtime fetch. Appearance is applied to the document root
// before first paint so a saved mode/palette/density never
// flashes the default.
import { spaceQueryClient } from "@hatch/space-sdk/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { applyAppearance, loadAppearance } from "./lib/preferences";
import "./themes/index.css";
import "./themes/highlight.css";

applyAppearance(loadAppearance());

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
