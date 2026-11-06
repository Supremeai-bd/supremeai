import { httpRequest } from "../../lib/http.js";

const HARNESS_BASE_URL = "https://app.harness.io";

export interface HarnessExecutionSummary {
  pipelineIdentifier: string;
  status: string;
  totalDurationMs?: number | null;
  startTs?: number;
}

export class HarnessAdapter {
  private getHeaders(): Record<string, string> {
    const apiKey =
      process.env.HARNESS_API_KEY ||
      process.env.HARNESS_API_KEY_NILOYJOY7 ||
      "";
    const accountId = process.env.HARNESS_ACCOUNT_ID || "mP23Uox3Tlq9mlDNsy-0OA";

    return {
      "x-api-key": apiKey,
      "Harness-Account": accountId,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
  }

  private getScopeQuery(orgId = "default", projectId = "default_project"): string {
    const accountId = process.env.HARNESS_ACCOUNT_ID || "mP23Uox3Tlq9mlDNsy-0OA";
    return `accountIdentifier=${accountId}&orgIdentifier=${orgId}&projectIdentifier=${projectId}`;
  }

  /** Check connectivity to Harness */
  async ping(): Promise<{ ok: boolean; message: string }> {
    const scope = this.getScopeQuery();
    const url = `${HARNESS_BASE_URL}/gateway/ng/api/projects?${scope}`;
    try {
      const res = await httpRequest<{ status?: string }>(url, {
        method: "GET",
        headers: this.getHeaders(),
      });
      return { ok: res.data?.status === "SUCCESS", message: "Harness API connected successfully" };
    } catch (err: any) {
      return { ok: false, message: `Harness ping failed: ${err?.message || err}` };
    }
  }

  /** Trigger execution of a deployment or verification pipeline */
  async triggerPipeline(
    pipelineIdentifier: string,
    inputs: Record<string, any> = {}
  ): Promise<any> {
    const scope = this.getScopeQuery();
    const url = `${HARNESS_BASE_URL}/pipeline/api/pipeline/execute/${pipelineIdentifier}?${scope}`;
    return httpRequest(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(inputs),
    });
  }

  /** Query the execution status of a pipeline run */
  async getExecutionStatus(
    executionId: string
  ): Promise<HarnessExecutionSummary | null> {
    const scope = this.getScopeQuery();
    const url = `${HARNESS_BASE_URL}/pipeline/api/pipelines/execution/v2/${executionId}?${scope}`;
    try {
      const res = await httpRequest<any>(url, {
        method: "GET",
        headers: this.getHeaders(),
      });
      return res?.data?.pipelineExecutionSummary || null;
    } catch (err) {
      return null;
    }
  }

  /** Query environment status in Harness */
  async listEnvironments(): Promise<any[]> {
    const scope = this.getScopeQuery();
    const url = `${HARNESS_BASE_URL}/gateway/ng/api/environmentsV2?${scope}`;
    const res = await httpRequest<any>(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return res?.data?.content || [];
  }
}

export const harnessAdapter = new HarnessAdapter();
