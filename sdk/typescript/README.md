# @datagit/sdk

The official TypeScript/JavaScript client for the **DataGit Developer SaaS Platform**.

## Installation

```bash
npm install @datagit/sdk
```

## Quick Start

```typescript
import { DataGitClient } from '@datagit/sdk';

const datagit = new DataGitClient({
  apiKey: process.env.DATAGIT_API_KEY!,
  baseUrl: 'https://api.datagit.dev', // or http://localhost:8000 for local development
});

// 1. Search Repositories with standard vitality scoring
const repos = await datagit.repositories.search({
  keyword: 'langchain',
  language: 'Python',
  min_stars: 1000,
});

for (const repo of repos.items) {
  console.log(`${repo.full_name} (${repo.stars} stars) - Health: ${repo.health?.label} (${repo.health?.score}/100)`);
}

// 2. Trigger an Asynchronous Background Crawl Job
const job = await datagit.jobs.create('openai', 'commits', 3);
console.log(`Job queued: ID ${job.job_id}`);

// 3. Generate a RAG / Vector-ready dataset in Object Storage
const exportArtifact = await datagit.exports.createArtifact({
  format: 'rag_json',
  search: 'agent',
});
console.log(`Signed download URL: ${exportArtifact.download_url}`);
```

## License
Apache-2.0
