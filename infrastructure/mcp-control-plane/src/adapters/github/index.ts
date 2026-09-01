import { buildAccountRegistry } from "../../registry/account.registry.js";
import { httpRequest, bearerAuth } from "../../lib/http.js";

const BASE_URL = "https://api.github.com/repos/SaifulHaqueNiloy/supremeai";

function getApiKey(accountId: string): string {
  const accounts = buildAccountRegistry();
  const account = accounts.find((a) => a.id === accountId && a.provider === "github");
  if (!account) throw new Error(`GitHub account not found: ${accountId}`);
  if (!account.available) throw new Error(`GitHub account is not configured/available: ${accountId}`);

  const apiKey = process.env[account.apiKeyRef];
  if (!apiKey) throw new Error(`Missing GitHub Token in env for: ${account.apiKeyRef}`);
  return apiKey;
}

function githubHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "SupremeAI-MCP-Control-Tower",
  };
}

export async function getWorkflowRuns(accountId: string, limit = 5): Promise<unknown> {
  const token = getApiKey(accountId);
  const res = await httpRequest(`${BASE_URL}/actions/runs?per_page=${limit}`, {
    headers: githubHeaders(token),
  });
  return res.data;
}

export async function getFailedLogs(accountId: string, runId: string): Promise<unknown> {
  const token = getApiKey(accountId);
  // Get jobs for the run
  const jobsRes = await httpRequest(`${BASE_URL}/actions/runs/${runId}/jobs`, {
    headers: githubHeaders(token),
  });
  
  const jobs = (jobsRes.data as any).jobs || [];
  const failedJobs = jobs.filter((j: any) => j.conclusion === "failure");

  if (failedJobs.length === 0) {
    return { message: "No failed jobs found for this run.", jobs };
  }

  // To get actual raw logs for a job, you hit /actions/jobs/{job_id}/logs
  // Note: GitHub redirects to a temporary URL for logs. Our httpRequest might not follow or handle plain text well if it's zipped.
  // Actually, job logs are text.
  const failedJobLogs = await Promise.allSettled(
    failedJobs.map(async (job: any) => {
      try {
        const logRes = await fetch(`${BASE_URL}/actions/jobs/${job.id}/logs`, {
          headers: githubHeaders(token),
          redirect: 'follow'
        });
        if (!logRes.ok) throw new Error(`Failed to fetch logs: ${logRes.status}`);
        const logText = await logRes.text();
        // Return only the last 2000 characters of the log to prevent massive payloads
        const snippet = logText.slice(-2000);
        return { jobName: job.name, logsSnippet: snippet };
      } catch (e) {
        return { jobName: job.name, error: (e as Error).message };
      }
    })
  );

  return {
    runId,
    failedJobs: failedJobLogs.map(r => r.status === 'fulfilled' ? r.value : r.reason),
  };
}

export async function listSecrets(accountId: string): Promise<unknown> {
  const token = getApiKey(accountId);
  const res = await httpRequest(`${BASE_URL}/actions/secrets`, {
    headers: githubHeaders(token),
  });
  // GitHub returns only secret names, not values!
  return res.data;
}
