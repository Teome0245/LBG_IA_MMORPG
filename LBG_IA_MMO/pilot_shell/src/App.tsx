import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { ShellLayout } from "./shell/ShellLayout";
import {
  CompanionView,
  DesktopView,
  HealthView,
  HomeView,
  JobsView,
  LyraView,
  MmoView,
  OpsView,
  PmView,
} from "./features/views";
import { LayoutProvider, SettingsProvider } from "./stores/context";
import { LogsProvider } from "./stores/logsContext";

export function App() {
  return (
    <SettingsProvider>
      <LayoutProvider>
        <LogsProvider>
          <HashRouter>
            <ShellLayout>
              <Routes>
              <Route path="/" element={<HomeView />} />
              <Route path="/ops" element={<OpsView />} />
              <Route path="/mmo" element={<MmoView />} />
              <Route path="/jobs" element={<JobsView />} />
              <Route path="/pm" element={<PmView />} />
              <Route path="/lyra" element={<LyraView />} />
              <Route path="/desktop" element={<DesktopView />} />
              <Route path="/health" element={<HealthView />} />
              <Route path="/companion" element={<CompanionView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </ShellLayout>
          </HashRouter>
        </LogsProvider>
      </LayoutProvider>
    </SettingsProvider>
  );
}
