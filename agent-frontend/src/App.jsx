import React, { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Topbar from './components/Topbar';
import DetailPanel from './components/DetailPanel';
import Modal from './components/Modal';
import Toast from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';
import AppContext from './AppContext';
import { api } from './api';

// ── Lazy-loaded views ──
const Dashboard = lazy(() => import('./components/views/Dashboard'));
const Tasks = lazy(() => import('./components/views/Tasks'));
const Agents = lazy(() => import('./components/views/Agents'));
const Skills = lazy(() => import('./components/views/Skills'));
const MemoryView = lazy(() => import('./components/views/Memory'));
const Sessions = lazy(() => import('./components/views/Sessions'));
const Settings = lazy(() => import('./components/views/Settings'));
const WorkersView = lazy(() => import('./components/views/Workers'));
const CronJobsView = lazy(() => import('./components/views/CronJobs'));
const TokensView = lazy(() => import('./components/views/Tokens'));
const MonitorView = lazy(() => import('./components/views/Monitor'));
const OutputView = lazy(() => import('./components/views/OutputView'));
const ProfileView = lazy(() => import('./components/views/ProfileView'));
const AdminView = lazy(() => import('./components/views/AdminView'));

// ── Context ──
function PageLoader() {
  return (
    <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--text-muted)',fontSize:14}}>
      加载中...
    </div>
  );
}

function AppInner() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  const [tasks, setTasks] = useState([]);
  const [agents, setAgents] = useState([]);
  const [skills, setSkills] = useState([]);
  const [memory, setMemory] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [cronJobs, setCronJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const [detailType, setDetailType] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [modalType, setModalType] = useState(null);
  const [modalData, setModalData] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [agRes, tRes, sRes, kRes, wRes, cjRes] = await Promise.all([
          api.get('/agents/', { page_size: 50 }),
          api.get('/tasks/unified/'),
          api.get('/skills/', { page_size: 200 }),
          api.get('/knowledge/', { page_size: 50 }),
          api.get('/system/workers/'),
          api.get('/cron-jobs/', { page_size: 50 }),
        ]);
        setAgents(agRes.results || agRes || []);
        setTasks(tRes.results || tRes || []);
        setSkills(sRes.results || sRes || []);
        setMemory(kRes.results || kRes || []);
        setWorkers(wRes.workers || []);
        setCronJobs(cjRes.results || cjRes || []);
        try {
          const cRes = await api.get('/conversations/', { page_size: 50 });
          setSessions(cRes.results || cRes || []);
        } catch {}
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const addToast = useCallback((msg, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000);
  }, []);

  const openDetail = useCallback((type, data) => { setDetailType(type); setDetailData(data); }, []);
  const closeDetail = useCallback(() => { setDetailType(null); setDetailData(null); }, []);
  const openModal = useCallback((type, data = null) => { setModalType(type); setModalData(data); }, []);
  const closeModal = useCallback(() => { setModalType(null); setModalData(null); }, []);

  const ctx = { tasks, setTasks, agents, setAgents, skills, setSkills, memory, setMemory,
    sessions, setSessions, workers, cronJobs, loading, addToast, openDetail, openModal };

  return (
    <AppContext.Provider value={ctx}>
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-glow" aria-hidden="true" />
      <div className={`sidebar-backdrop${mobileOpen ? ' show' : ''}`} onClick={() => setMobileOpen(false)} />

      <Topbar onMobileOpen={() => setMobileOpen(true)} />

      <main className="main-content-v2">
        <div className="view-container">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/tasks" element={<Tasks openModal={openModal} />} />
                <Route path="/agents" element={<Agents />} />
                <Route path="/skills" element={<Skills />} />
                <Route path="/memory" element={<MemoryView />} />
                <Route path="/sessions" element={<Sessions />} />
                <Route path="/tokens" element={<TokensView />} />
                <Route path="/workers" element={<WorkersView />} />
                <Route path="/cron" element={<CronJobsView />} />
                <Route path="/settings" element={<Settings addToast={addToast} />} />
                <Route path="/monitor" element={<MonitorView />} />
                <Route path="/output" element={<OutputView />} />
                <Route path="/profile" element={<ProfileView />} />
                <Route path="/admin" element={<AdminView />} />
                <Route path="*" element={<Dashboard />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
      <DetailPanel type={detailType} data={detailData} onClose={closeDetail} />
      <Modal type={modalType} data={modalData} onClose={closeModal} />
      <Toast toasts={toasts} />
    </AppContext.Provider>
  );
}

export default function App() {
  return <AppInner />;
}
