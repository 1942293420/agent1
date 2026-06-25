import React, { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import Dashboard from './components/views/Dashboard';
import Tasks from './components/views/Tasks';
import Agents from './components/views/Agents';
import Skills from './components/views/Skills';
import MemoryView from './components/views/Memory';
import Sessions from './components/views/Sessions';
import Logs from './components/views/Logs';
import Settings from './components/views/Settings';
import WorkersView from './components/views/Workers';
import CronJobsView from './components/views/CronJobs';
import TokensView from './components/views/Tokens';
import MonitorView from './components/views/Monitor';
import OutputView from './components/views/OutputView';
import RealtimeDashboard from './components/views/RealtimeDashboard';
import HomePage from './components/views/HomePage';
import AdminView from './components/views/AdminView';
import DetailPanel from './components/DetailPanel';
import Modal from './components/Modal';
import Toast from './components/Toast';
import { api } from './api';

export default function App() {
  const [view, setView] = useState('home');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(220);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);

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

  // Sidebar resize
  const sidebarDragging = useRef(false);
  const sidebarStartX = useRef(0);
  const sidebarStartWidth = useRef(220);

  const handleSidebarResizeStart = useCallback((e) => {
    e.preventDefault();
    sidebarDragging.current = true;
    sidebarStartX.current = e.clientX;
    sidebarStartWidth.current = sidebarWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [sidebarWidth]);

  useEffect(() => {
    const onMove = (e) => {
      if (!sidebarDragging.current) return;
      const delta = e.clientX - sidebarStartX.current;
      setSidebarWidth(Math.max(180, Math.min(400, sidebarStartWidth.current + delta)));
    };
    const onUp = () => {
      if (sidebarDragging.current) {
        sidebarDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [agRes, tRes, sRes, kRes, wRes, cjRes, ptRes] = await Promise.all([
          api.get('/agents/', { page_size: 50 }),
          api.get('/tasks/', { page_size: 100, ordering: '-created_at' }),
          api.get('/skills/', { page_size: 200 }),
          api.get('/knowledge/', { page_size: 50 }),
          api.get('/system/workers/'),
          api.get('/cron-jobs/', { page_size: 50 }),
          api.get('/parent-tasks/'),
        ]);
        setAgents(agRes.results || agRes || []);
        const taskList = tRes.results || tRes || [];
        const ptList = Array.isArray(ptRes) ? ptRes : [];
        // 把父任务合并到任务列表（在前面）
        const merged = [
          ...ptList.map(pt => ({ ...pt, title: pt.user_message?.slice(0,60) || '(无消息)', _type: 'parent', _pt: pt })),
          ...taskList,
        ];
        setTasks(merged);
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

  const viewLabels = {
    dashboard:'仪表盘', tasks:'任务管理', agents:'Agent管理', skills:'Skill库',
    memory:'记忆管理', sessions:'会话中心', tokens:'Tokens', logs:'运行日志',
    workers:'Worker', cron:'定时任务', settings:'系统设置', monitor:'系统监控',
    admin:'用户管理',
  };

  const sharedProps = { tasks, setTasks, agents, setAgents, skills, setSkills, memory, setMemory,
    sessions, setSessions, workers, cronJobs, loading, addToast, openDetail, openModal, setView };

  return (
    <>
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-glow" aria-hidden="true" />
      <div className={`sidebar-backdrop${mobileOpen ? ' show' : ''}`} onClick={() => setMobileOpen(false)} />
      <Sidebar
        view={view} onViewChange={(v) => { setView(v); setMobileOpen(false); }}
        collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(prev => !prev)}
        mobileOpen={mobileOpen} onMobileOpen={() => setMobileOpen(true)}
        workers={workers}
        width={sidebarWidth}
        onResizeStart={handleSidebarResizeStart}
      />
      <main className="main-content">
        <Topbar view={view} viewLabels={viewLabels} addToast={addToast} onMobileOpen={() => setMobileOpen(true)} />
        <div className="view-container">
          {view === 'dashboard' && <Dashboard {...sharedProps} />}
          {view === 'tasks' && <Tasks {...sharedProps} openModal={openModal} />}
          {view === 'agents' && <Agents {...sharedProps} />}
          {view === 'skills' && <Skills {...sharedProps} />}
          {view === 'memory' && <MemoryView {...sharedProps} />}
          {view === 'sessions' && <Sessions {...sharedProps} />}
          {view === 'tokens' && <TokensView {...sharedProps} />}
          {view === 'logs' && <Logs addToast={addToast} />}
          {view === 'workers' && <WorkersView {...sharedProps} />}
          {view === 'cron' && <CronJobsView {...sharedProps} />}
          {view === 'settings' && <Settings addToast={addToast} />}
          {view === 'monitor' && <MonitorView />}
          {view === 'admin' && <AdminView addToast={addToast} />}
          {view === 'output' && <OutputView />}
          {view === 'realtime' && <RealtimeDashboard parentTaskId={selectedTaskId} />}
          {view === 'home' && <HomePage />}
        </div>
      </main>
      <DetailPanel type={detailType} data={detailData} onClose={closeDetail} {...sharedProps} />
      <Modal type={modalType} data={modalData} onClose={closeModal} {...sharedProps} />
      <Toast toasts={toasts} />
    </>
  );
}
