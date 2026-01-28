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
  CheckCircle2,
  Upload,
  FileText,
  Sparkles,
  Trash2
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
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
  const [batches, setBatches] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [aiReport, setAiReport] = useState(null);
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);
  const [comparisonReport, setComparisonReport] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonMode, setComparisonMode] = useState('upload'); // 'upload' | 'select'
  const [selectedBatchIds, setSelectedBatchIds] = useState([]);
  const [customPrompt, setCustomPrompt] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);

  // 轮询日志和结果
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const [newLogs, newResults, newBatches] = await Promise.all([
          scraperService.getLogs(),
          scraperService.getResults(),
          scraperService.getBatches()
        ]);
        setLogs(newLogs);
        setResults(newResults);
        setBatches(newBatches);

        // Update selected batch details if open
        if (selectedBatch) {
          const updatedBatch = newBatches.find(b => b.id === selectedBatch.id);
          if (updatedBatch) setSelectedBatch(updatedBatch);
        }
      } catch (err) {
        console.error("Failed to fetch updates:", err);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Fetch AI Models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const models = await scraperService.getAiModels();
        setAiModels(models);
        if (models.length > 0) setSelectedModel(models[0]);
      } catch (err) {
        console.error("Failed to fetch AI models:", err);
      }
    };
    fetchModels();
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

  const handleBatchUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsScraping(true);
    try {
      const res = await scraperService.uploadBatch(file);
      alert(`Batch started! ID: ${res.batch_id} (${res.task_count} tasks)`);
      setActiveTab('dashboard');
    } catch (err) {
      alert(`Upload Failed: ${err.message}`);
    } finally {
      setIsScraping(false);
    }
  };

  const handleDownloadCSV = () => {
    window.open('http://localhost:8080/export/csv', '_blank');
  };

  const handleGenerateAI = async () => {
    setIsGeneratingAi(true);
    try {
      // Use most recent batch if available, otherwise global
      const recentBatch = batches.length > 0 ? batches[0] : null;
      const payload = recentBatch
        ? { batch_id: recentBatch.id, origin: "BATCH", destination: "ANALYSIS", ai_model_config: selectedModel }
        : { origin: "GLOBAL", destination: "MARKET", ai_model_config: selectedModel };

      const res = await scraperService.generateAIReport(payload);
      setAiReport(res.report);
    } catch (err) {
      alert("AI Generation Failed: " + err.message);
    } finally {
      setIsGeneratingAi(false);
    }
  };

  const handleCompareFiles = async (event) => {
    const files = event.target.files;
    if (!files || files.length < 2) {
      alert("Please select at least 2 CSV files for comparison.");
      return;
    }

    setIsComparing(true);
    try {
      const data = await scraperService.uploadComparisonFiles(files, customPrompt, selectedModel);
      setComparisonReport(data.report);
    } catch (error) {
      console.error("Comparison failed:", error);
      alert("Failed to generate comparison report.");
    } finally {
      setIsComparing(false);
    }
  };

  const handleCompareBatches = async () => {
    if (selectedBatchIds.length < 2) {
      alert("Please select at least 2 batches to compare.");
      return;
    }
    setIsComparing(true);
    try {
      const data = await scraperService.compareBatches(selectedBatchIds, customPrompt, selectedModel);
      setComparisonReport(data.report);
    } catch (error) {
      console.error("Batch comparison failed:", error);
      alert("Failed to compare batches: " + (error.response?.data?.detail || error.message));
    } finally {
      setIsComparing(false);
    }
  };

  const toggleBatchSelection = (id) => {
    if (selectedBatchIds.includes(id)) {
      setSelectedBatchIds(prev => prev.filter(bid => bid !== id));
    } else {
      if (selectedBatchIds.length >= 5) return alert("max 5 batches");
      setSelectedBatchIds(prev => [...prev, id]);
    }
  };

  const handleDeleteBatch = async (e, batchId) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete Batch #${batchId}?`)) {
      try {
        await scraperService.deleteBatch(batchId);
        const updatedBatches = await scraperService.getBatches();
        setBatches(updatedBatches);
        if (selectedBatchIds.includes(batchId)) {
          setSelectedBatchIds(prev => prev.filter(id => id !== batchId));
        }
      } catch (error) {
        console.error("Failed to delete batch:", error);
        alert("Failed to delete batch.");
      }
    }
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

        {activeTab === 'ai' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-full">
            {/* Left Controls */}
            <div className="space-y-6">
              <div className="glass-card p-6 bg-gradient-to-br from-indigo-900 to-purple-900 text-white border-none shadow-xl">
                <h3 className="font-bold text-xl mb-4 flex items-center gap-2">
                  <Sparkles className="text-yellow-300" />
                  AI Strategy Engine
                </h3>
                <p className="text-indigo-200 text-sm mb-6 leading-relaxed">
                  Powered by Gemini 1.5 Pro. Analyze your latest flight data to detect trends, anomalies, and pricing opportunities.
                </p>

                <div className="bg-white/10 rounded-xl p-4 mb-6 backdrop-blur-sm">
                  <p className="text-xs text-indigo-300 uppercase tracking-widest font-bold mb-2">AI Model Setup</p>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <Database size={16} className="text-indigo-400" />
                      <span className="font-mono text-sm font-bold">
                        {batches.length > 0 ? `Batch #${batches[0].id}` : 'Global History'}
                      </span>
                    </div>

                    <div className="pt-2">
                      <select
                        className="w-full bg-indigo-800/50 border border-indigo-400/30 rounded-lg p-2 text-xs font-bold outline-none text-white appearance-none cursor-pointer"
                        value={selectedModel ? `${selectedModel.provider}:${selectedModel.name}` : ''}
                        onChange={(e) => {
                          const [provider, name] = e.target.value.split(':');
                          setSelectedModel(aiModels.find(m => m.provider === provider && m.name === name));
                        }}
                      >
                        {aiModels.map((m, i) => (
                          <option key={i} value={`${m.provider}:${m.name}`}>{m.label}</option>
                        ))}
                        {aiModels.length === 0 && <option value="">No Models Available</option>}
                      </select>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleGenerateAI}
                  disabled={isGeneratingAi}
                  className={`w-full py-4 rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg
                                ${isGeneratingAi ? 'bg-indigo-800 text-indigo-400 cursor-not-allowed' : 'bg-white text-indigo-900 hover:bg-indigo-50'}`}
                >
                  {isGeneratingAi ? (
                    <>
                      <Loader2 className="animate-spin" /> Analyzing Data...
                    </>
                  ) : (
                    <>
                      <Sparkles size={18} /> Generate Strategy Report
                    </>
                  )}
                </button>
              </div>

              {/* New: Competitor Comparison Upload */}
              {/* New: Competitor Comparison Upload */}
              <div className="glass-card p-6 border-slate-200 shadow-sm bg-white">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-bold text-lg flex items-center gap-2 text-slate-800">
                    <Upload size={20} className="text-blue-500" />
                    Competitor Analysis
                  </h3>
                  <div className="flex bg-slate-100 rounded-lg p-1">
                    <button
                      className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${comparisonMode === 'upload' ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                      onClick={() => setComparisonMode('upload')}
                    >
                      Upload
                    </button>
                    <button
                      className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${comparisonMode === 'select' ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                      onClick={() => setComparisonMode('select')}
                    >
                      History
                    </button>
                  </div>
                </div>

                {comparisonMode === 'upload' ? (
                  <>
                    <p className="text-sm text-slate-500 mb-4">
                      Upload multiple CSVs (e.g., MU.csv, AC.csv) to generate a cross-airline strategy report.
                    </p>
                    <label className={`w-full border-2 border-dashed border-slate-300 rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer hover:bg-slate-50 transition-colors ${isComparing ? 'opacity-50 pointer-events-none' : ''}`}>
                      <input
                        type="file"
                        multiple
                        accept=".csv"
                        onChange={handleCompareFiles}
                        className="hidden"
                      />
                      {isComparing ? (
                        <>
                          <Loader2 className="animate-spin text-blue-500 mb-2" />
                          <span className="text-sm font-bold text-blue-600">Analyzing Files...</span>
                        </>
                      ) : (
                        <>
                          <FileText className="text-slate-400 mb-2" />
                          <span className="text-sm font-bold text-slate-600">Select 2+ Files</span>
                        </>
                      )}
                    </label>
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 block">Optional: Comparison Focus</label>
                      <textarea
                        className="w-full text-sm p-3 rounded-lg border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none bg-slate-50"
                        placeholder="E.g., Compare weekend pricing..."
                        rows="2"
                        value={customPrompt}
                        onChange={(e) => setCustomPrompt(e.target.value)}
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-slate-500 mb-4">
                      Select previous batches to compare via AI.
                    </p>
                    <div className="max-h-48 overflow-y-auto space-y-2 mb-4 pr-2 custom-scrollbar">
                      {batches.length > 0 ? batches.map(b => (
                        <div key={b.id}
                          className={`p-3 rounded-lg border cursor-pointer flex justify-between items-center transition-all ${selectedBatchIds.includes(b.id) ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-slate-100 hover:bg-slate-50'}`}
                          onClick={() => toggleBatchSelection(b.id)}
                        >
                          <div>
                            <div className="text-xs font-bold text-slate-700">Batch #{b.id}</div>
                            {/* Status Tag */}
                            <div className="flex items-center gap-2 mt-1">
                              <span className={`w-2 h-2 rounded-full ${b.status === 'completed' ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
                              <span className="text-[10px] text-slate-500 font-mono">{b.timestamp.split('T')[0]}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(e) => handleDeleteBatch(e, b.id)}
                              className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
                              title="Delete Batch"
                            >
                              <Trash2 size={14} />
                            </button>
                            {selectedBatchIds.includes(b.id) ?
                              <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">✓</div> :
                              <div className="w-5 h-5 rounded-full border border-slate-300"></div>
                            }
                          </div>
                        </div>
                      )) : <p className="text-xs text-slate-400 italic text-center py-4">No batch history available.</p>}
                    </div>
                    <div className="mb-4 pt-4 border-t border-slate-100">
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 block">Optional: Comparison Focus</label>
                      <textarea
                        className="w-full text-sm p-3 rounded-lg border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none bg-slate-50"
                        placeholder="E.g., Compare weekend pricing, or check if MU undercuts CA..."
                        rows="2"
                        value={customPrompt}
                        onChange={(e) => setCustomPrompt(e.target.value)}
                      />
                    </div>

                    <button
                      onClick={handleCompareBatches}
                      disabled={selectedBatchIds.length < 2 || isComparing}
                      className={`w-full py-3 rounded-xl font-bold text-sm transition-all flex items-center justify-center gap-2 ${selectedBatchIds.length < 2 || isComparing ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:shadow-lg hover:shadow-blue-200'}`}
                    >
                      {isComparing ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
                      {isComparing ? 'Comparing...' : `Compare (${selectedBatchIds.length}) Batches`}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Right Content - Report */}
            <div className="lg:col-span-2 glass-card p-8 min-h-[500px] flex flex-col relative overflow-y-auto">
              {/* Header Tabs to switch reports if both exist */}
              {(aiReport && comparisonReport) && (
                <div className="flex gap-4 mb-6 border-b border-slate-100">
                  <button onClick={() => setComparisonReport(null)} className="pb-2 font-bold text-slate-400 hover:text-slate-800">Single Analysis</button>
                  <button className="pb-2 font-bold text-indigo-600 border-b-2 border-indigo-600">Comparison Report</button>
                </div>
              )}

              {comparisonReport ? (
                <div className="prose prose-slate max-w-none">
                  <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                    <h2 className="text-2xl font-bold text-indigo-900 m-0">Competitive Landscape Report</h2>
                    <span className="text-xs text-slate-400 font-mono">Generated: {new Date().toLocaleTimeString()}</span>
                  </div>
                  <ReactMarkdown>{comparisonReport}</ReactMarkdown>
                  <button onClick={() => setComparisonReport(null)} className="mt-8 text-sm text-slate-400 underline">Back to Single Analysis</button>
                </div>
              ) : !aiReport ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-300">
                  <div className="w-24 h-24 rounded-full bg-slate-50 flex items-center justify-center mb-6">
                    <Sparkles size={40} className="text-slate-200" />
                  </div>
                  <p className="font-medium">Ready to analyze. Click "Generate" to start.</p>
                </div>
              ) : (
                <div className="prose prose-slate max-w-none">
                  <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                    <h2 className="text-2xl font-bold text-slate-800 m-0">Market Analysis Report</h2>
                    <span className="text-xs text-slate-400 font-mono">Generated: {new Date().toLocaleTimeString()}</span>
                  </div>
                  <ReactMarkdown>{aiReport}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        )
        }

        {
          activeTab === 'data' && (
            <div className="space-y-6">
              {!selectedBatch ? (
                // Batch List View
                <div className="glass-card p-6">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="font-bold text-lg text-slate-800">Batch History</h3>
                    <button
                      onClick={handleDownloadCSV}
                      className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-md hover:bg-primary-700 transition-all"
                    >
                      <Database size={16} /> Export All Results
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-widest font-black">
                          <th className="px-4 py-4">Batch ID</th>
                          <th className="px-4 py-4">Time</th>
                          <th className="px-4 py-4">Total Tasks</th>
                          <th className="px-4 py-4">Status</th>
                          <th className="px-4 py-4">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {batches.length > 0 ? batches.map((batch, i) => (
                          <tr key={i} className="hover:bg-slate-50 transition-colors cursor-pointer" onClick={() => setSelectedBatch(batch)}>
                            <td className="px-4 py-4 font-mono text-xs font-bold text-primary-600">
                              {batch.id}
                            </td>
                            <td className="px-4 py-4 text-sm font-medium text-slate-600">
                              {batch.timestamp.split('T')[0]} {batch.timestamp.split('T')[1].substring(0, 5)}
                            </td>
                            <td className="px-4 py-4 font-bold text-slate-800">
                              {batch.total_tasks} tasks
                            </td>
                            <td className="px-4 py-4">
                              <span className={`px-2 py-1 text-[10px] font-black rounded uppercase ${batch.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'
                                }`}>
                                {batch.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 flex gap-2 items-center">
                              <button className="text-xs font-bold text-slate-400 hover:text-primary-600" onClick={() => setSelectedBatch(batch)}>View Details &rarr;</button>

                              {/* Download CSV */}
                              {batch.status === 'completed' && (
                                <a
                                  href={scraperService.getBatchExportUrl(batch.id)}
                                  download
                                  onClick={(e) => e.stopPropagation()}
                                  className="p-1 text-slate-400 hover:text-blue-600"
                                  title="Download Batch CSV"
                                >
                                  <Database size={14} />
                                </a>
                              )}

                              {/* Delete Batch */}
                              <button
                                onClick={(e) => handleDeleteBatch(e, batch.id)}
                                className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                title="Delete Batch"
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        )) : (
                          <tr>
                            <td colSpan="5" className="px-4 py-10 text-center text-slate-400 italic">No batch history found. Upload a CSV to start.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                // Batch Detail View
                <div className="glass-card p-6">
                  <div className="flex justify-between items-center mb-6">
                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => setSelectedBatch(null)}
                        className="p-2 hover:bg-slate-100 rounded-full text-slate-500 transition-colors"
                      >
                        &larr; Back
                      </button>
                      <div>
                        <h3 className="font-bold text-lg text-slate-800">Batch {selectedBatch.id} Details</h3>
                        <p className="text-xs text-slate-500">{selectedBatch.timestamp}</p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 text-xs font-bold rounded-full uppercase ${selectedBatch.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                      {selectedBatch.status}
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-widest font-black">
                          <th className="px-4 py-4">Route</th>
                          <th className="px-4 py-4">Status</th>
                          <th className="px-4 py-4">Message / Error</th>
                          <th className="px-4 py-4">Data Count</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {selectedBatch.tasks.map((task, i) => (
                          <tr key={i} className="hover:bg-slate-50 transition-colors">
                            <td className="px-4 py-4 font-bold text-slate-800">
                              {task.origin} → {task.destination}
                            </td>
                            <td className="px-4 py-4">
                              <span className={`px-2 py-1 text-[10px] font-black rounded uppercase ${task.status === 'success' ? 'bg-emerald-100 text-emerald-700' :
                                task.status === 'failed' ? 'bg-rose-100 text-rose-700' :
                                  'bg-slate-100 text-slate-600'
                                }`}>
                                {task.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 text-xs font-mono">
                              <span className={task.status === 'failed' ? 'text-rose-600 font-bold' : 'text-slate-500'}>
                                {task.message}
                              </span>
                            </td>
                            <td className="px-4 py-4 font-bold text-slate-500">
                              {task.result_count}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )
        }
        {
          activeTab === 'search' && (
            <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
              <div className="md:col-span-2 glass-card p-8 shadow-2xl relative overflow-hidden border-none lg:p-10">
                <div className="absolute top-0 right-0 w-32 h-32 gradient-bg opacity-5 -mr-16 -mt-16 rounded-full" />
                <h2 className="text-2xl font-bold text-slate-800 mb-8 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center text-primary-600">
                    <Search size={22} />
                  </div>
                  Configure Research Task
                </h2>
                <TaskForm onSubmit={handleLaunchTask} />
              </div>

              <div className="space-y-6">
                <div className="glass-card p-8 border-dashed border-2 border-slate-200 bg-slate-50/50">
                  <div className="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-primary-600 mb-6">
                    <Upload size={24} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-800 mb-2">Batch CSV Upload</h3>
                  <p className="text-sm text-slate-500 mb-6">Upload a CSV file for multiple automated searches. System will process rows sequentially.</p>

                  <label className="block w-full">
                    <span className="sr-only">Choose CSV file</span>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={handleBatchUpload}
                      className="block w-full text-sm text-slate-500
                      file:mr-4 file:py-2.5 file:px-4
                      file:rounded-xl file:border-0
                      file:text-sm file:font-bold
                      file:bg-primary-600 file:text-white
                      hover:file:bg-primary-700
                      cursor-pointer"
                    />
                  </label>

                  <div className="mt-8 pt-6 border-t border-slate-200">
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Required Headers</p>
                    <div className="flex flex-wrap gap-2">
                      {['origin', 'destination', 'start_date'].map(h => (
                        <span key={h} className="px-2 py-1 bg-white border border-slate-200 rounded text-[10px] font-mono text-slate-600">{h}</span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="glass-card p-6 bg-slate-800 text-white border-none">
                  <div className="flex items-center gap-3 mb-4">
                    <FileText className="text-blue-400" size={20} />
                    <h4 className="font-bold">Template Info</h4>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Date format: <b>MM/DD/YYYY</b><br />
                    Optional headers: trip_type, routing_codes, cabin, nights.
                  </p>
                </div>
              </div>
            </div>
          )
        }
      </main >
    </div >
  );
}
