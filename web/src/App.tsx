import { Route, Routes } from "react-router-dom";

import { Shell } from "./components/Shell";
import { Anomalies } from "./pages/Anomalies";
import { Applications } from "./pages/Applications";
import { Copilot } from "./pages/Copilot";
import { Executive } from "./pages/Executive";
import { Forecast } from "./pages/Forecast";
import { Governance } from "./pages/Governance";
import { Integrations } from "./pages/Integrations";
import { Optimize } from "./pages/Optimize";
import { Showback } from "./pages/Showback";

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Executive />} />
        <Route path="applications" element={<Applications />} />
        <Route path="showback" element={<Showback />} />
        <Route path="forecast" element={<Forecast />} />
        <Route path="optimize" element={<Optimize />} />
        <Route path="anomalies" element={<Anomalies />} />
        <Route path="governance" element={<Governance />} />
        <Route path="copilot" element={<Copilot />} />
        <Route path="integrations" element={<Integrations />} />
      </Route>
    </Routes>
  );
}
