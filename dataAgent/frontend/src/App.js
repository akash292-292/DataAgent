import { Routes, Route } from "react-router-dom";
import Dashboard from "./pages/dashboard";
import HomePage from "./pages/HomePage";
import ProfilingOptions from "./pages/profiling/options";   
import Preview from "./pages/profiling/preview";
import ProfilingRules from "./pages/profiling/rules";
import GP from './pages/profiling/GoogleDrivePicker';
import HomeButton from "./pages/profiling/HomeButton";
import OptionsMapping from './pages/mapping/optionsMapping';
import DriveSelection from "./pages/mapping/DriveSelection";
import FileSelection from "./pages/mapping/FileSelection";
import FinalLink from "./pages/mapping/FinalLink";
import PMLandingPage from "./pm/components/LandingPage";
import PMHomePage from "./pm/components/HomePage";
import PMProjectsPage from "./pm/components/ProjectsPage";
import PMGoogleCallback from "./pm/components/GoogleCallback";
import PMEmailLoginCallback from "./pm/components/EmailLoginCallback";
import { AuthProvider as PMAuthProvider } from "./pm/contexts/AuthContext";


function App() {
  return (
    <>
      <PMAuthProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<HomePage />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/profiling/options" element={<ProfilingOptions />} />
          <Route path="/profiling/preview" element={<Preview />} />
          <Route path="/profiling/rules" element={<ProfilingRules />} />
          <Route path="/profiling/GoogleDrivePicker" element={<GP />} />
          <Route path="/mapping/OptionsMapping" element={<OptionsMapping />} />
          <Route path="/DriveSelection" element={<DriveSelection />} />
          <Route path="/FileSelection" element={<FileSelection />} />
          <Route path="/FinalLink" element={<FinalLink />} />

          <Route path="/pm" element={<PMLandingPage />} />
          <Route path="/callback" element={<PMGoogleCallback />} />
          <Route path="/email-login" element={<PMEmailLoginCallback />} />
          <Route path="/home" element={<PMHomePage />} />
          <Route path="/projects" element={<PMProjectsPage />} />
        </Routes>
      </PMAuthProvider>
      <HomeButton />
    </>

  );
}

export default App;
