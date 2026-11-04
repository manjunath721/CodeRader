import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import ProjectLayout from "@/components/ProjectLayout";
import DashboardPage from "@/pages/DashboardPage";
import DevelopersPage from "@/pages/DevelopersPage";
import DeveloperDetailPage from "@/pages/DeveloperDetailPage";
import ModulesPage from "@/pages/ModulesPage";
import ModuleDetailPage from "@/pages/ModuleDetailPage";
import KnowledgeGraphPage from "@/pages/KnowledgeGraphPage";
import SimulationPage from "@/pages/SimulationPage";
import RecommendationsPage from "@/pages/RecommendationsPage";
import HistoryPage from "@/pages/HistoryPage";
import ProjectSettingsPage from "@/pages/ProjectSettingsPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="developers" element={<DevelopersPage />} />
            <Route path="developers/:developerId" element={<DeveloperDetailPage />} />
            <Route path="modules" element={<ModulesPage />} />
            <Route path="modules/:moduleId" element={<ModuleDetailPage />} />
            <Route path="graph" element={<KnowledgeGraphPage />} />
            <Route path="simulation" element={<SimulationPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="settings" element={<ProjectSettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
