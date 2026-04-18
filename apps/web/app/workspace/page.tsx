import { Suspense } from "react";

import PrismWorkspace from "../components/PrismWorkspace";

export default function WorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center bg-prism-bg text-sm text-slate-400">
          Loading workspace…
        </div>
      }
    >
      <PrismWorkspace />
    </Suspense>
  );
}
