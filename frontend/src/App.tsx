import { Suspense } from "react";
import { RouterProvider } from "react-router-dom";

import { ActionStepUpProvider } from "./auth/ActionStepUpProvider";
import { router } from "./router";

function App() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-slate-500">Cargando...</p>}>
      <ActionStepUpProvider>
        <RouterProvider router={router} />
      </ActionStepUpProvider>
    </Suspense>
  );
}

export default App;
