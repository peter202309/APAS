import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  Search,
  Settings,
  Database,
  Activity,
  TrendingUp,
  AlertCircle,
  Loader2,
  CheckCircle2
} from 'lucide-react';
import TaskForm from './components/TaskForm';
import { scraperService } from './services/api';

const SidebarItem = ({ icon: Icon, label, active, onClick }) => (
  <div
    onClick={onClick}
    className={`flex items-center space-x-3 p-3 rounded-xl cursor-pointer transition-all duration-200 ${active
        ? 'bg-blue-600 text-white shadow-lg shadow-blue-200'
        : 'hover:bg-slate-100 text-slate-500 hover:text-slate-900'
      }`}
  >
    <Icon size={20} className={active ? 'text-white' : 'text-slate-400'} />
    <span className="font-bold text-sm tracking-tight">{label}</span>
  </div>
);

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isScraping, setIsScraping] = useState(false);
  const [logs, setLogs] = useState([]);
  const [results, setResults] = useState([]);

  // 轮询日志和结果
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const [newLogs, newResults] = await Promise.all([
          scraperService.getLogs(),
          scraperService.getResults()
        ]);
        setLogs(newLogs);
        setResults(newResults);
      } catch (err) {
        console.error("Failed to fetch updates:", err);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleLaunchTask = async (taskData) => {
    setIsScraping(true);
    try {
      // 确保 nights 是数字且不为空
      const cleanTask = {
        ...taskData,
        nights: taskData.nights || 7,
        adults: taskData.adults || 1
      };
      await scraperService.launchTask(cleanTask);
      setActiveTab('dashboard');
    } catch (err) {
      const errMsg = err.response?.data?.detail
        ? JSON.stringify(err.response.data.detail)
        : err.message;
      alert(`Launch Failed: ${errMsg}`);
    } finally {
      setIsScraping(false);
    }
  };

  const handleDownloadCSV = () => {
    window.open('http://localhost:8080/export/csv', '_blank');
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-64 p-6 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="flex items-center space-x-3 mb-10 px-2 leading-none">
          <div className="w-10 h-10 gradient-bg rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
            A
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-slate-800 block">APAS Pro</span>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Enterprise Flight AI</span>
          </div>
        </div>

        <nav className="space-y-2 flex-1">
          <SidebarItem
            icon={LayoutDashboard}
            label="Dashboard"
            active={activeTab === 'dashboard'}
            onClick={() => setActiveTab('dashboard')}
          />
          <SidebarItem
            icon={Search}
            label="Launch Scraper"
            active={activeTab === 'search'}
            onClick={() => setActiveTab('search')}
          />
          <SidebarItem
            icon={Database}
            label="Query History"
            active={activeTab === 'data'}
            onClick={() => setActiveTab('data')}
          />
          <SidebarItem
            icon={TrendingUp}
            label="AI Insights"
            active={activeTab === 'ai'}
            onClick={() => setActiveTab('ai')}
          />
        </nav>

        <div className="pt-6 border-t border-slate-100">
          <SidebarItem
            icon={Settings}
            label="System Config"
            active={activeTab === 'settings'}
            onClick={() => setActiveTab('settings')}
          />
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-10 relative">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 capitalize leading-tight">
              {activeTab.replace(/([A-Z])/g, ' $1').trim()}
            </h1>
            <p className="text-slate-500 mt-1 font-medium">Automatic Price Analysis & Strategy System</p>
          </div>

          <div className="flex items-center space-x-4">
            <div className="glass-card px-4 py-2 flex items-center space-x-3 border-none bg-white shadow-sm">
              <Activity className={isScraping || logs.length > 0 ? "text-emerald-500 animate-pulse" : "text-slate-300"} size={18} />
              <span className="text-sm font-bold text-slate-600 font-mono">NODES: {logs.length > 0 ? 'BUSY' : 'READY'}</span>
            </div>
            <div className="w-10 h-10 rounded-full gradient-bg border-4 border-white shadow-md flex items-center justify-center text-white font-bold">
              M
            </div>
          </div>
        </header>

        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="glass-card p-6 lg:col-span-2 flex flex-col min-h-[500px]">
              <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-slate-800">
                <TrendingUp className="text-primary-600" size={22} />
                Live Extraction Status
              </h3>
              <div className="flex-1 bg-slate-900 rounded-2xl p-6 font-mono text-sm overflow-y-auto text-emerald-400 border shadow-inner">
                {logs.length > 0 ? logs.map((log, idx) => (
                  <div key={idx} className="mb-2 flex gap-3">
                    <span className="text-slate-500 text-[10px] w-24">[{log.timestamp.split(' ')[1]}]</span>
                    <span className={log.level === 'ERROR' ? 'text-rose-400' : 'text-emerald-400'}>{log.message}</span>
                  </div>
                )) : (
                  <div className="h-full flex items-center justify-center text-slate-600 italic">
                    SYSTEM IDLE - Waiting for task initiation...
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-6">
              <div className="glass-card p-6">
                <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-slate-800">
                  <AlertCircle className="text-amber-500" size={22} />
                  MU Intelligence
                </h3>
                <div className="space-y-6">
                  <div className="p-4 bg-amber-50 border-1 border-amber-100 border-l-4 border-amber-400 shadow-sm rounded-r-xl">
                    <p className="text-[10px] font-black text-amber-800 uppercase tracking-widest bg-amber-200 w-max px-1.5 rounded mb-2">High Variance</p>
                    <p className="text-sm text-amber-900 font-semibold leading-relaxed">MU 5101: Price spiked 12% compared to last check. Competitors remain stable.</p>
                  </div>
                  <div className="p-4 bg-emerald-50 border-1 border-emerald-100 border-l-4 border-emerald-400 shadow-sm rounded-r-xl">
                    <p className="text-[10px] font-black text-emerald-800 uppercase tracking-widest bg-emerald-200 w-max px-1.5 rounded mb-2">Strategy Tip</p>
                    <p className="text-sm text-emerald-900 font-semibold leading-relaxed">Feb 20-22: Competitor sold out. Suggested markup: +15%.</p>
                  </div>
                </div>
              </div>

              <div className="glass-card p-6 bg-gradient-to-br from-primary-600 to-blue-700 text-white border-none shadow-blue-200">
                <h3 className="font-bold text-lg mb-4">Export Stats</h3>
                <p className="text-sm text-blue-100 mb-6 font-medium">Capture results for local archive or spreadsheet analysis.</p>
                <button
                  onClick={handleDownloadCSV}
                  className="w-full bg-white/10 hover:bg-white/20 border border-white/20 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all cursor-pointer"
                >
                  <Database size={18} /> Download CSV Report
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'data' && (
          <div className="space-y-6">
            <div className="glass-card p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-lg text-slate-800">Historical Scraper Results</h3>
                <button
                  onClick={handleDownloadCSV}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-md hover:bg-primary-700 transition-all"
                >
                  <Database size={16} /> Export All
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-widest font-black">
                      <th className="px-4 py-4">Time</th>
                      <th className="px-4 py-4">Route</th>
                      <th className="px-4 py-4">Filter</th>
                      <th className="px-4 py-4">Status</th>
                      <th className="px-4 py-4">Data Count</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {results.length > 0 ? results.map((res, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-4 text-sm font-medium text-slate-600">
                          {res.timestamp.split('T')[0]} {res.timestamp.split('T')[1].substring(0, 5)}
                        </td>
                        <td className="px-4 py-4 font-bold text-slate-800">
                          {res.task.origin} → {res.task.destination}
                        </td>
                        <td className="px-4 py-4 text-xs font-mono text-primary-600 font-black">
                          {res.task.routing_codes || '--'}
                        </td>
                        <td className="px-4 py-4">
                          <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-[10px] font-black rounded uppercase">Success</span>
                        </td>
                        <td className="px-4 py-4 font-bold text-slate-500">
                          {res.prices.length} points
                        </td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan="5" className="px-4 py-10 text-center text-slate-400 italic">No historical data found. Launch a task to begin.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
        {activeTab === 'search' && (
          <div className="max-w-2xl mx-auto">
            <div className="glass-card p-8 shadow-2xl relative overflow-hidden border-none text-left">
              <div className="absolute top-0 right-0 w-32 h-32 gradient-bg opacity-5 -mr-16 -mt-16 rounded-full" />
              <h2 className="text-2xl font-bold text-slate-800 mb-8 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center text-primary-600">
                  <Search size={22} />
                </div>
                Configure Research Task
              </h2>
              <TaskForm onSubmit={handleLaunchTask} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
