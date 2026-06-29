import { Routes, Route, Navigate } from "react-router-dom"

import { AuthProvider } from "@/contexts/AuthContext"
import LandingPage from "@/pages/landing"
import LoginPage from "@/pages/login"
import RegisterPage from "@/pages/register"
import DashboardPage from "@/pages/dashboard"
import ProjectDetailPage from "@/pages/ProjectDetail"
import RepoDetailPage from "@/pages/RepoDetail"
import PipelineGenerator from "@/pages/PipelineGenerator"
import PipelineHistory from "@/pages/PipelineHistory"
import PipelineCompare from "@/pages/PipelineCompare"
import PipelineVersionDetail from "@/pages/PipelineVersionDetail"
import RunDetail from "@/pages/RunDetail"
import SettingsPage from "@/pages/Settings"
import RunAnalysis from "@/pages/RunAnalysis"
import ProtectedRoute from "@/components/ProtectedRoute"
import ErrorBoundary from "@/components/ErrorBoundary"
import { useAuth } from "@/hooks/useAuth"

function HomeRedirect() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId"
          element={
            <ProtectedRoute>
              <ProjectDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId"
          element={
            <ProtectedRoute>
              <RepoDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines"
          element={
            <ProtectedRoute>
              <PipelineHistory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines/generate"
          element={
            <ProtectedRoute>
              <PipelineGenerator />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines/:version"
          element={
            <ProtectedRoute>
              <ErrorBoundary>
                <PipelineVersionDetail />
              </ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId"
          element={
            <ProtectedRoute>
              <RunDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines/:version/runs/:runId/analysis"
          element={
            <ProtectedRoute>
              <RunAnalysis />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/repos/:repoId/pipelines/compare"
          element={
            <ProtectedRoute>
              <PipelineCompare />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipelines"
          element={
            <ProtectedRoute>
              <PipelineHistory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  )
}

export default App
