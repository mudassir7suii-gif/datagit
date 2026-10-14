/**
 * Official TypeScript SDK for DataGit Developer SaaS Platform.
 * Supports Node.js 18+ and modern browsers with zero external dependencies.
 */

export class DataGitAPIError extends Error {
  public readonly statusCode: number;
  public readonly detail: string;

  constructor(statusCode: number, detail: string) {
    super(`DataGit API Error ${statusCode}: ${detail}`);
    this.name = 'DataGitAPIError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

export interface ClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export interface CrawlJob {
  id: number;
  target: string;
  target_type?: string;
  depth: 'metadata' | 'commits' | 'issues' | 'full';
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  total_found: number;
  items_crawled: number;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface RepositoryItem {
  id: number;
  github_id: number;
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
  stars: number;
  forks: number;
  open_issues: number;
  url: string;
  is_archived?: boolean;
  repo_pushed_at?: string | null;
  crawled_at?: string | null;
  health?: {
    score: number;
    label: 'Thriving' | 'Active' | 'Moderate' | 'Dormant';
    color: string;
    breakdown: {
      recency: number;
      popularity: number;
      issue_hygiene: number;
      vitality: number;
    };
  };
}

export interface SearchRepositoriesParams {
  keyword?: string;
  language?: string;
  owner?: string;
  min_stars?: number;
  limit?: number;
  offset?: number;
}

export interface ExportArtifactItem {
  artifact_id: number;
  filename: string;
  format: 'csv' | 'json' | 'parquet' | 'rag_json';
  file_size: number;
  checksum_sha256?: string | null;
  download_token: string;
  download_url: string;
  expires_at?: string | null;
}

export interface WebhookItem {
  id: number;
  url: string;
  events: string[];
  is_active: boolean;
  last_triggered_at?: string | null;
  failure_count: number;
  created_at?: string | null;
}

export interface WorkspaceItem {
  id: number;
  name: string;
  slug: string;
  role: string;
  is_owner: boolean;
  created_at?: string | null;
}

export interface SavedSearchItem {
  id: number;
  name: string;
  query_params: Record<string, unknown>;
  notify_on_new: boolean;
  workspace_id?: number | null;
  last_checked_at?: string | null;
  created_at?: string | null;
}

export interface RateLimitStatus {
  active_tokens_count: number;
  total_remaining_requests: number;
  total_limit: number;
  pools: Array<{
    token_masked: string;
    limit: number;
    remaining: number;
    seconds_until_reset: number;
    is_exhausted: boolean;
  }>;
}

class BaseNamespace {
  constructor(protected readonly client: DataGitClient) {}

  protected get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
    return this.client._request<T>('GET', path, params);
  }

  protected post<T>(path: string, body?: unknown): Promise<T> {
    return this.client._request<T>('POST', path, undefined, body);
  }

  protected delete<T>(path: string): Promise<T> {
    return this.client._request<T>('DELETE', path);
  }
}

export class JobsNamespace extends BaseNamespace {
  async list(): Promise<CrawlJob[]> {
    const res = await this.get<{ items: CrawlJob[] }>('/api/jobs');
    return res.items || [];
  }

  async create(target: string, depth: 'metadata' | 'commits' | 'issues' | 'full' = 'metadata', maxPages: number = 3): Promise<{ job_id: number; message: string; target: string; status: string }> {
    return this.post('/api/jobs', { target, depth, max_pages: maxPages });
  }

  async get(jobId: number): Promise<CrawlJob> {
    return this.get<CrawlJob>(`/api/jobs/${jobId}`);
  }

  async cancel(jobId: number): Promise<{ message: string; job_id: number; status: string }> {
    return this.post(`/api/jobs/${jobId}/cancel`);
  }

  async rerun(jobId: number): Promise<{ message: string; job_id: number; original_job_id: number; target: string }> {
    return this.post(`/api/jobs/${jobId}/rerun`);
  }
}

export class RepositoriesNamespace extends BaseNamespace {
  async search(params: SearchRepositoriesParams = {}): Promise<{ total: number; limit: number; offset: number; items: RepositoryItem[] }> {
    const query: Record<string, unknown> = {
      search: params.keyword,
      language: params.language,
      owner: params.owner,
      min_stars: params.min_stars,
      limit: params.limit ?? 24,
      offset: params.offset ?? 0
    };
    return this.get('/api/repos', query);
  }

  async get(repoId: number): Promise<RepositoryItem> {
    return this.get<RepositoryItem>(`/api/repos/${repoId}`);
  }

  async delete(repoId: number): Promise<{ message: string }> {
    return this.delete(`/api/repos/${repoId}`);
  }
}

export class ExportsNamespace extends BaseNamespace {
  async createArtifact(params: {
    format?: 'csv' | 'json' | 'parquet' | 'rag_json';
    search?: string;
    owner?: string;
    language?: string;
    min_stars?: number;
  } = {}): Promise<ExportArtifactItem> {
    return this.post('/api/export/generate', {
      format: params.format ?? 'csv',
      search: params.search,
      owner: params.owner,
      language: params.language,
      min_stars: params.min_stars
    });
  }

  async listArtifacts(): Promise<ExportArtifactItem[]> {
    const res = await this.get<{ items: ExportArtifactItem[] }>('/api/export/artifacts');
    return res.items || [];
  }

  getDownloadUrl(downloadToken: string): string {
    return `${this.client.baseUrl}/api/export/download/${downloadToken}`;
  }
}

export class WebhooksNamespace extends BaseNamespace {
  async list(): Promise<WebhookItem[]> {
    const res = await this.get<{ items: WebhookItem[] }>('/api/webhooks');
    return res.items || [];
  }

  async create(url: string, secret?: string, events?: string[]): Promise<WebhookItem & { secret: string }> {
    return this.post('/api/webhooks', {
      url,
      secret,
      events: events ? events.join(',') : 'job.completed,job.failed'
    });
  }

  async delete(webhookId: number): Promise<{ message: string }> {
    return this.delete(`/api/webhooks/${webhookId}`);
  }

  async test(webhookId: number): Promise<{ message: string; delivery_status: number }> {
    return this.post(`/api/webhooks/${webhookId}/test`);
  }
}

export class WorkspacesNamespace extends BaseNamespace {
  async list(): Promise<WorkspaceItem[]> {
    const res = await this.get<{ items: WorkspaceItem[] }>('/api/workspaces');
    return res.items || [];
  }

  async create(name: string): Promise<WorkspaceItem> {
    return this.post('/api/workspaces', { name });
  }
}

export class SavedSearchesNamespace extends BaseNamespace {
  async list(): Promise<SavedSearchItem[]> {
    const res = await this.get<{ items: SavedSearchItem[] }>('/api/saved-searches');
    return res.items || [];
  }

  async create(name: string, queryParams: Record<string, unknown>, notifyOnNew: boolean = false, workspaceId?: number): Promise<SavedSearchItem> {
    return this.post('/api/saved-searches', {
      name,
      query_params: queryParams,
      notify_on_new: notifyOnNew,
      workspace_id: workspaceId
    });
  }

  async delete(searchId: number): Promise<{ message: string }> {
    return this.delete(`/api/saved-searches/${searchId}`);
  }
}

export class BillingNamespace extends BaseNamespace {
  async checkout(plan: 'pro' | 'enterprise' = 'pro', successUrl?: string, cancelUrl?: string): Promise<{ checkout_url: string; plan?: string; mode: string }> {
    return this.post('/api/billing/checkout', {
      plan,
      success_url: successUrl,
      cancel_url: cancelUrl
    });
  }
}

export class DataGitClient {
  public readonly apiKey: string;
  public readonly baseUrl: string;
  public readonly timeoutMs: number;

  public readonly jobs: JobsNamespace;
  public readonly repositories: RepositoriesNamespace;
  public readonly exports: ExportsNamespace;
  public readonly webhooks: WebhooksNamespace;
  public readonly workspaces: WorkspacesNamespace;
  public readonly savedSearches: SavedSearchesNamespace;
  public readonly billing: BillingNamespace;

  constructor(options: ClientOptions) {
    if (!options.apiKey) {
      throw new Error('DataGitClient requires an apiKey.');
    }
    this.apiKey = options.apiKey.trim();
    this.baseUrl = (options.baseUrl ?? 'http://localhost:8000').replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? 30000;

    this.jobs = new JobsNamespace(this);
    this.repositories = new RepositoriesNamespace(this);
    this.exports = new ExportsNamespace(this);
    this.webhooks = new WebhooksNamespace(this);
    this.workspaces = new WorkspacesNamespace(this);
    this.savedSearches = new SavedSearchesNamespace(this);
    this.billing = new BillingNamespace(this);
  }

  async ratelimitStatus(): Promise<RateLimitStatus> {
    return this._request<RateLimitStatus>('GET', '/api/ratelimit');
  }

  async _request<T>(
    method: 'GET' | 'POST' | 'DELETE',
    path: string,
    params?: Record<string, unknown>,
    body?: unknown
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (params) {
      const sp = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          sp.append(key, String(value));
        }
      }
      const qs = sp.toString();
      if (qs) url += `?${qs}`;
    }

    const headers: Record<string, string> = {
      'User-Agent': 'DataGit-TypeScript-SDK/0.2.0',
      'Accept': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
      'X-API-Key': this.apiKey
    };

    let bodyData: string | undefined = undefined;
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      bodyData = JSON.stringify(body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(url, {
        method,
        headers,
        body: bodyData,
        signal: controller.signal
      });

      if (!resp.ok) {
        let detail = resp.statusText;
        try {
          const errData = await resp.json();
          detail = errData.detail || JSON.stringify(errData);
        } catch {
          detail = await resp.text();
        }
        throw new DataGitAPIError(resp.status, detail);
      }

      const text = await resp.text();
      return (text ? JSON.parse(text) : {}) as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
