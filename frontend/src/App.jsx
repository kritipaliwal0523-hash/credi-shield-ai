import { useState } from 'react'
import { NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import './App.css'
import LoginPage from './pages/LoginPage'
import UploadPage from './pages/UploadPage'
import DashboardPage from './pages/DashboardPage'
import BuyerLookupPage from './pages/BuyerLookupPage'
import RiskTablePage from './pages/RiskTablePage'

function AppShell({ children, onLogout }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="logo-title">Buyer Reliability</div>
          <p className="brand-sub">MSME payment risk</p>
        </div>
        <nav className="nav-links">
          <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Dashboard
          </NavLink>
          <NavLink to="/upload" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Upload Data
          </NavLink>
          <NavLink to="/buyers" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Buyer Risk Table
          </NavLink>
          <NavLink to="/lookup" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Buyer Lookup
          </NavLink>
        </nav>
        <button className="logout-button" onClick={onLogout}>
          Logout
        </button>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <h1 className="topbar-title">Buyer Payment Reliability</h1>
        </header>
        <div className="page-content">{children}</div>
      </main>
    </div>
  )
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(localStorage.getItem('access_token')),
  )
  const navigate = useNavigate()

  const handleLogin = () => {
    setIsAuthenticated(true)
    navigate('/dashboard')
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    setIsAuthenticated(false)
    navigate('/')
  }

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
      </Routes>
    )
  }

  return (
    <AppShell onLogout={handleLogout}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/buyers" element={<RiskTablePage />} />
        <Route path="/lookup" element={<BuyerLookupPage />} />
        <Route path="*" element={<DashboardPage />} />
      </Routes>
    </AppShell>
  )
}

export default App
