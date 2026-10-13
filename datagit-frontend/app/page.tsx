'use client';

import React, { useState, useEffect, FormEvent, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL !== undefined
  ? process.env.NEXT_PUBLIC_API_URL
  : '';

interface Repository {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  description: string | null;
  language: string | null;
  stars: number;
  forks: number;
  open_issues: number;
  url: string;
  is_archived?: boolean;
  crawled_at?: string | null;
}

interface Commit {
  id: number;
  sha: string;
  author_name: string | null;
  author_email: string | null;
  message: string | null;
  committed_at: string | null;
  url: string | null;
}

interface Issue {
  id: number;
  github_number: number;
  title: string;
  state: string;
  author: string | null;
  comments_count: number;
  is_pull_request: boolean;
  created_at: string | null;
  closed_at: string | null;
  url: string | null;
}

interface RepositoryDetail extends Repository {
  default_branch?: string;
  is_fork?: boolean;
  is_private?: boolean;
  repo_created_at?: string | null;
  repo_updated_at?: string | null;
  repo_pushed_at?: string | null;
  commits: Commit[];
  issues: Issue[];
}

interface CrawlJob {
  id: number;
  target: string;
  target_type: string;
  depth: string;
  status: string;
  total_found: number;
  items_crawled: number;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

interface Insights {
  total_repositories: number;
  total_stars: number;
  total_forks: number;
  top_languages: { language: string; count: number }[];
}

interface RateLimitPool {
  token_masked: string;
  limit: number;
  remaining: number;
  seconds_until_reset: number;
  is_exhausted: boolean;
}

interface RateLimitStatus {
  active_tokens_count: number;
  total_remaining_requests: number;
  total_limit: number;
  pools: RateLimitPool[];
}

export default function DataGitApp() {
  const [view, setView] = useState<'signin' | 'signup' | 'dashboard'>('signin');
  const [dashboardTab, setDashboardTab] = useState<'explore' | 'jobs'>('explore');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [token, setToken] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState<string>('');

  // Dashboard Data State
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [totalFound, setTotalFound] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 24;
  const [insights, setInsights] = useState<Insights | null>(null);
  const [rateLimit, setRateLimit] = useState<RateLimitStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');
  const [minStars, setMinStars] = useState<number>(0);

  // Crawler Action State (Background Jobs)
  const [targetOrg, setTargetOrg] = useState<string>('google');
  const [crawlDepth, setCrawlDepth] = useState<string>('metadata');
  const [maxPages, setMaxPages] = useState<number>(3);
  const [isSubmittingJob, setIsSubmittingJob] = useState<boolean>(false);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [jobMessage, setJobMessage] = useState<string>('');
  const [jobError, setJobError] = useState<string>('');

  // Repository Detail Modal State
  const [selectedRepo, setSelectedRepo] = useState<RepositoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailModalOpen, setDetailModalOpen] = useState<boolean>(false);
  const [detailTab, setDetailTab] = useState<'commits' | 'issues'>('commits');

  // Authenticated API request helper with automatic 401 handling per Constitution
  const authFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers = new Headers(options.headers || {});
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const res = await fetch(url, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (res.status === 401) {
      // Token expired or invalid - force re-authentication
      localStorage.removeItem('datagit_token');
      localStorage.removeItem('datagit_email');
      setToken('');
      setView('signin');
      setErrorMsg('Your session has expired. Please sign in again.');
      throw new Error('Session expired');
    }
    return res;
  }, [token]);

  // Restore token from localStorage and verify session on startup
  useEffect(() => {
    const savedToken = localStorage.getItem('datagit_token');
    const savedEmail = localStorage.getItem('datagit_email');
    if (savedToken && savedEmail) {
      setToken(savedToken);
      setEmail(savedEmail);
      // Verify validity
      fetch(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${savedToken}` },
        credentials: 'include',
      })
        .then((res) => {
          if (res.ok) {
            setView('dashboard');
          } else {
            localStorage.removeItem('datagit_token');
            setToken('');
            setView('signin');
          }
        })
        .catch(() => {
          setView('dashboard');
        });
    }
  }, []);

  // Fetch Insights & Rate Limits on Dashboard load
  useEffect(() => {
    if (view === 'dashboard') {
      fetchInsights();
      fetchRateLimits();
    }
  }, [view]);

  // Poll Jobs list when on 'jobs' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'jobs') {
      fetchJobs();
      const interval = setInterval(fetchJobs, 3000);
      return () => clearInterval(interval);
    }
  }, [view, dashboardTab]);

  // Debounce search and filter updates
  useEffect(() => {
    if (view === 'dashboard') {
      const timer = setTimeout(() => {
        fetchRepositories();
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [view, searchTerm, selectedLanguage, minStars, page]);

  const fetchInsights = async () => {
    try {
      const res = await fetch(`${API_URL}/api/insights`);
      if (res.ok) {
        const data = await res.json();
        setInsights(data);
      }
    } catch {
      // API offline
    }
  };

  const fetchRateLimits = async () => {
    try {
      const res = await authFetch(`${API_URL}/api/ratelimit`);
      if (res.ok) {
        const data = await res.json();
        setRateLimit(data);
      }
    } catch {
      // Ignore
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await authFetch(`${API_URL}/api/jobs?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.items || []);
      }
    } catch {
      // Ignore
    }
  };

  const fetchRepositories = async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: offset.toString(),
        min_stars: minStars.toString(),
      });
      if (searchTerm.trim()) params.append('search', searchTerm.trim());
      if (selectedLanguage.trim()) params.append('language', selectedLanguage.trim());

      const res = await fetch(`${API_URL}/api/repos?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setRepositories(data.items || []);
        setTotalFound(data.total || 0);
      }
    } catch (err: unknown) {
      console.error('Failed to load repositories', err);
    } finally {
      setLoading(false);
    }
  };

  const openRepoDetails = async (repoId: number) => {
    setDetailLoading(true);
    setDetailModalOpen(true);
    try {
      const res = await fetch(`${API_URL}/api/repos/${repoId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedRepo(data);
      }
    } catch (err) {
      console.error('Failed to load repo detail', err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDeleteRepo = async (repoId: number) => {
    if (!window.confirm('Are you sure you want to delete this repository from the dataset?')) {
      return;
    }
    try {
      const res = await authFetch(`${API_URL}/api/repos/${repoId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDetailModalOpen(false);
        fetchRepositories();
        fetchInsights();
      }
    } catch (err) {
      console.error('Failed to delete repo', err);
    }
  };

  // Auth: Sign Up
  const handleSignUp = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const res = await fetch(`${API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      let data: any = null;
      try {
        data = await res.json();
      } catch {
        const text = await res.text().catch(() => '');
        data = { detail: text || `Server error (${res.status})` };
      }
      if (!res.ok) throw new Error(data?.detail || 'Sign up failed');
      setSuccessMsg('Account created successfully! Please sign in.');
      setView('signin');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  // Auth: Sign In
  const handleSignIn = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const res = await fetch(`${API_URL}/api/auth/signin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      let data: any = null;
      try {
        data = await res.json();
      } catch {
        const text = await res.text().catch(() => '');
        data = { detail: text || `Server error (${res.status})` };
      }
      if (!res.ok) throw new Error(data?.detail || 'Sign in failed');

      const authToken = data.access_token;
      setToken(authToken);
      localStorage.setItem('datagit_token', authToken);
      localStorage.setItem('datagit_email', email);
      setView('dashboard');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  const handleSignOut = async () => {
    try {
      await fetch(`${API_URL}/api/auth/signout`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      });
    } catch {
      // Ignore
    }
    localStorage.removeItem('datagit_token');
    localStorage.removeItem('datagit_email');
    setToken('');
    setView('signin');
  };

  // Dispatch Asynchronous Background Crawl Job
  const handleTriggerJob = async (e: FormEvent) => {
    e.preventDefault();
    if (!targetOrg) return;
    setIsSubmittingJob(true);
    setJobMessage('');
    setJobError('');
    try {
      const res = await authFetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: targetOrg, depth: crawlDepth, max_pages: maxPages }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to dispatch crawl job');

      setJobMessage(`Success! Background Crawl Job #${data.job_id} queued for ${data.target}.`);
      setDashboardTab('jobs');
      fetchJobs();
      fetchRateLimits();
    } catch (err: unknown) {
      setJobError(err instanceof Error ? err.message : 'Error launching job');
    } finally {
      setIsSubmittingJob(false);
    }
  };

  const handleCancelJob = async (jobId: number) => {
    try {
      const res = await authFetch(`${API_URL}/api/jobs/${jobId}/cancel`, {
        method: 'POST',
      });
      if (res.ok) {
        fetchJobs();
      }
    } catch (err) {
      console.error('Failed to cancel job', err);
    }
  };

  // Export with all active filters forwarded per Constitution
  const handleExport = (format: 'csv' | 'json' | 'parquet') => {
    const params = new URLSearchParams({ format });
    if (searchTerm.trim()) params.append('search', searchTerm.trim());
    if (selectedLanguage) params.append('language', selectedLanguage);
    if (minStars > 0) params.append('min_stars', minStars.toString());
    
    // Authenticated download via anchor or new window
    const url = `${API_URL}/api/export?${params.toString()}`;
    const authUrl = `${url}${token ? `&auth_token=${encodeURIComponent(token)}` : ''}`;
    window.open(authUrl, '_blank');
  };

  const totalPages = Math.max(1, Math.ceil(totalFound / pageSize));

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-40 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600 text-white font-black px-3 py-1 rounded-lg text-lg tracking-wider shadow-lg shadow-indigo-500/20">
            DATAGIT
          </div>
          <span className="text-slate-400 text-xs hidden sm:inline font-mono">
            v0.2.0 • AI-Ready Repository Intelligence
          </span>
        </div>

        {view === 'dashboard' && (
          <div className="flex items-center space-x-4">
            <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-medium">
              <button
                onClick={() => setDashboardTab('explore')}
                className={`px-3 py-1 rounded-md transition ${dashboardTab === 'explore' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                Explorer
              </button>
              <button
                onClick={() => setDashboardTab('jobs')}
                className={`px-3 py-1 rounded-md transition ${dashboardTab === 'jobs' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                Job Monitor {jobs.filter((j) => j.status === 'running').length > 0 && '⚡'}
              </button>
            </div>

            <span className="text-xs text-slate-400 hidden md:inline">
              <span className="text-indigo-400 font-semibold">{email}</span>
            </span>
            <button
              onClick={handleSignOut}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded-lg border border-slate-700 transition"
            >
              Sign Out
            </button>
          </div>
        )}
      </header>

      {/* Auth Screen */}
      {view !== 'dashboard' && (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl">
            <h2 className="text-2xl font-bold mb-2 text-white">
              {view === 'signin' ? 'Welcome to DataGit' : 'Create an Account'}
            </h2>
            <p className="text-slate-400 text-sm mb-6">
              {view === 'signin'
                ? 'Sign in to access repository intelligence, launch jobs, and export datasets'
                : 'Register to deploy and monitor crawler pipelines in compliance with the DataGit Constitution'}
            </p>

            {errorMsg && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">{errorMsg}</div>}
            {successMsg && <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm rounded-lg">{successMsg}</div>}

            <form onSubmit={view === 'signin' ? handleSignIn : handleSignUp} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Email Address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition text-sm"
                  placeholder="developer@example.com"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Password (min 8 characters)</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  maxLength={72}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition text-sm"
                  placeholder="••••••••"
                />
              </div>
              <button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-3 rounded-lg shadow-lg shadow-indigo-600/30 transition text-sm"
              >
                {view === 'signin' ? 'Sign In' : 'Create Account'}
              </button>
            </form>

            <p className="text-center text-xs text-slate-400 mt-6">
              {view === 'signin' ? "Don't have an account? " : 'Already registered? '}
              <button
                onClick={() => {
                  setView(view === 'signin' ? 'signup' : 'signin');
                  setErrorMsg('');
                  setSuccessMsg('');
                }}
                className="text-indigo-400 hover:underline font-medium"
              >
                {view === 'signin' ? 'Sign Up' : 'Sign In'}
              </button>
            </p>
          </div>
        </div>
      )}

      {/* Main Dashboard Screen */}
      {view === 'dashboard' && (
        <div className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
          {/* Metrics & Observability Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Indexed Repositories</span>
              <p className="text-2xl font-bold text-white mt-1">
                {insights ? insights.total_repositories.toLocaleString() : '—'}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Total Stargazers</span>
              <p className="text-2xl font-bold text-amber-400 mt-1">
                ⭐ {insights ? insights.total_stars.toLocaleString() : '—'}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">GitHub Rate Budget</span>
              <p className="text-2xl font-bold text-emerald-400 mt-1">
                {rateLimit ? `${rateLimit.total_remaining_requests.toLocaleString()} / ${rateLimit.total_limit.toLocaleString()}` : '—'}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm flex flex-col justify-between">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Streaming Export</span>
              <div className="flex gap-2 mt-2">
                <button onClick={() => handleExport('csv')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">CSV</button>
                <button onClick={() => handleExport('json')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">JSON</button>
                <button onClick={() => handleExport('parquet')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">Parquet</button>
              </div>
            </div>
          </div>

          {/* TAB 1: EXPLORER VIEW */}
          {dashboardTab === 'explore' && (
            <>
              {/* Search & Filter Toolbar */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col md:flex-row gap-3 items-center justify-between">
                <div className="flex-1 w-full flex flex-wrap sm:flex-nowrap gap-3">
                  <input
                    type="text"
                    placeholder="Search repository names, descriptions (FTS5 accelerated)..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                      setPage(1);
                    }}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white text-sm flex-1 focus:outline-none focus:border-indigo-500"
                  />
                  <select
                    value={selectedLanguage}
                    onChange={(e) => {
                      setSelectedLanguage(e.target.value);
                      setPage(1);
                    }}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">All Languages</option>
                    {insights?.top_languages.map((l) => (
                      <option key={l.language} value={l.language}>
                        {l.language} ({l.count})
                      </option>
                    ))}
                  </select>
                  <select
                    value={minStars}
                    onChange={(e) => {
                      setMinStars(Number(e.target.value));
                      setPage(1);
                    }}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                  >
                    <option value={0}>Any Stars</option>
                    <option value={100}>100+ Stars</option>
                    <option value={1000}>1,000+ Stars</option>
                    <option value={5000}>5,000+ Stars</option>
                  </select>
                </div>
                <div className="text-xs text-slate-400 whitespace-nowrap">
                  Showing {repositories.length} of {totalFound.toLocaleString()} repos
                </div>
              </div>

              {/* Repositories Grid */}
              {loading ? (
                <div className="text-center py-12 text-slate-500 text-sm">Loading repository intelligence...</div>
              ) : repositories.length === 0 ? (
                <div className="text-center py-12 bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 text-sm">
                  No repositories match the current filters.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {repositories.map((repo) => (
                    <div
                      key={repo.id}
                      onClick={() => openRepoDetails(repo.id)}
                      className="bg-slate-900 border border-slate-800 p-5 rounded-xl hover:border-indigo-500/50 cursor-pointer transition flex flex-col justify-between group"
                    >
                      <div>
                        <div className="flex justify-between items-start gap-2 mb-2">
                          <h3 className="font-semibold text-sm text-indigo-400 group-hover:text-indigo-300 truncate">
                            {repo.full_name}
                          </h3>
                          <span className="text-xs bg-slate-950 border border-slate-800 px-2 py-0.5 rounded-full text-amber-400 font-mono whitespace-nowrap">
                            ⭐ {repo.stars.toLocaleString()}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2 mb-4">
                          {repo.description || 'No description provided.'}
                        </p>
                      </div>
                      <div className="flex justify-between items-center text-xs text-slate-500 border-t border-slate-800/80 pt-3">
                        <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[11px]">
                          {repo.language || 'Unknown'}
                        </span>
                        <div className="flex gap-3">
                          <span>🍴 {repo.forks}</span>
                          <span>⚠️ {repo.open_issues}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Server-Side Pagination Bar */}
              <div className="flex items-center justify-between bg-slate-900 border border-slate-800 px-5 py-3 rounded-xl text-xs">
                <span className="text-slate-400">
                  Page <span className="text-white font-medium">{page}</span> of{' '}
                  <span className="text-white font-medium">{totalPages}</span>
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-700 transition"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-700 transition"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}

          {/* TAB 2: BACKGROUND JOBS MONITOR */}
          {dashboardTab === 'jobs' && (
            <div className="space-y-6">
              {/* Job Launcher Panel */}
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
                <h2 className="text-base font-semibold text-white mb-1">Queue Asynchronous Crawl Job</h2>
                <p className="text-slate-400 text-xs mb-4">
                  Jobs run in the background with pacing, jitter, and rate-limit persistence. Target can be an organization, user, or single repository (<code className="text-indigo-300">owner/repo</code>).
                </p>
                <form onSubmit={handleTriggerJob} className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="text"
                    placeholder="e.g. google, openai, or facebook/react..."
                    value={targetOrg}
                    onChange={(e) => setTargetOrg(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white flex-1 focus:outline-none focus:border-indigo-500 text-sm"
                  />
                  <select
                    value={crawlDepth}
                    onChange={(e) => setCrawlDepth(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-indigo-500 text-sm"
                  >
                    <option value="metadata">Depth: Metadata Only</option>
                    <option value="commits">Depth: Metadata + Commits</option>
                    <option value="issues">Depth: Metadata + Issues/PRs</option>
                    <option value="full">Depth: Full Depth</option>
                  </select>
                  <select
                    value={maxPages}
                    onChange={(e) => setMaxPages(Number(e.target.value))}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-indigo-500 text-sm"
                  >
                    <option value={1}>1 Page (100 Repos)</option>
                    <option value={3}>3 Pages (300 Repos)</option>
                    <option value={5}>5 Pages (500 Repos)</option>
                    <option value={10}>10 Pages (1,000 Repos)</option>
                  </select>
                  <button
                    type="submit"
                    disabled={isSubmittingJob}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-950 text-white font-medium px-6 py-2.5 rounded-lg shadow-lg shadow-indigo-600/20 text-sm transition"
                  >
                    {isSubmittingJob ? 'Queuing...' : 'Launch Job'}
                  </button>
                </form>
                {jobMessage && <p className="mt-3 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-2 rounded-lg">✔ {jobMessage}</p>}
                {jobError && <p className="mt-3 text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2 rounded-lg">✖ {jobError}</p>}
              </div>

              {/* Jobs Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h3 className="font-semibold text-sm text-white">Background Crawl Jobs History</h3>
                  <button onClick={fetchJobs} className="text-xs text-indigo-400 hover:underline">Refresh</button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 uppercase font-semibold border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3">ID</th>
                        <th className="px-4 py-3">Target</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3">Depth</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Progress</th>
                        <th className="px-4 py-3">Started</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {jobs.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                            No crawl jobs executed yet.
                          </td>
                        </tr>
                      ) : (
                        jobs.map((j) => (
                          <tr key={j.id} className="hover:bg-slate-800/40 transition">
                            <td className="px-4 py-3 font-mono text-slate-400">#{j.id}</td>
                            <td className="px-4 py-3 font-medium text-white">{j.target}</td>
                            <td className="px-4 py-3 text-slate-400 uppercase text-[11px]">{j.target_type}</td>
                            <td className="px-4 py-3 text-slate-400">{j.depth}</td>
                            <td className="px-4 py-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                  j.status === 'completed'
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                    : j.status === 'running'
                                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse'
                                    : j.status === 'failed'
                                    ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                                    : 'bg-slate-800 text-slate-400'
                                }`}
                              >
                                {j.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-slate-300">
                              {j.items_crawled} / {j.total_found > 0 ? j.total_found : '—'} repos
                            </td>
                            <td className="px-4 py-3 text-slate-500 text-[11px]">
                              {j.created_at ? new Date(j.created_at).toLocaleTimeString() : '—'}
                            </td>
                            <td className="px-4 py-3">
                              {j.status === 'running' || j.status === 'queued' ? (
                                <button
                                  onClick={() => handleCancelJob(j.id)}
                                  className="text-red-400 hover:text-red-300 text-xs font-medium"
                                >
                                  Cancel
                                </button>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* REPOSITORY DETAIL MODAL */}
      {detailModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 max-w-3xl w-full rounded-2xl shadow-2xl max-h-[85vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-800 flex justify-between items-start">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  {selectedRepo?.full_name || 'Repository Details'}
                  {selectedRepo?.stars !== undefined && (
                    <span className="text-xs bg-slate-950 border border-slate-800 px-2 py-0.5 rounded-full text-amber-400 font-mono">
                      ⭐ {selectedRepo.stars.toLocaleString()}
                    </span>
                  )}
                </h2>
                <p className="text-xs text-slate-400 mt-1">{selectedRepo?.description || 'No description provided.'}</p>
              </div>
              <button
                onClick={() => setDetailModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg font-bold px-2 py-1"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {detailLoading ? (
                <div className="text-center py-12 text-slate-500 text-sm">Loading repository intelligence...</div>
              ) : selectedRepo ? (
                <>
                  {/* Metadata Stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-500">Language</span>
                      <p className="text-white font-semibold mt-0.5">{selectedRepo.language || 'Unknown'}</p>
                    </div>
                    <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-500">Forks / Issues</span>
                      <p className="text-white font-semibold mt-0.5">🍴 {selectedRepo.forks} • ⚠️ {selectedRepo.open_issues}</p>
                    </div>
                    <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-500">Default Branch</span>
                      <p className="text-white font-semibold mt-0.5">{selectedRepo.default_branch || 'main'}</p>
                    </div>
                    <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-500">GitHub Link</span>
                      <p className="mt-0.5">
                        <a href={selectedRepo.url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline font-semibold">
                          Visit Repo ↗
                        </a>
                      </p>
                    </div>
                  </div>

                  {/* Tabs: Commits vs Issues */}
                  <div>
                    <div className="flex border-b border-slate-800 text-xs font-medium space-x-4 mb-3">
                      <button
                        onClick={() => setDetailTab('commits')}
                        className={`pb-2 border-b-2 transition ${detailTab === 'commits' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-white'}`}
                      >
                        Recent Commits ({selectedRepo.commits?.length || 0})
                      </button>
                      <button
                        onClick={() => setDetailTab('issues')}
                        className={`pb-2 border-b-2 transition ${detailTab === 'issues' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-white'}`}
                      >
                        Recent Issues & PRs ({selectedRepo.issues?.length || 0})
                      </button>
                    </div>

                    {detailTab === 'commits' && (
                      <div className="space-y-2">
                        {selectedRepo.commits?.length === 0 ? (
                          <p className="text-xs text-slate-500 py-4 text-center">No commits stored for this repository (crawled with depth=metadata).</p>
                        ) : (
                          selectedRepo.commits.map((c) => (
                            <div key={c.sha} className="bg-slate-950 border border-slate-800/80 p-3 rounded-lg text-xs flex justify-between items-start gap-3">
                              <div>
                                <p className="text-slate-200 font-medium line-clamp-1">{c.message || 'No commit message'}</p>
                                <span className="text-[11px] text-slate-500">{c.author_name} • {c.committed_at ? new Date(c.committed_at).toLocaleDateString() : ''}</span>
                              </div>
                              <span className="font-mono text-[10px] bg-slate-900 px-2 py-0.5 rounded text-indigo-400">{c.sha.slice(0, 7)}</span>
                            </div>
                          ))
                        )}
                      </div>
                    )}

                    {detailTab === 'issues' && (
                      <div className="space-y-2">
                        {selectedRepo.issues?.length === 0 ? (
                          <p className="text-xs text-slate-500 py-4 text-center">No issues stored for this repository (crawled with depth=metadata).</p>
                        ) : (
                          selectedRepo.issues.map((i) => (
                            <div key={i.id} className="bg-slate-950 border border-slate-800/80 p-3 rounded-lg text-xs flex justify-between items-start gap-3">
                              <div>
                                <p className="text-slate-200 font-medium line-clamp-1">
                                  #{i.github_number} {i.title}
                                </p>
                                <span className="text-[11px] text-slate-500">By {i.author || 'unknown'} • {i.is_pull_request ? 'Pull Request' : 'Issue'}</span>
                              </div>
                              <span className={`text-[10px] px-2 py-0.5 rounded uppercase font-semibold ${i.state === 'open' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}>
                                {i.state}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-950 border-t border-slate-800 flex justify-between items-center">
              {selectedRepo && (
                <button
                  onClick={() => handleDeleteRepo(selectedRepo.id)}
                  className="text-red-400 hover:text-red-300 text-xs font-semibold px-3 py-1.5 rounded border border-red-500/20 hover:border-red-500/40 transition"
                >
                  Delete Repository
                </button>
              )}
              <button
                onClick={() => setDetailModalOpen(false)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-4 py-2 rounded-lg font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}