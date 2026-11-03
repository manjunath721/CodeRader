import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "@/pages/HomePage";
import ProjectLayout from "@/components/ProjectLayout";
import DashboardPage from "@/pages/DashboardPage";
import DevelopersPage from "@/pages/DevelopersPage";
import DeveloperDetailPage from "@/pages/DeveloperDetailPage";
import ModulesPage from "@/pages/ModulesPage";
import ModuleDetailPage from "@/pages/ModuleDetailPage";
import KnowledgeGraphPage from "@/pages/KnowledgeGraphPage";
import SimulationPage from "@/pages/SimulationPage";
import RecommendationsPage from "@/pages/RecommendationsPage";
import AIAnalystPage from "@/pages/AIAnalystPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="developers" element={<DevelopersPage />} />
          <Route path="developers/:developerId" element={<DeveloperDetailPage />} />
          <Route path="modules" element={<ModulesPage />} />
          <Route path="modules/:moduleId" element={<ModuleDetailPage />} />
          <Route path="graph" element={<KnowledgeGraphPage />} />
          <Route path="simulation" element={<SimulationPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="ai" element={<AIAnalystPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
