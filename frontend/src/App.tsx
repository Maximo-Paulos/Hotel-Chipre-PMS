import { Suspense } from "react";
import { RouterProvider } from "react-router-dom";

import { router } from "./router";

function App() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-slate-500">Cargando...</p>}>
      <RouterProvider router={router} />
    </Suspense>
  );
}

export default App;
