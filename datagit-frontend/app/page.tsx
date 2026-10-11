'use client';

import React, { useState, useEffect, FormEvent } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

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
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [token, setToken] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState<string>('');

  // Dashboard Data State
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [totalFound, setTotalFound] = useState<number>(0);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [rateLimit, setRateLimit] = useState<RateLimitStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');
  const [minStars, setMinStars] = useState<number>(0);

  // Crawler Action State
  const [targetOrg, setTargetOrg] = useState<string>('google');
  const [crawlDepth, setCrawlDepth] = useState<string>('metadata');
  const [isCrawling, setIsCrawling] = useState<boolean>(false);
  const [crawlMessage, setCrawlMessage] = useState<string>('');
  const [crawlError, setCrawlError] = useState<string>('');

  // Restore token from localStorage
  useEffect(() => {
    const savedToken = localStorage.getItem('datagit_token');
    const savedEmail = localStorage.getItem('datagit_email');
    if (savedToken && savedEmail) {
      setToken(savedToken);
      setEmail(savedEmail);
      setView('dashboard');
    }
  }, []);

  // Fetch Insights & Rate Limits on Dashboard load
  useEffect(() => {
    if (view === 'dashboard') {
      fetchInsights();
      fetchRateLimits();
    }
  }, [view]);

  // Debounce search and filter updates
  useEffect(() => {
    if (view === 'dashboard') {
      const timer = setTimeout(() => {
        fetchRepositories();
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [view, searchTerm, selectedLanguage, minStars]);

  const fetchInsights = async () => {
    try {
      const res = await fetch(`${API_URL}/api/insights`);
      if (res.ok) {
        const data = await res.json();
        setInsights(data);
      }
    } catch {
      // API may not be active yet
    }
  };

  const fetchRateLimits = async () => {
    try {
      const res = await fetch(`${API_URL}/api/ratelimit`);
      if (res.ok) {
        const data = await res.json();
        setRateLimit(data);
      }
    } catch {
      // API may not be active yet
    }
  };

  const fetchRepositories = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: '30',
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

  // Auth: Sign Up
  const handleSignUp = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const res = await fetch(`${API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Sign up failed');
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
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Sign in failed');

      const authToken = data.access_token;
      setToken(authToken);
      localStorage.setItem('datagit_token', authToken);
      localStorage.setItem('datagit_email', email);
      setView('dashboard');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('datagit_token');
    localStorage.removeItem('datagit_email');
    setToken('');
    setView('signin');
  };

  // Run Crawler
  const handleTriggerCrawl = async (e: FormEvent) => {
    e.preventDefault();
    if (!targetOrg) return;
    setIsCrawling(true);
    setCrawlMessage('');
    setCrawlError('');
    try {
      const res = await fetch(`${API_URL}/api/crawl`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ target: targetOrg, depth: crawlDepth, max_pages: 3 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Crawling failed');

      setCrawlMessage(`Success! Indexed ${data.total_found} repositories for ${data.target}.`);
      fetchInsights();
      fetchRateLimits();
      fetchRepositories();
    } catch (err: unknown) {
      setCrawlError(err instanceof Error ? err.message : 'Error crawling target');
    } finally {
      setIsCrawling(false);
    }
  };

  const handleExport = (format: 'csv' | 'json' | 'parquet') => {
    const params = new URLSearchParams({ format });
    if (selectedLanguage) params.append('language', selectedLanguage);
    if (minStars > 0) params.append('min_stars', minStars.toString());
    const url = `${API_URL}/api/export?${params.toString()}`;
    window.open(url, '_blank');
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600 text-white font-black px-3 py-1 rounded-lg text-lg tracking-wider shadow-lg shadow-indigo-500/20">
            DATAGIT
          </div>
          <span className="text-slate-400 text-xs hidden sm:inline font-mono">v0.2.0 • AI Repository Intelligence</span>
        </div>

        {view === 'dashboard' && (
          <div className="flex items-center space-x-4">
            <span className="text-xs text-slate-400 hidden md:inline">
              User: <span className="text-indigo-400 font-semibold">{email}</span>
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

      {/* Auth Screens */}
      {view !== 'dashboard' && (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl">
            <h2 className="text-2xl font-bold mb-2 text-white">
              {view === 'signin' ? 'Welcome to DataGit' : 'Create an Account'}
            </h2>
            <p className="text-slate-400 text-sm mb-6">
              {view === 'signin' ? 'Sign in to access repository intelligence and datasets' : 'Register to deploy and monitor crawler pipelines'}
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
                <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Password</label>
                <input
                  type="password"
                  required
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
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Rate Limit Budget</span>
              <p className="text-2xl font-bold text-emerald-400 mt-1">
                {rateLimit ? `${rateLimit.total_remaining_requests.toLocaleString()} / ${rateLimit.total_limit.toLocaleString()}` : '—'}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm flex flex-col justify-between">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Export Dataset</span>
              <div className="flex gap-2 mt-2">
                <button onClick={() => handleExport('csv')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">CSV</button>
                <button onClick={() => handleExport('json')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">JSON</button>
                <button onClick={() => handleExport('parquet')} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-1.5 rounded font-medium border border-slate-700 transition">Parquet</button>
              </div>
            </div>
          </div>

          {/* Crawler Controller Panel */}
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
            <h2 className="text-base font-semibold text-white mb-3">Launch GitHub Ingestion Job</h2>
            <form onSubmit={handleTriggerCrawl} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                placeholder="Target user or organization (e.g. google, openai, vercel)..."
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
              <button
                type="submit"
                disabled={isCrawling}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-950 text-white font-medium px-6 py-2.5 rounded-lg shadow-lg shadow-indigo-600/20 text-sm transition"
              >
                {isCrawling ? 'Crawling GitHub...' : 'Run Ingestion'}
              </button>
            </form>
            {crawlMessage && (
              <p className="mt-3 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-2 rounded-lg">
                ✔ {crawlMessage}
              </p>
            )}
            {crawlError && (
              <p className="mt-3 text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2 rounded-lg">
                ✖ {crawlError}
              </p>
            )}
          </div>

          {/* Search & Filter Toolbar */}
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col md:flex-row gap-3 items-center justify-between">
            <div className="flex-1 w-full flex gap-3">
              <input
                type="text"
                placeholder="Search repository names, descriptions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white text-sm flex-1 focus:outline-none focus:border-indigo-500"
              />
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
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
                onChange={(e) => setMinStars(Number(e.target.value))}
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
                <div key={repo.id} className="bg-slate-900 border border-slate-800 p-5 rounded-xl hover:border-slate-700 transition flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start gap-2 mb-2">
                      <a
                        href={repo.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold text-sm text-indigo-400 hover:underline truncate"
                      >
                        {repo.full_name}
                      </a>
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
        </div>
      )}
    </main>
  );
}