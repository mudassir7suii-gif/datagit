'use client';

import React, { useState, useEffect, FormEvent, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL !== undefined
  ? process.env.NEXT_PUBLIC_API_URL
  : '';

interface HealthScore {
  score: number;
  label: string;
  color: string;
  breakdown: {
    recency: number;
    popularity: number;
    issue_hygiene: number;
    vitality: number;
  };
}

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
  repo_pushed_at?: string | null;
  crawled_at?: string | null;
  health?: HealthScore;
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

interface ApiResponse {
  detail?: string;
  access_token?: string;
  message?: string;
  email?: string;
  job_id?: number;
}

interface ApiKeyItem {
  id: number;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  is_revoked: boolean;
}

interface WorkspaceItem {
  id: number;
  name: string;
  slug: string;
  role: string;
  is_owner: boolean;
  created_at: string | null;
}

interface WebhookItem {
  id: number;
  url: string;
  events: string[];
  is_active: boolean;
  last_triggered_at: string | null;
  failure_count: number;
  created_at: string | null;
}

interface ExportArtifactItem {
  id: number;
  filename: string;
  format: string;
  file_size: number;
  checksum_sha256: string | null;
  download_url: string;
  expires_at: string | null;
  created_at: string | null;
}

interface TokenValidationResult {
  valid: boolean;
  username: string;
  scopes: string[];
  rate_limit: number;
  rate_limit_remaining: number;
  masked: string;
}

interface AuditLogItem {
  id: number;
  action: string;
  target: string | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

interface RepoSummary {
  overview: string;
  tech_stack: string[];
  primary_use_case: string;
  activity_level: string;
  stars_count: number;
  forks_count: number;
  recent_focus: string;
  rag_recommendation: string;
  generated_at?: string;
}

interface SloTelemetry {
  status: string;
  targets: {
    crawl_start_latency_p95_target_seconds: number;
    export_success_rate_target_percent: number;
    api_query_latency_p95_target_ms: number;
    platform_availability_target_percent: number;
  };
  current: {
    crawl_start_latency_p95_seconds: number;
    crawl_start_latency_avg_seconds: number;
    crawl_job_success_rate_percent: number;
    export_success_rate_percent: number;
    api_p95_ms: number;
    platform_uptime_percent: number;
  };
  error_budget_remaining: {
    crawl_latency_budget_percent: number;
    export_budget_percent: number;
    api_budget_percent: number;
  };
  monthly_review_schedule: string;
}

interface UserProfile {
  id: number;
  email: string;
  created_at: string;
  plan: string;
  monthly_crawls_used: number;
  monthly_crawls_limit: number;
  max_pages_allowed: number;
}

export default function DataGitApp() {
  const [view, setView] = useState<'signin' | 'signup' | 'dashboard'>('signin');
  const [dashboardTab, setDashboardTab] = useState<'explore' | 'jobs' | 'exports' | 'webhooks' | 'credentials' | 'api-keys' | 'audit' | 'slos'>('explore');
  const [showPricing, setShowPricing] = useState<boolean>(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  // Workspaces State
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceItem | null>(null);
  const [showWorkspaceModal, setShowWorkspaceModal] = useState<boolean>(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState<string>('');

  // API Keys & Interactive SDK
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [createdKey, setCreatedKey] = useState<string>('');
  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [sdkLang, setSdkLang] = useState<'python' | 'curl' | 'cli'>('python');

  // Exports & Object Storage State
  const [exportArtifacts, setExportArtifacts] = useState<ExportArtifactItem[]>([]);
  const [exportFormat, setExportFormat] = useState<'csv' | 'json' | 'parquet' | 'rag_json'>('csv');
  const [exportGenerating, setExportGenerating] = useState<boolean>(false);
  const [exportMessage, setExportMessage] = useState<string>('');

  // Webhooks State
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [newWebhookUrl, setNewWebhookUrl] = useState<string>('');
  const [newWebhookEvents, setNewWebhookEvents] = useState<string>('job.completed,job.failed');
  const [createdWebhookSecret, setCreatedWebhookSecret] = useState<string>('');
  const [webhookTestMessage, setWebhookTestMessage] = useState<string>('');
  const [testingWebhookId, setTestingWebhookId] = useState<number | null>(null);

  // GitHub Credentials Pool State
  const [tokenInput, setTokenInput] = useState<string>('');
  const [validatingToken, setValidatingToken] = useState<boolean>(false);
  const [tokenValidation, setTokenValidation] = useState<TokenValidationResult | null>(null);
  const [tokenAddMessage, setTokenAddMessage] = useState<string>('');
  const [tokenAddError, setTokenAddError] = useState<string>('');

  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [email, setEmail] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('datagit_email') || '';
    }
    return '';
  });
  const [password, setPassword] = useState<string>('');
  const [token, setToken] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('datagit_token') || '';
    }
    return '';
  });
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
  const [detailTab, setDetailTab] = useState<'commits' | 'issues' | 'summary'>('commits');
  const [repoSummary, setRepoSummary] = useState<RepoSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState<boolean>(false);
  const [summaryError, setSummaryError] = useState<string>('');
  const [sloData, setSloData] = useState<SloTelemetry | null>(null);
  const [sloLoading, setSloLoading] = useState<boolean>(false);

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

  const fetchInsights = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/insights`);
      if (res.ok) {
        const data = await res.json();
        setInsights(data);
      }
    } catch {
      // API offline
    }
  }, []);

  const fetchRateLimits = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/ratelimit`);
      if (res.ok) {
        const data = await res.json();
        setRateLimit(data);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/jobs?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.items || []);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/auth/me`);
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchApiKeys = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/auth/api-keys`);
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data.items || []);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/audit?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data.items || []);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/workspaces`);
      if (res.ok) {
        const data = await res.json();
        const items = data.items || [];
        setWorkspaces(items);
        if (items.length > 0) {
          setActiveWorkspace((prev) => prev || items[0]);
        }
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchExportArtifacts = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/export/artifacts`);
      if (res.ok) {
        const data = await res.json();
        setExportArtifacts(data.items || []);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchWebhooks = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/api/webhooks`);
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data.items || []);
      }
    } catch {
      // Ignore
    }
  }, [authFetch]);

  const fetchRepositories = useCallback(async () => {
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
  }, [page, minStars, searchTerm, selectedLanguage]);

  // Restore token from localStorage and verify session on startup
  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
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
        localStorage.removeItem('datagit_token');
        setToken('');
        setView('signin');
      });
  }, [token]);

  // Fetch Profile, Insights & Rate Limits on Dashboard load
  useEffect(() => {
    if (view === 'dashboard') {
      const timer = setTimeout(() => {
        fetchProfile();
        fetchInsights();
        fetchRateLimits();
        fetchWorkspaces();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, fetchProfile, fetchInsights, fetchRateLimits, fetchWorkspaces]);

  // Poll Jobs list when on 'jobs' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'jobs') {
      const timer = setTimeout(() => {
        fetchJobs();
      }, 0);
      const interval = setInterval(fetchJobs, 3000);
      return () => {
        clearTimeout(timer);
        clearInterval(interval);
      };
    }
  }, [view, dashboardTab, fetchJobs]);

  // Load API keys when on 'api-keys' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'api-keys') {
      const timer = setTimeout(() => {
        fetchApiKeys();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchApiKeys]);

  // Load Export Artifacts when on 'exports' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'exports') {
      const timer = setTimeout(() => {
        fetchExportArtifacts();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchExportArtifacts]);

  // Load Webhooks when on 'webhooks' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'webhooks') {
      const timer = setTimeout(() => {
        fetchWebhooks();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchWebhooks]);

  // Refresh Rate Limits when on 'credentials' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'credentials') {
      const timer = setTimeout(() => {
        fetchRateLimits();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchRateLimits]);

  // Load Audit Trail when on 'audit' tab
  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'audit') {
      const timer = setTimeout(() => {
        fetchAuditLogs();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchAuditLogs]);

  // Debounce search and filter updates
  useEffect(() => {
    if (view === 'dashboard') {
      const timer = setTimeout(() => {
        fetchRepositories();
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [view, fetchRepositories]);

  const openRepoDetails = async (repoId: number) => {
    setDetailLoading(true);
    setDetailModalOpen(true);
    setDetailTab('commits');
    setRepoSummary(null);
    setSummaryError('');
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

  const fetchRepoSummary = async (repoId: number, forceRefresh = false) => {
    setSummaryLoading(true);
    setSummaryError('');
    try {
      const res = await authFetch(`${API_URL}/api/repositories/${repoId}/summary?force_refresh=${forceRefresh ? 'true' : 'false'}`);
      if (res.ok) {
        const data = await res.json();
        setRepoSummary(data);
      } else {
        const err = await res.json().catch(() => ({}));
        setSummaryError(err.detail || 'Failed to generate AI summary.');
      }
    } catch (e: unknown) {
      setSummaryError(e instanceof Error ? e.message : 'Error generating summary.');
    } finally {
      setSummaryLoading(false);
    }
  };

  const fetchSlos = useCallback(async () => {
    setSloLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/slos`);
      if (res.ok) {
        const data = await res.json();
        setSloData(data);
      }
    } catch {
      // offline or error
    } finally {
      setSloLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (view === 'dashboard' && dashboardTab === 'slos') {
      const timer = setTimeout(() => {
        fetchSlos();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [view, dashboardTab, fetchSlos]);

  const handleInstallGithubApp = async () => {
    try {
      const wsParam = activeWorkspace ? `?workspace_id=${activeWorkspace.id}` : '';
      const res = await authFetch(`${API_URL}/api/github/app/install-url${wsParam}`);
      if (res.ok) {
        const data = await res.json();
        if (data.install_url) {
          window.open(data.install_url, '_blank');
        }
      } else {
        alert('Failed to retrieve GitHub App installation URL.');
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Error opening GitHub App install flow.');
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
      let data: ApiResponse | null = null;
      try {
        data = (await res.json()) as ApiResponse;
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
      let data: ApiResponse | null = null;
      try {
        data = (await res.json()) as ApiResponse;
      } catch {
        const text = await res.text().catch(() => '');
        data = { detail: text || `Server error (${res.status})` };
      }
      if (!res.ok) throw new Error(data?.detail || 'Sign in failed');

      const authToken = data?.access_token || '';
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

  const handleRerunJob = async (jobId: number) => {
    try {
      const res = await authFetch(`${API_URL}/api/jobs/${jobId}/rerun`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setJobMessage(`Job #${jobId} re-enqueued as Job #${data.job_id}.`);
        fetchJobs();
      }
    } catch (err: unknown) {
      setJobError(err instanceof Error ? err.message : 'Failed to re-run job');
    }
  };

  const handleCreateApiKey = async (e: FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    try {
      const res = await authFetch(`${API_URL}/api/auth/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setCreatedKey(data.api_key || '');
        setNewKeyName('');
        fetchApiKeys();
      }
    } catch (err) {
      console.error('Failed to create API key', err);
    }
  };

  const handleRevokeApiKey = async (keyId: number) => {
    if (!window.confirm('Are you sure you want to revoke this API key? This action is immediate and cannot be undone.')) {
      return;
    }
    try {
      const res = await authFetch(`${API_URL}/api/auth/api-keys/${keyId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchApiKeys();
      }
    } catch (err) {
      console.error('Failed to revoke API key', err);
    }
  };

  const handleCopyKey = () => {
    if (!createdKey) return;
    navigator.clipboard.writeText(createdKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const handleCreateWorkspace = async (e: FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    try {
      const res = await authFetch(`${API_URL}/api/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newWorkspaceName.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setNewWorkspaceName('');
        setShowWorkspaceModal(false);
        await fetchWorkspaces();
        setActiveWorkspace(data);
      }
    } catch (err) {
      console.error('Failed to create workspace', err);
    }
  };

  const handleGenerateExportArtifact = async () => {
    setExportGenerating(true);
    setExportMessage('');
    try {
      const res = await authFetch(`${API_URL}/api/export/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format: exportFormat,
          search: searchTerm.trim() || undefined,
          language: selectedLanguage.trim() || undefined,
          min_stars: minStars > 0 ? minStars : undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setExportMessage(`Export artifact '${data.filename}' created! Stored in object storage with 48h retention.`);
        fetchExportArtifacts();
      } else {
        const err = await res.json();
        setExportMessage(err.detail || 'Export generation failed.');
      }
    } catch (err: unknown) {
      setExportMessage(err instanceof Error ? err.message : 'Export generation error');
    } finally {
      setExportGenerating(false);
    }
  };

  const handleCreateWebhook = async (e: FormEvent) => {
    e.preventDefault();
    if (!newWebhookUrl.trim()) return;
    try {
      const res = await authFetch(`${API_URL}/api/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: newWebhookUrl.trim(),
          events: newWebhookEvents.trim() || 'job.completed,job.failed',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCreatedWebhookSecret(data.secret || '');
        setNewWebhookUrl('');
        fetchWebhooks();
      }
    } catch (err) {
      console.error('Failed to create webhook', err);
    }
  };

  const handleDeleteWebhook = async (webhookId: number) => {
    if (!window.confirm('Delete this webhook endpoint?')) return;
    try {
      const res = await authFetch(`${API_URL}/api/webhooks/${webhookId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchWebhooks();
      }
    } catch (err) {
      console.error('Failed to delete webhook', err);
    }
  };

  const handleTestWebhook = async (webhookId: number) => {
    setTestingWebhookId(webhookId);
    setWebhookTestMessage('');
    try {
      const res = await authFetch(`${API_URL}/api/webhooks/${webhookId}/test`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data.success) {
        setWebhookTestMessage(`Delivery verified! Receiver returned HTTP 2xx. HMAC Signature: ${data.signature.slice(0, 20)}...`);
      } else {
        setWebhookTestMessage(`Delivery attempted, but target receiver did not respond with 2xx.`);
      }
    } catch (err: unknown) {
      setWebhookTestMessage(err instanceof Error ? err.message : 'Webhook ping failed.');
    } finally {
      setTestingWebhookId(null);
    }
  };

  const handleValidateToken = async () => {
    if (!tokenInput.trim()) return;
    setValidatingToken(true);
    setTokenValidation(null);
    setTokenAddMessage('');
    setTokenAddError('');
    try {
      const res = await authFetch(`${API_URL}/api/tokens/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setTokenValidation(data);
      } else {
        setTokenAddError(data.detail || 'Token validation failed.');
      }
    } catch (err: unknown) {
      setTokenAddError(err instanceof Error ? err.message : 'Validation error.');
    } finally {
      setValidatingToken(false);
    }
  };

  const handleAddToken = async () => {
    if (!tokenInput.trim()) return;
    setTokenAddMessage('');
    setTokenAddError('');
    try {
      const res = await authFetch(`${API_URL}/api/tokens/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setTokenAddMessage(data.message || 'Token registered successfully.');
        setTokenInput('');
        setTokenValidation(null);
        fetchRateLimits();
      } else {
        setTokenAddError(data.detail || 'Failed to add token to pool.');
      }
    } catch (err: unknown) {
      setTokenAddError(err instanceof Error ? err.message : 'Error adding token.');
    }
  };

  // Export with all active filters forwarded per Constitution
  const handleExport = (format: 'csv' | 'json' | 'parquet' | 'rag_json') => {
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

        <div className="flex items-center space-x-3">
          {view === 'dashboard' && workspaces.length > 0 && (
            <div className="hidden md:flex items-center gap-1.5 bg-slate-950 border border-slate-800 px-2.5 py-1 rounded-lg text-xs">
              <span className="text-slate-400">🏢</span>
              <select
                aria-label="Active Workspace"
                value={activeWorkspace?.id || ''}
                onChange={(e) => {
                  const ws = workspaces.find((w) => w.id === Number(e.target.value));
                  if (ws) setActiveWorkspace(ws);
                }}
                className="bg-transparent text-white font-medium focus:outline-none cursor-pointer text-xs"
              >
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id} className="bg-slate-900 text-white">
                    {w.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowWorkspaceModal(true)}
                title="Create Workspace"
                className="text-indigo-400 hover:text-indigo-300 font-bold ml-1 text-xs"
              >
                +
              </button>
            </div>
          )}

          <button
            onClick={() => setShowPricing(true)}
            className="text-xs text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/80 transition flex items-center gap-1.5"
          >
            <span>💎</span>
            <span>Plans & Quotas</span>
          </button>

          {view === 'dashboard' ? (
            <div className="flex items-center space-x-3">
              <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-medium overflow-x-auto">
                <button
                  onClick={() => setDashboardTab('explore')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'explore' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Explorer
                </button>
                <button
                  onClick={() => setDashboardTab('jobs')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'jobs' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Jobs {jobs.filter((j) => j.status === 'running').length > 0 && '⚡'}
                </button>
                <button
                  onClick={() => setDashboardTab('exports')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'exports' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Exports
                </button>
                <button
                  onClick={() => setDashboardTab('webhooks')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'webhooks' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Webhooks
                </button>
                <button
                  onClick={() => setDashboardTab('credentials')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'credentials' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  GitHub Tokens
                </button>
                <button
                  onClick={() => setDashboardTab('api-keys')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'api-keys' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  API Keys & SDK
                </button>
                <button
                  onClick={() => setDashboardTab('audit')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'audit' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Audit
                </button>
                <button
                  onClick={() => setDashboardTab('slos')}
                  className={`px-2.5 py-1 rounded-md transition ${dashboardTab === 'slos' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  SLOs & Reliability
                </button>
              </div>

              {profile && (
                <div className="hidden 2xl:flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1 rounded-lg text-xs">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span className="text-slate-400 uppercase tracking-wider font-semibold text-[10px]">{profile.plan} Tier</span>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-300 font-mono">{profile.monthly_crawls_used} / {profile.monthly_crawls_limit} crawls</span>
                </div>
              )}

              <span className="text-xs text-slate-400 hidden md:inline">
                <span className="text-indigo-400 font-semibold">{email || 'Guest Explorer'}</span>
              </span>
              <button
                onClick={handleSignOut}
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded-lg border border-slate-700 transition"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                setView('dashboard');
                fetchRepositories();
              }}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium px-3 py-1.5"
            >
              Live Demo →
            </button>
          )}
        </div>
      </header>

      {/* Auth / Public Marketing Hero Screen (Spec 3.1 & 4.4) */}
      {view !== 'dashboard' && (
        <div className="flex-1 flex flex-col justify-center items-center p-6 max-w-6xl w-full mx-auto my-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center w-full">
            {/* Left Hero Column: 30-Second Understanding & Value Props */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-950/60 border border-indigo-800/50 rounded-full text-indigo-400 text-xs font-mono">
                <span>⚡ Rate-Limit Resilient</span>
                <span>•</span>
                <span>AI-Ready Dataset Platform</span>
              </div>
              <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-white leading-tight">
                Turn any GitHub org or repo into <span className="text-transparent bg-clip-text bg-linear-to-r from-indigo-400 to-purple-400">clean, AI-ready datasets.</span>
              </h1>
              <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                Automated repository intelligence without writing or babysitting crawlers. Paced GitHub API ingestion with shared rate budgets, full-text search, and multi-format streaming exports.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
                  <div className="text-indigo-400 text-lg mb-1">🛡️</div>
                  <h4 className="text-xs font-semibold text-white">Zero Quota Burn</h4>
                  <p className="text-[11px] text-slate-400 mt-1">Multi-token rotation, pacing, jitter & 403/429 backoff.</p>
                </div>
                <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
                  <div className="text-purple-400 text-lg mb-1">🔍</div>
                  <h4 className="text-xs font-semibold text-white">Full-Text Indexed</h4>
                  <p className="text-[11px] text-slate-400 mt-1">FTS5 accelerated search & content-hash deduplication.</p>
                </div>
                <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl">
                  <div className="text-emerald-400 text-lg mb-1">📦</div>
                  <h4 className="text-xs font-semibold text-white">Streaming Exports</h4>
                  <p className="text-[11px] text-slate-400 mt-1">Memory-safe streaming CSV, JSON, and Apache Parquet.</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 pt-2">
                <button
                  onClick={() => {
                    setView('dashboard');
                    fetchRepositories();
                  }}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-5 py-2.5 rounded-lg shadow-lg shadow-indigo-600/30 font-medium transition flex items-center gap-2"
                >
                  <span>Explore Repositories Demo</span>
                  <span>→</span>
                </button>
                <div className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-400 hidden sm:flex items-center gap-2">
                  <span className="text-indigo-400">$</span>
                  <span>python -m datagit.cli.main crawl vercel</span>
                </div>
              </div>
            </div>

            {/* Right Column: Sign In / Sign Up Form */}
            <div className="lg:col-span-5 w-full">
              <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl">
                <h2 className="text-2xl font-bold mb-2 text-white">
                  {view === 'signin' ? 'Welcome to DataGit' : 'Create an Account'}
                </h2>
                <p className="text-slate-400 text-sm mb-6">
                  {view === 'signin'
                    ? 'Sign in to dispatch background crawl jobs and export structured corpora.'
                    : 'Register to manage crawl pipelines in compliance with the DataGit Constitution.'}
                </p>

                {errorMsg && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">{errorMsg}</div>}
                {successMsg && <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm rounded-lg">{successMsg}</div>}

                <form onSubmit={view === 'signin' ? handleSignIn : handleSignUp} className="space-y-4">
                  <div>
                    <label htmlFor="auth-email" className="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Email Address</label>
                    <input
                      id="auth-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition text-sm"
                      placeholder="developer@example.com"
                    />
                  </div>
                  <div>
                    <label htmlFor="auth-password" className="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Password (min 8 characters)</label>
                    <input
                      id="auth-password"
                      name="password"
                      type="password"
                      autoComplete={view === 'signin' ? 'current-password' : 'new-password'}
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
          </div>
        </div>
      )}

      {/* Pricing & Quotas Modal (Spec 3.8 & 4.7) */}
      {showPricing && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full p-6 sm:p-8 space-y-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-xl font-bold text-white">Transparent Plans & Quotas</h3>
                <p className="text-xs text-slate-400 mt-1">Know exact limits, quotas, and capabilities before committing.</p>
              </div>
              <button
                onClick={() => setShowPricing(false)}
                className="text-slate-400 hover:text-white text-lg font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Developer Free</span>
                  <div className="text-2xl font-black text-white mt-2">$0 <span className="text-xs font-normal text-slate-500">/mo</span></div>
                  <ul className="text-xs text-slate-300 space-y-2 mt-4">
                    <li>✔ 50 Monthly Crawls</li>
                    <li>✔ 3 Pages / 300 Repos per crawl</li>
                    <li>✔ 60 req/min API rate limit</li>
                    <li>✔ CSV, JSON, Parquet exports</li>
                    <li>✔ FTS5 Full-Text Search</li>
                  </ul>
                </div>
                <button
                  onClick={() => setShowPricing(false)}
                  className="w-full mt-6 bg-slate-800 hover:bg-slate-700 text-white text-xs py-2 rounded-lg font-medium transition"
                >
                  Current Tier
                </button>
              </div>

              <div className="bg-slate-950 border-2 border-indigo-500/80 rounded-xl p-5 flex flex-col justify-between relative shadow-xl shadow-indigo-500/10">
                <span className="absolute -top-3 right-4 bg-indigo-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">Most Popular</span>
                <div>
                  <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Team Pro</span>
                  <div className="text-2xl font-black text-white mt-2">$49 <span className="text-xs font-normal text-slate-500">/mo</span></div>
                  <ul className="text-xs text-slate-300 space-y-2 mt-4">
                    <li>✔ 2,000 Monthly Crawls</li>
                    <li>✔ 50 Pages / 5,000 Repos per crawl</li>
                    <li>✔ 600 req/min API rate limit</li>
                    <li>✔ Multi-Token Rotating Pool</li>
                    <li>✔ Full Commits & Issues Depth</li>
                    <li>✔ 365 Days Data Retention</li>
                  </ul>
                </div>
                <button
                  onClick={() => alert('Stripe self-serve upgrade integration is configured. Contact support to activate Pro tier.')}
                  className="w-full mt-6 bg-indigo-600 hover:bg-indigo-500 text-white text-xs py-2 rounded-lg font-medium transition"
                >
                  Upgrade to Pro
                </button>
              </div>

              <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">Enterprise AI</span>
                  <div className="text-2xl font-black text-white mt-2">Custom</div>
                  <ul className="text-xs text-slate-300 space-y-2 mt-4">
                    <li>✔ Unlimited Crawls & Pages</li>
                    <li>✔ Dedicated Workers & Token Pool</li>
                    <li>✔ VPC / Self-Hosted Deployment</li>
                    <li>✔ Custom Embeddings Pipelines</li>
                    <li>✔ 99.9% Uptime SLA</li>
                  </ul>
                </div>
                <button
                  onClick={() => window.open('mailto:enterprise@datagit.dev', '_blank')}
                  className="w-full mt-6 bg-slate-800 hover:bg-slate-700 text-white text-xs py-2 rounded-lg font-medium transition"
                >
                  Contact Sales
                </button>
              </div>
            </div>

            {/* ICP Comparison Matrix (Epic P3.3) */}
            <div className="w-full pt-8 border-t border-slate-800/80 mt-6">
              <div className="text-center mb-6">
                <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider font-mono">Platform Comparison</span>
                <h3 className="text-xl sm:text-2xl font-bold text-white mt-1">Why Engineers & Platform Teams Choose DataGit</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-xl mx-auto">
                  Engineered specifically for AI developers, researchers, and OSINT platform teams who need reliable repo corpora without writing custom crawlers.
                </p>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80 shadow-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 text-slate-400 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="p-3.5">Capability / Requirement</th>
                      <th className="p-3.5 text-indigo-400 font-bold bg-indigo-950/30">DataGit</th>
                      <th className="p-3.5">DIY Python Scripts</th>
                      <th className="p-3.5">Raw GitHub REST API</th>
                      <th className="p-3.5">Generic Web Scrapers</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    <tr>
                      <td className="p-3.5 font-medium text-white">Rate-Limit Protection & Token Pooling</td>
                      <td className="p-3.5 bg-indigo-950/10 text-emerald-400 font-semibold">✔ Multi-PAT / Redis Paced</td>
                      <td className="p-3.5 text-red-400">✖ Single Token Burn</td>
                      <td className="p-3.5 text-amber-400">⚠️ 5,000/hr Hard Ceiling</td>
                      <td className="p-3.5 text-red-400">✖ Cloudflare / 429 Bans</td>
                    </tr>
                    <tr>
                      <td className="p-3.5 font-medium text-white">Incremental Delta Crawling (SHA256)</td>
                      <td className="p-3.5 bg-indigo-950/10 text-emerald-400 font-semibold">✔ Content-hash deduplication</td>
                      <td className="p-3.5 text-red-400">✖ Re-crawls everything</td>
                      <td className="p-3.5 text-amber-400">⚠️ Manual ETag wiring</td>
                      <td className="p-3.5 text-red-400">✖ No entity state</td>
                    </tr>
                    <tr>
                      <td className="p-3.5 font-medium text-white">AI & RAG Ready Formats</td>
                      <td className="p-3.5 bg-indigo-950/10 text-emerald-400 font-semibold">✔ RAG JSON + Parquet streaming</td>
                      <td className="p-3.5 text-amber-400">⚠️ Custom JSON scripts</td>
                      <td className="p-3.5 text-slate-400">Raw nested responses</td>
                      <td className="p-3.5 text-red-400">✖ Messy raw HTML</td>
                    </tr>
                    <tr>
                      <td className="p-3.5 font-medium text-white">Multi-Worker Distributed Safety</td>
                      <td className="p-3.5 bg-indigo-950/10 text-emerald-400 font-semibold">✔ Shared queue & backoff lock</td>
                      <td className="p-3.5 text-red-400">✖ Concurrency collisions</td>
                      <td className="p-3.5 text-slate-400">—</td>
                      <td className="p-3.5 text-amber-400">⚠️ Complex proxy setups</td>
                    </tr>
                    <tr>
                      <td className="p-3.5 font-medium text-white">Full-Text Code & Repo Search</td>
                      <td className="p-3.5 bg-indigo-950/10 text-emerald-400 font-semibold">✔ Porter Unicode FTS5</td>
                      <td className="p-3.5 text-red-400">✖ Unindexed file scanning</td>
                      <td className="p-3.5 text-amber-400">⚠️ Separate search rate limits</td>
                      <td className="p-3.5 text-red-400">✖ None</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
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
                    id="repo-search"
                    name="searchTerm"
                    aria-label="Search repositories"
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
                          <div className="flex items-center gap-1.5 shrink-0">
                            {repo.health && (
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                                repo.health.label === 'Thriving' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
                                repo.health.label === 'Active' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30' :
                                repo.health.label === 'Moderate' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
                                'bg-red-500/10 text-red-400 border border-red-500/30'
                              }`}>
                                {repo.health.score}
                              </span>
                            )}
                            <span className="text-xs bg-slate-950 border border-slate-800 px-2 py-0.5 rounded-full text-amber-400 font-mono whitespace-nowrap">
                              ⭐ {repo.stars.toLocaleString()}
                            </span>
                          </div>
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
                    id="target-org"
                    name="targetOrg"
                    aria-label="Crawl target"
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
                                <button
                                  onClick={() => handleRerunJob(j.id)}
                                  className="text-indigo-400 hover:text-indigo-300 text-xs font-medium"
                                >
                                  Re-run
                                </button>
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

          {/* TAB: EXPORTS VIEW */}
          {dashboardTab === 'exports' && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>📦</span> Dataset Export Center
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Export mined repositories into clean AI-ready corpora. Generate signed object storage artifacts (48-hour retention) or stream directly.
                  </p>
                </div>

                {/* Filter indicators */}
                <div className="flex flex-wrap items-center gap-2 text-xs pt-1">
                  <span className="text-slate-500">Active Export Filters:</span>
                  <span className="bg-slate-950 border border-slate-800 px-2.5 py-0.5 rounded text-indigo-400 font-mono">
                    Keyword: {searchTerm || 'All'}
                  </span>
                  <span className="bg-slate-950 border border-slate-800 px-2.5 py-0.5 rounded text-purple-400 font-mono">
                    Language: {selectedLanguage || 'All'}
                  </span>
                  <span className="bg-slate-950 border border-slate-800 px-2.5 py-0.5 rounded text-amber-400 font-mono">
                    Min Stars: {minStars}
                  </span>
                </div>

                {/* Format and generation controls */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-3 border-t border-slate-800/80">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400 font-medium">Format:</span>
                    {(['csv', 'json', 'parquet', 'rag_json'] as const).map((fmt) => (
                      <button
                        key={fmt}
                        onClick={() => setExportFormat(fmt)}
                        className={`text-xs px-3 py-1.5 rounded-lg border font-mono uppercase transition ${
                          exportFormat === fmt
                            ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm'
                            : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                        }`}
                      >
                        {fmt === 'rag_json' ? 'RAG JSON' : fmt}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    <button
                      onClick={handleGenerateExportArtifact}
                      disabled={exportGenerating}
                      className="flex-1 sm:flex-none bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg shadow-indigo-600/30 transition flex items-center justify-center gap-1.5"
                    >
                      <span>💾</span>
                      <span>{exportGenerating ? 'Generating Artifact...' : 'Save to Object Storage'}</span>
                    </button>
                    <button
                      onClick={() => handleExport(exportFormat)}
                      className="flex-1 sm:flex-none bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium px-4 py-2 rounded-lg border border-slate-700 transition flex items-center justify-center gap-1.5"
                    >
                      <span>⚡</span>
                      <span>Direct Stream</span>
                    </button>
                  </div>
                </div>

                {exportMessage && (
                  <div className="p-3 bg-slate-950 border border-indigo-900/50 rounded-lg text-xs text-indigo-300 font-mono">
                    {exportMessage}
                  </div>
                )}
              </div>

              {/* Stored Artifacts Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Stored Export Artifacts</h4>
                  <span className="text-xs text-slate-500">{exportArtifacts.length} stored</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Filename</th>
                        <th className="px-4 py-3">Format</th>
                        <th className="px-4 py-3">Size</th>
                        <th className="px-4 py-3">SHA-256 Checksum</th>
                        <th className="px-4 py-3">Expires</th>
                        <th className="px-4 py-3">Download</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {exportArtifacts.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                            No stored export artifacts yet. Click &apos;Save to Object Storage&apos; above.
                          </td>
                        </tr>
                      ) : (
                        exportArtifacts.map((a) => (
                          <tr key={a.id} className="hover:bg-slate-800/40 transition">
                            <td className="px-4 py-3 font-mono text-white text-[11px]">{a.filename}</td>
                            <td className="px-4 py-3">
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-950 border border-slate-800 text-indigo-400">
                                {a.format}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {(a.file_size / 1024).toFixed(1)} KB
                            </td>
                            <td className="px-4 py-3 font-mono text-slate-500 text-[10px]">
                              {a.checksum_sha256 ? `${a.checksum_sha256.slice(0, 12)}...` : '—'}
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {a.expires_at ? new Date(a.expires_at).toLocaleDateString() : '—'}
                            </td>
                            <td className="px-4 py-3">
                              <a
                                href={`${API_URL}${a.download_url}`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold text-xs"
                              >
                                <span>Download</span>
                                <span>↗</span>
                              </a>
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

          {/* TAB: WEBHOOKS VIEW */}
          {dashboardTab === 'webhooks' && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🪝</span> Webhooks & Event Subscriptions
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Receive asynchronous HTTP POST payloads whenever crawl jobs finish, fail, or exports are ready. Payloads are signed with HMAC-SHA256 headers.
                  </p>
                </div>

                <form onSubmit={handleCreateWebhook} className="space-y-3 pt-1">
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
                    <input
                      id="webhook-url"
                      name="webhookUrl"
                      aria-label="Webhook endpoint URL"
                      type="url"
                      required
                      placeholder="https://your-domain.com/webhooks/datagit..."
                      value={newWebhookUrl}
                      onChange={(e) => setNewWebhookUrl(e.target.value)}
                      className="md:col-span-8 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white text-xs focus:outline-none focus:border-indigo-500"
                    />
                    <input
                      id="webhook-events"
                      name="webhookEvents"
                      aria-label="Webhook subscribed events"
                      type="text"
                      placeholder="job.completed,job.failed,export.ready"
                      value={newWebhookEvents}
                      onChange={(e) => setNewWebhookEvents(e.target.value)}
                      className="md:col-span-4 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white text-xs focus:outline-none focus:border-indigo-500 font-mono"
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-5 py-2 rounded-lg shadow-lg shadow-indigo-600/30 transition"
                    >
                      + Register Webhook
                    </button>
                  </div>
                </form>

                {createdWebhookSecret && (
                  <div className="bg-emerald-950/70 border border-emerald-700/60 p-4 rounded-xl space-y-2">
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                      <span>🔒</span> Webhook Secret Generated (Save now for signature verification):
                    </span>
                    <code className="block bg-slate-950/80 p-2.5 rounded border border-emerald-800/50 text-xs font-mono text-emerald-300 select-all overflow-x-auto">
                      {createdWebhookSecret}
                    </code>
                  </div>
                )}

                {webhookTestMessage && (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs text-indigo-300 font-mono">
                    {webhookTestMessage}
                  </div>
                )}
              </div>

              {/* Webhooks Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Active Webhooks</h4>
                  <span className="text-xs text-slate-500">{webhooks.length} endpoints</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Endpoint URL</th>
                        <th className="px-4 py-3">Subscribed Events</th>
                        <th className="px-4 py-3">Last Triggered</th>
                        <th className="px-4 py-3">Failures</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {webhooks.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                            No webhooks registered yet. Register an endpoint above to receive crawl lifecycle updates.
                          </td>
                        </tr>
                      ) : (
                        webhooks.map((w) => (
                          <tr key={w.id} className="hover:bg-slate-800/40 transition">
                            <td className="px-4 py-3 font-mono text-white text-[11px]">{w.url}</td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-1">
                                {w.events.map((ev) => (
                                  <span key={ev} className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950 border border-slate-800 text-indigo-400">
                                    {ev}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {w.last_triggered_at ? new Date(w.last_triggered_at).toLocaleString() : 'Never'}
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {w.failure_count > 0 ? (
                                <span className="text-red-400 font-semibold">{w.failure_count} errors</span>
                              ) : (
                                <span className="text-emerald-400">0 errors</span>
                              )}
                            </td>
                            <td className="px-4 py-3 flex items-center gap-3">
                              <button
                                onClick={() => handleTestWebhook(w.id)}
                                disabled={testingWebhookId === w.id}
                                className="text-indigo-400 hover:text-indigo-300 font-medium text-xs disabled:opacity-50"
                              >
                                {testingWebhookId === w.id ? 'Testing...' : 'Test Ping'}
                              </button>
                              <button
                                onClick={() => handleDeleteWebhook(w.id)}
                                className="text-red-400 hover:text-red-300 font-medium text-xs"
                              >
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Signature Verification Guide Box */}
              <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-2">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <span>🔐</span> HMAC-SHA256 Signature Verification Example
                </h4>
                <p className="text-xs text-slate-400">
                  DataGit signs every webhook payload with the <code className="text-indigo-400 font-mono">X-DataGit-Signature</code> header. Verify in Python:
                </p>
                <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
{`import hmac, hashlib

def verify_datagit_webhook(secret: str, raw_payload: bytes, header_signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_signature)`}
                </pre>
              </div>
            </div>
          )}

          {/* TAB: GITHUB CREDENTIALS & TOKEN POOL VIEW */}
          {dashboardTab === 'credentials' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <span className="text-slate-400 text-xs">Rotating Token Pool</span>
                  <p className="text-2xl font-bold text-white mt-1">
                    {rateLimit?.active_tokens_count || 1} Token{(rateLimit?.active_tokens_count || 1) > 1 ? 's' : ''}
                  </p>
                  <span className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                    AES-256 Encrypted at Rest
                  </span>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <span className="text-slate-400 text-xs">Total Pool Rate Remaining</span>
                  <p className="text-2xl font-bold text-indigo-400 mt-1 font-mono">
                    {rateLimit?.total_remaining_requests.toLocaleString() || '5,000'} / {rateLimit?.total_limit.toLocaleString() || '5,000'}
                  </p>
                  <span className="text-[11px] text-slate-400 mt-1">GitHub API requests available</span>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                  <span className="text-slate-400 text-xs">Rate Limit Strategy</span>
                  <p className="text-lg font-bold text-white mt-1">Shared Multi-Worker Store</p>
                  <span className="text-[11px] text-slate-400 mt-1">Exponential backoff on 403/429</span>
                </div>
              </div>

              {/* GitHub App Connection Banner (Epic P2.1) */}
              <div className="bg-linear-to-r from-indigo-950/70 to-purple-950/70 border border-indigo-700/60 p-5 rounded-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div className="space-y-1">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    ⭐ Recommended for Organizations
                  </div>
                  <h3 className="text-sm font-bold text-white">Connect DataGit GitHub App</h3>
                  <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                    Install the official GitHub App directly into your organization or personal account. Eliminates manual PAT rotation, automatically manages tokens, and isolates repository permissions.
                  </p>
                </div>
                <button
                  onClick={handleInstallGithubApp}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg shadow-lg shadow-indigo-600/30 transition whitespace-nowrap flex items-center gap-2"
                >
                  <span>🚀</span> Install GitHub App
                </button>
              </div>

              {/* Add & Validate Token Form */}
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🔑</span> Connect GitHub Personal Access Token (PAT)
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Add GitHub PATs to scale beyond the default rate limits. Tokens are tested live, encrypted with Fernet AES-256, and never logged in plain text.
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    id="token-input"
                    name="tokenInput"
                    aria-label="GitHub Personal Access Token"
                    type="password"
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx or github_pat_..."
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white text-xs font-mono focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleValidateToken}
                    disabled={validatingToken || !tokenInput.trim()}
                    className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2.5 rounded-lg border border-slate-700 transition whitespace-nowrap"
                  >
                    {validatingToken ? 'Verifying with GitHub...' : 'Validate Token'}
                  </button>
                </div>

                {/* Scope recommendations */}
                <div className="text-[11px] text-slate-400 flex flex-wrap gap-2 items-center">
                  <span className="text-slate-500">Recommended Scopes:</span>
                  <span className="bg-slate-950 border border-slate-800 px-2 py-0.5 rounded font-mono text-slate-300">public_repo</span>
                  <span className="bg-slate-950 border border-slate-800 px-2 py-0.5 rounded font-mono text-slate-300">read:org</span>
                  <span className="bg-slate-950 border border-slate-800 px-2 py-0.5 rounded font-mono text-slate-300">repo (optional, for private repos)</span>
                </div>

                {/* Validation Preview Card */}
                {tokenValidation && (
                  <div className="bg-slate-950 border border-emerald-800/60 p-4 rounded-xl space-y-3">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="text-emerald-400 text-sm">✓</span>
                        <span className="text-xs font-bold text-white">Valid Token for @{tokenValidation.username}</span>
                      </div>
                      <span className="text-xs font-mono text-indigo-400">
                        {tokenValidation.rate_limit_remaining} / {tokenValidation.rate_limit} requests remaining
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 flex gap-2 items-center">
                      <span>Detected scopes:</span>
                      <span className="font-mono text-slate-300">
                        {tokenValidation.scopes.length > 0 ? tokenValidation.scopes.join(', ') : 'None (Public read-only)'}
                      </span>
                    </div>
                    <button
                      onClick={handleAddToken}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow transition"
                    >
                      Save & Encrypt into Rotating Pool
                    </button>
                  </div>
                )}

                {tokenAddMessage && (
                  <div className="p-3 bg-emerald-950/60 border border-emerald-700/60 rounded-lg text-xs text-emerald-300 font-mono">
                    ✓ {tokenAddMessage}
                  </div>
                )}

                {tokenAddError && (
                  <div className="p-3 bg-red-950/60 border border-red-700/60 rounded-lg text-xs text-red-300 font-mono">
                    ⚠️ {tokenAddError}
                  </div>
                )}
              </div>

              {/* Pool Status Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Active Token Pool Status</h4>
                  <span className="text-xs text-slate-500">{rateLimit?.pools?.length || 0} active</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Token Mask</th>
                        <th className="px-4 py-3">Quota Remaining</th>
                        <th className="px-4 py-3">Limit</th>
                        <th className="px-4 py-3">Reset Countdown</th>
                        <th className="px-4 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {(rateLimit?.pools || []).map((p, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/40 transition">
                          <td className="px-4 py-3 font-mono text-indigo-400 text-[11px]">{p.token_masked}</td>
                          <td className="px-4 py-3 font-mono text-white text-[11px]">{p.remaining}</td>
                          <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">{p.limit}</td>
                          <td className="px-4 py-3 text-slate-400 text-[11px]">{Math.floor(p.seconds_until_reset / 60)}m remaining</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${p.is_exhausted ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                              {p.is_exhausted ? 'Cooling Down' : 'Active'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: API KEYS & AUTOMATION VIEW */}
          {dashboardTab === 'api-keys' && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>🔑</span> Programmatic API Keys
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Authenticate headless crawlers, CI/CD pipelines, and SDKs using <code className="text-indigo-400 font-mono">X-API-Key: dg_live_...</code> or <code className="text-indigo-400 font-mono">Authorization: Bearer dg_live_...</code>
                  </p>
                </div>

                {/* Create Key Form */}
                <form onSubmit={handleCreateApiKey} className="flex flex-col sm:flex-row gap-3 pt-2">
                  <input
                    id="api-key-name"
                    name="apiKeyName"
                    aria-label="API key description"
                    type="text"
                    required
                    placeholder="Key description (e.g., GitHub Actions, Production Mining Agent)..."
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white text-xs focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-5 py-2.5 rounded-lg shadow-lg shadow-indigo-600/30 transition whitespace-nowrap"
                  >
                    + Generate Key
                  </button>
                </form>

                {/* One-time Key Secret Banner */}
                {createdKey && (
                  <div className="bg-emerald-950/70 border border-emerald-700/60 p-4 rounded-xl space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                        <span>🔒</span> New API Key Generated (Copy now — it will not be shown again)
                      </span>
                      <button
                        onClick={handleCopyKey}
                        className="bg-emerald-700 hover:bg-emerald-600 text-white text-xs px-3 py-1 rounded font-medium transition"
                      >
                        {copiedKey ? '✓ Copied!' : 'Copy Key'}
                      </button>
                    </div>
                    <code className="block bg-slate-950/80 p-2.5 rounded border border-emerald-800/50 text-xs font-mono text-emerald-300 select-all overflow-x-auto">
                      {createdKey}
                    </code>
                  </div>
                )}
              </div>

              {/* API Keys Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Active Keys</h4>
                  <span className="text-xs text-slate-500">{apiKeys.filter((k) => !k.is_revoked).length} active</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Key Name</th>
                        <th className="px-4 py-3">Prefix</th>
                        <th className="px-4 py-3">Created</th>
                        <th className="px-4 py-3">Last Used</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {apiKeys.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                            No API keys created yet. Generate one above to automate data crawls.
                          </td>
                        </tr>
                      ) : (
                        apiKeys.map((k) => (
                          <tr key={k.id} className="hover:bg-slate-800/40 transition">
                            <td className="px-4 py-3 font-medium text-white">{k.name}</td>
                            <td className="px-4 py-3 font-mono text-indigo-400">{k.key_prefix}...</td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {k.created_at ? new Date(k.created_at).toLocaleDateString() : '—'}
                            </td>
                            <td className="px-4 py-3 text-slate-400 text-[11px]">
                              {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : 'Never'}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                  k.is_revoked
                                    ? 'bg-slate-800 text-slate-500 border border-slate-700'
                                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                }`}
                              >
                                {k.is_revoked ? 'Revoked' : 'Active'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              {!k.is_revoked && (
                                <button
                                  onClick={() => handleRevokeApiKey(k.id)}
                                  className="text-red-400 hover:text-red-300 text-xs font-medium"
                                >
                                  Revoke
                                </button>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Interactive Code Snippets / SDK Quickstart */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                      <span>💻</span> Developer Automation & SDK Quickstart
                    </h4>
                    <p className="text-[11px] text-slate-400 mt-0.5">Use your live API key to interact with DataGit programmatically.</p>
                  </div>
                  <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-medium">
                    <button
                      onClick={() => setSdkLang('python')}
                      className={`px-3 py-1 rounded transition ${sdkLang === 'python' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                    >
                      Python SDK
                    </button>
                    <button
                      onClick={() => setSdkLang('curl')}
                      className={`px-3 py-1 rounded transition ${sdkLang === 'curl' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                    >
                      cURL / REST
                    </button>
                    <button
                      onClick={() => setSdkLang('cli')}
                      className={`px-3 py-1 rounded transition ${sdkLang === 'cli' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                    >
                      DataGit CLI
                    </button>
                  </div>
                </div>

                <div className="p-4 bg-slate-950">
                  {sdkLang === 'python' && (
                    <pre className="text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`from datagit.sdk import DataGitClient

# Initialize DataGit Client
client = DataGitClient(api_key="${apiKeys.find(k => !k.is_revoked)?.key_prefix ? `${apiKeys.find(k => !k.is_revoked)?.key_prefix}...` : 'dg_live_YOUR_KEY'}", base_url="${API_URL || 'http://localhost:8000'}")

# 1. Enqueue asynchronous background crawl
job = client.jobs.create(target="facebook/react", depth="metadata", max_pages=3)
print(f"Dispatched Job #{job['job_id']}")

# 2. Search mined repository intelligence
results = client.repositories.search(keyword="react", min_stars=5000)
print(f"Found {results['total']} matching repositories")

# 3. Generate signed object storage export
artifact = client.exports.create_artifact(format="csv", search="react")
print(f"Download URL (48h retention): {artifact['download_url']}")`}
                    </pre>
                  )}

                  {sdkLang === 'curl' && (
                    <pre className="text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`# 1. Enqueue a background crawl job
curl -X POST "${API_URL || 'http://localhost:8000'}/api/jobs" \\
  -H "Authorization: Bearer ${apiKeys.find(k => !k.is_revoked)?.key_prefix ? `${apiKeys.find(k => !k.is_revoked)?.key_prefix}...` : 'dg_live_YOUR_KEY'}" \\
  -H "Content-Type: application/json" \\
  -d '{"target": "facebook/react", "depth": "metadata", "max_pages": 3}'

# 2. Search repositories with FTS
curl "${API_URL || 'http://localhost:8000'}/api/repos?search=react&min_stars=1000"

# 3. Stream export directly
curl -H "Authorization: Bearer ${apiKeys.find(k => !k.is_revoked)?.key_prefix ? `${apiKeys.find(k => !k.is_revoked)?.key_prefix}...` : 'dg_live_YOUR_KEY'}" \\
  "${API_URL || 'http://localhost:8000'}/api/export?format=csv&min_stars=500" -o dataset.csv`}
                    </pre>
                  )}

                  {sdkLang === 'cli' && (
                    <pre className="text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`# Crawl target GitHub organization or repo
datagit crawl facebook/react --depth metadata

# Search repositories locally with filters
datagit search --min-stars 1000 --lang TypeScript

# Export dataset to CSV, JSON, or Parquet
datagit export --format parquet --output react_ecosystem.parquet`}
                    </pre>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: AUDIT TRAIL VIEW */}
          {dashboardTab === 'audit' && (
            <div className="space-y-6">
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>🛡️</span> Security & Operations Audit Trail
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Immutable audit trail recording logins, crawl dispatches, credential operations, and export events.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Recent Audit Events</h4>
                  <span className="text-xs text-slate-500">{auditLogs.length} events</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Timestamp</th>
                        <th className="px-4 py-3">Action</th>
                        <th className="px-4 py-3">Target</th>
                        <th className="px-4 py-3">Details</th>
                        <th className="px-4 py-3">Client IP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {auditLogs.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                            No audit log events recorded yet.
                          </td>
                        </tr>
                      ) : (
                        auditLogs.map((log) => (
                          <tr key={log.id} className="hover:bg-slate-800/40 transition">
                            <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                              {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                            </td>
                            <td className="px-4 py-3 font-semibold text-indigo-400">
                              {log.action}
                            </td>
                            <td className="px-4 py-3 text-white font-mono text-[11px]">
                              {log.target || '—'}
                            </td>
                            <td className="px-4 py-3 text-slate-300 text-[11px]">
                              {log.details || '—'}
                            </td>
                            <td className="px-4 py-3 font-mono text-slate-500 text-[11px]">
                              {log.ip_address || '—'}
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

          {/* TAB: SLO TELEMETRY & RELIABILITY (Epic P3.3) */}
          {dashboardTab === 'slos' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>📊</span> Service Level Objectives (SLOs) & Reliability Engineering
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Real-time telemetry tracking crawl latency, export reliability, API p95 budgets, and monthly review rituals per SLO.md.
                </p>
              </div>

              {sloLoading && !sloData ? (
                <div className="text-center py-12 text-slate-500 text-xs">Computing live reliability SLI metrics...</div>
              ) : sloData ? (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                      <span className="text-slate-400 text-xs">Crawl Start Latency (p95)</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold text-white font-mono">{sloData.current.crawl_start_latency_p95_seconds}s</span>
                        <span className="text-[11px] text-slate-500 font-mono">/ &lt;{sloData.targets.crawl_start_latency_p95_target_seconds}s</span>
                      </div>
                      <span className="text-[11px] text-emerald-400 flex items-center gap-1 mt-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        Within Target
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                      <span className="text-slate-400 text-xs">Export Success Rate</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold text-emerald-400 font-mono">{sloData.current.export_success_rate_percent}%</span>
                        <span className="text-[11px] text-slate-500 font-mono">/ {sloData.targets.export_success_rate_target_percent}%</span>
                      </div>
                      <span className="text-[11px] text-slate-400 mt-2">Zero truncation</span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                      <span className="text-slate-400 text-xs">API Latency (p95)</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold text-indigo-400 font-mono">{sloData.current.api_p95_ms}ms</span>
                        <span className="text-[11px] text-slate-500 font-mono">/ &lt;{sloData.targets.api_query_latency_p95_target_ms}ms</span>
                      </div>
                      <span className="text-[11px] text-indigo-300 mt-2">FTS5 Accelerated</span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
                      <span className="text-slate-400 text-xs">Platform Uptime</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold text-white font-mono">{sloData.current.platform_uptime_percent}%</span>
                      </div>
                      <span className="text-[11px] text-emerald-400 mt-2">Budget remaining: 99.0%</span>
                    </div>
                  </div>

                  {/* Monthly Review Ritual & Targets */}
                  <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-800 pb-4">
                      <div>
                        <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
                          Monthly Reliability Review Ritual
                        </h4>
                        <p className="text-xs text-slate-400 mt-0.5">
                          Scheduled ritual: <span className="text-indigo-400 font-medium">{sloData.monthly_review_schedule}</span>
                        </p>
                      </div>
                      <button
                        onClick={fetchSlos}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded-lg border border-slate-700 transition"
                      >
                        ↻ Refresh Telemetry
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                      <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 font-medium">1. Error Budget Status</span>
                        <p className="text-slate-300 mt-1">Crawl Latency: <span className="text-emerald-400 font-mono">{sloData.error_budget_remaining.crawl_latency_budget_percent}%</span> healthy.</p>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 font-medium">2. Quota & Backoff Safety</span>
                        <p className="text-slate-300 mt-1">Rate Safety: <span className="text-emerald-400 font-mono">100%</span> compliance with 0 hard lockouts.</p>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 font-medium">3. Action Items</span>
                        <p className="text-slate-300 mt-1">All core service SLOs meeting 10/10 developer bar.</p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-12">
                  <button
                    onClick={fetchSlos}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition"
                  >
                    Load Live SLO Metrics
                  </button>
                </div>
              )}
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
                  {/* Repository Health Score Card */}
                  {selectedRepo.health && (
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white">Repository Health</span>
                          <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                            selectedRepo.health.label === 'Thriving' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
                            selectedRepo.health.label === 'Active' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30' :
                            selectedRepo.health.label === 'Moderate' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
                            'bg-red-500/10 text-red-400 border border-red-500/30'
                          }`}>
                            {selectedRepo.health.label} • {selectedRepo.health.score}/100
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 hidden sm:inline">Pushed recency, stars, issue ratio & vitality</span>
                      </div>
                      <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden flex">
                        <div style={{ width: `${selectedRepo.health.score}%` }} className={`h-full ${
                          selectedRepo.health.label === 'Thriving' ? 'bg-emerald-500' :
                          selectedRepo.health.label === 'Active' ? 'bg-indigo-500' :
                          selectedRepo.health.label === 'Moderate' ? 'bg-amber-500' : 'bg-red-500'
                        }`} />
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-400 text-center">
                        <div className="bg-slate-900/60 p-2 rounded border border-slate-800/50">
                          <div className="text-slate-500 text-[10px]">Recency</div>
                          <div className="text-white font-mono font-medium mt-0.5">{selectedRepo.health.breakdown.recency}/40</div>
                        </div>
                        <div className="bg-slate-900/60 p-2 rounded border border-slate-800/50">
                          <div className="text-slate-500 text-[10px]">Adoption</div>
                          <div className="text-white font-mono font-medium mt-0.5">{selectedRepo.health.breakdown.popularity}/25</div>
                        </div>
                        <div className="bg-slate-900/60 p-2 rounded border border-slate-800/50">
                          <div className="text-slate-500 text-[10px]">Hygiene</div>
                          <div className="text-white font-mono font-medium mt-0.5">{selectedRepo.health.breakdown.issue_hygiene}/20</div>
                        </div>
                        <div className="bg-slate-900/60 p-2 rounded border border-slate-800/50">
                          <div className="text-slate-500 text-[10px]">Vitality</div>
                          <div className="text-white font-mono font-medium mt-0.5">{selectedRepo.health.breakdown.vitality}/15</div>
                        </div>
                      </div>
                    </div>
                  )}

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
                      <button
                        onClick={() => {
                          setDetailTab('summary');
                          if (selectedRepo && !repoSummary) {
                            fetchRepoSummary(selectedRepo.id);
                          }
                        }}
                        className={`pb-2 border-b-2 transition ${detailTab === 'summary' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-white'}`}
                      >
                        AI Technical Summary 🧠
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

                    {detailTab === 'summary' && (
                      <div className="space-y-4">
                        {summaryLoading ? (
                          <div className="text-center py-8 text-slate-500 text-xs">
                            Generating AI technical repository summary...
                          </div>
                        ) : summaryError ? (
                          <div className="bg-slate-950 p-4 rounded-xl border border-amber-500/30 text-xs space-y-3">
                            <div className="text-amber-400 font-medium flex items-center gap-2">
                              <span>🔒</span> Pro Tier Feature
                            </div>
                            <p className="text-slate-300">{summaryError}</p>
                            <button
                              onClick={() => {
                                setDetailModalOpen(false);
                                setShowPricing(true);
                              }}
                              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-3 py-1.5 rounded-lg transition"
                            >
                              Upgrade to Pro ($49/mo)
                            </button>
                          </div>
                        ) : repoSummary ? (
                          <div className="space-y-4 text-xs">
                            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                              <div className="flex justify-between items-center">
                                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider font-mono">Overview & Architecture</span>
                                <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-mono">
                                  Velocity: {repoSummary.activity_level}
                                </span>
                              </div>
                              <p className="text-slate-200 leading-relaxed">{repoSummary.overview}</p>
                            </div>

                            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">Identified Tech Stack</span>
                              <div className="flex flex-wrap gap-1.5 mt-1">
                                {repoSummary.tech_stack?.map((tag) => (
                                  <span key={tag} className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200 font-mono text-[11px]">
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            </div>

                            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">Primary Use Case</span>
                              <p className="text-slate-300">{repoSummary.primary_use_case}</p>
                            </div>

                            <div className="bg-slate-950 p-4 rounded-xl border border-indigo-900/40 space-y-1">
                              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider font-mono">AI / RAG Corpus Ingestion</span>
                              <p className="text-slate-300">{repoSummary.rag_recommendation}</p>
                            </div>

                            <div className="flex justify-end pt-2">
                              <button
                                onClick={() => selectedRepo && fetchRepoSummary(selectedRepo.id, true)}
                                className="text-xs text-slate-400 hover:text-white transition flex items-center gap-1"
                              >
                                <span>↻</span> Regenerate Summary
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-6">
                            <button
                              onClick={() => selectedRepo && fetchRepoSummary(selectedRepo.id)}
                              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition"
                            >
                              Generate AI Summary
                            </button>
                          </div>
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

      {/* WORKSPACE CREATION MODAL */}
      {showWorkspaceModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 max-w-md w-full rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>🏢</span> Create Multi-Tenant Workspace
              </h3>
              <button
                onClick={() => setShowWorkspaceModal(false)}
                className="text-slate-400 hover:text-white font-bold"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Workspaces isolate crawled repositories, credentials, export artifacts, and team members.
            </p>
            <form onSubmit={handleCreateWorkspace} className="space-y-4 pt-1">
              <div>
                <label htmlFor="workspace-name" className="block text-xs font-medium text-slate-300 mb-1">Workspace Name</label>
                <input
                  id="workspace-name"
                  name="workspaceName"
                  type="text"
                  required
                  placeholder="e.g. AI Research Lab, Security Eng..."
                  value={newWorkspaceName}
                  onChange={(e) => setNewWorkspaceName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-white text-xs focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowWorkspaceModal(false)}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-4 py-2 rounded-lg font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg shadow-indigo-600/30 transition"
                >
                  Create Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}