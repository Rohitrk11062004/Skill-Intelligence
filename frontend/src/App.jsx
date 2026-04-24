import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';

// Raw Pages imported directly from Stitch conversion
import Login from './pages/Login.jsx';
import Registration from './pages/Registration.jsx';
import DashboardOverview from './pages/DashboardOverview.jsx';
import SkillAnalysis from './pages/SkillAnalysis.jsx';
import LearningRoadmap from './pages/LearningRoadmap.jsx';
import AssessmentQuiz from './pages/AssessmentQuiz.jsx';
import AssessmentResult from './pages/AssessmentResult.jsx';
import AssessmentsSummary from './pages/AssessmentsSummary.jsx';
import ProfileInfo from './pages/ProfileInfo.jsx';
import AccountSettings from './pages/AccountSettings.jsx';
import SkillTaxonomy from './pages/SkillTaxonomy.jsx';
import UploadJds from './pages/UploadJds.jsx';
import AdminDashboard from './pages/AdminDashboard.jsx';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0c0e14] flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RoleHome() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0c0e14] flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return user.is_manager ? <Navigate to="/admin" replace /> : <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Registration />} />
          
          {/* Main Flow Routes */}
          <Route path="/" element={<RoleHome />} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardOverview /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
          <Route path="/skill-analysis" element={<ProtectedRoute><SkillAnalysis /></ProtectedRoute>} />
          <Route path="/learning" element={<ProtectedRoute><LearningRoadmap /></ProtectedRoute>} />
          <Route path="/assessment" element={<ProtectedRoute><AssessmentQuiz /></ProtectedRoute>} />
          <Route path="/assessment/result" element={<ProtectedRoute><AssessmentResult /></ProtectedRoute>} />
          <Route path="/assessments-summary" element={<ProtectedRoute><AssessmentsSummary /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><ProfileInfo /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><AccountSettings /></ProtectedRoute>} />
          <Route path="/jds" element={<ProtectedRoute><UploadJds /></ProtectedRoute>} />
          <Route path="/taxonomy" element={<ProtectedRoute><SkillTaxonomy /></ProtectedRoute>} />
          
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
