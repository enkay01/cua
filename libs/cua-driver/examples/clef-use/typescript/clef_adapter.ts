import * as fs from 'node:fs';
import * as path from 'node:path';
import { ALL_CELLS, areAdjacent } from './grid_localizer.js';

export { ALL_CELLS, areAdjacent };

export function loadEnvFiles(): void {
  let current = process.cwd();
  while (true) {
    for (const file of ['.env.local', '.env']) {
      const fullPath = path.join(current, file);
      if (fs.existsSync(fullPath)) {
        try {
          const content = fs.readFileSync(fullPath, 'utf8');
          for (const rawLine of content.split('\n')) {
            const line = rawLine.trim();
            if (!line || line.startsWith('#') || !line.includes('=')) continue;
            const idx = line.indexOf('=');
            const key = line.slice(0, idx).trim();
            let val = line.slice(idx + 1).trim();
            if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
              val = val.slice(1, -1);
            }
            if (key && !process.env[key]) {
              process.env[key] = val;
            }
          }
        } catch {
          // ignore
        }
      }
    }
    if (fs.existsSync(path.join(current, '.git'))) break;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
}

loadEnvFiles();

export const DEFAULT_MODEL = process.env.CLEF_MODEL || '@cf/cloudflare/clef';
export const CLOUDFLARE_API_BASE = 'https://api.cloudflare.com/client/v4/accounts';

export interface ClefChoiceResult {
  choice: string;
  confidence: number;
  probabilities: Record<string, number>;
  model: string;
  rawResponse: unknown;
  sortedCandidates: [string, number][];
  topCandidate: [string, number];
  runnerUpCandidate?: [string, number];
  topNonAdjacentCandidate(referenceCell?: string): [string, number] | undefined;
}

export function createClefChoiceResult(
  choice: string,
  confidence: number,
  probabilities: Record<string, number>,
  model: string,
  rawResponse: unknown
): ClefChoiceResult {
  const sortedCandidates = Object.entries(probabilities).sort((a, b) => b[1] - a[1]) as [string, number][];
  const topCandidate: [string, number] = sortedCandidates.length > 0 ? sortedCandidates[0] : [choice, confidence];
  const runnerUpCandidate: [string, number] | undefined =
    sortedCandidates.length > 1 ? sortedCandidates[1] : undefined;

  return {
    choice,
    confidence,
    probabilities,
    model,
    rawResponse,
    sortedCandidates,
    topCandidate,
    runnerUpCandidate,
    topNonAdjacentCandidate(referenceCell?: string) {
      const ref = referenceCell || choice;
      for (const [cell, prob] of sortedCandidates) {
        if (cell !== ref && !areAdjacent(ref, cell)) {
          return [cell, prob];
        }
      }
      return undefined;
    },
  };
}

export function defaultCellCriteria(): Record<string, string> {
  const res: Record<string, string> = {};
  for (const cell of ALL_CELLS) {
    res[cell] = `Cell ${cell}`;
  }
  return res;
}

export function buildClefRequest(
  imageBase64: string,
  instructions: string,
  criteria?: Record<string, string>,
  model: string = DEFAULT_MODEL
): Record<string, unknown> {
  const modelSlug = model.toLowerCase().includes('flash') ? 'clef-flash' : 'clef';
  const cleanBase64 = imageBase64.replace(/^data:[^;]+;base64,/, '').trim();
  return {
    model: modelSlug,
    state: `Screenshot with 5x5 grid overlay (columns A-E, rows 1-5). Locate target: ${instructions}`,
    images: [`data:image/jpeg;base64,${cleanBase64}`],
    questions: {
      target_cell: {
        type: 'choice',
        instructions,
        criteria: criteria || defaultCellCriteria(),
      },
    },
  };
}

export function parseClefResponse(
  data: unknown,
  model: string = DEFAULT_MODEL,
  expectedCriteria: readonly string[] = ALL_CELLS
): ClefChoiceResult {
  if (!data || typeof data !== 'object') {
    throw new Error(`Invalid response payload: expected object, got ${typeof data}`);
  }

  const raw = data as Record<string, unknown>;
  const result = (raw.result && typeof raw.result === 'object' ? raw.result : raw) as Record<string, unknown>;

  const answersDict =
    (result.answers && typeof result.answers === 'object'
      ? result.answers
      : result.choices && typeof result.choices === 'object'
      ? result.choices
      : {}) as Record<string, unknown>;

  const targetChoice = (answersDict.target_cell || {}) as Record<string, unknown>;
  if (typeof targetChoice !== 'object' || targetChoice === null) {
    throw new Error("Invalid target_cell entry: expected object");
  }

  const rawChoice = targetChoice.choice;
  let choice = typeof rawChoice === 'string' ? rawChoice.trim().toUpperCase() : '';

  const rawProbs = (targetChoice.probabilities || {}) as Record<string, unknown>;
  if (typeof rawProbs !== 'object' || rawProbs === null) {
    throw new Error("Invalid probabilities field: expected object");
  }

  const expectedSet = new Set(expectedCriteria.map((c) => c.trim().toUpperCase()));
  const probabilities: Record<string, number> = {};

  for (const [k, v] of Object.entries(rawProbs)) {
    const cellKey = k.trim().toUpperCase();
    if (!expectedSet.has(cellKey)) {
      throw new Error(`Unknown cell score returned: "${cellKey}" is not in expected criteria`);
    }

    const val = Number(v);
    if (typeof v === 'boolean' || isNaN(val)) {
      throw new Error(`Non-numeric probability for cell ${cellKey}: ${v}`);
    }
    if (!Number.isFinite(val)) {
      throw new Error(`Non-finite probability for cell ${cellKey}: ${val}`);
    }
    if (val < 0.0 || val > 1.0 + 1e-4) {
      throw new Error(`Probability out of range [0, 1] for cell ${cellKey}: ${val}`);
    }

    probabilities[cellKey] = val;
  }

  if (!choice && Object.keys(probabilities).length > 0) {
    let maxVal = -Infinity;
    for (const [k, v] of Object.entries(probabilities)) {
      if (v > maxVal) {
        maxVal = v;
        choice = k;
      }
    }
  }

  if (!choice) {
    throw new Error("Malformed response: neither choice nor probabilities provided in target_cell");
  }

  if (!expectedSet.has(choice)) {
    throw new Error(`Choice "${choice}" not in expected criteria`);
  }

  let confidence: number;
  if (choice in probabilities) {
    confidence = probabilities[choice];
  } else if (Object.keys(probabilities).length > 0) {
    confidence = Math.max(...Object.values(probabilities));
  } else {
    confidence = Number(targetChoice.confidence) || 0;
  }

  const returnedModel = String(result.model || model);
  return createClefChoiceResult(choice, confidence, probabilities, returnedModel, data);
}

export interface ClefClientOptions {
  accountId?: string;
  apiToken?: string;
  model?: string;
  mockFixturePaths?: (string | URL)[];
  mockHandler?: (image: unknown, instructions: string) => Promise<ClefChoiceResult> | ClefChoiceResult;
}

export class ClefClient {
  public accountId?: string;
  public apiToken?: string;
  public model: string;
  public mockHandler?: (image: unknown, instructions: string) => Promise<ClefChoiceResult> | ClefChoiceResult;
  private fixtureQueue: string[];
  private fixtureIndex = 0;

  constructor(options: ClefClientOptions = {}) {
    this.accountId = options.accountId || process.env.CLOUDFLARE_ACCOUNT_ID;
    this.apiToken = options.apiToken || process.env.CLOUDFLARE_API_TOKEN;
    this.model = options.model || DEFAULT_MODEL;
    this.mockHandler = options.mockHandler;
    this.fixtureQueue = (options.mockFixturePaths || []).map((p) => String(p));
  }

  public get isLiveConfigured(): boolean {
    return Boolean(this.accountId && this.apiToken);
  }

  public async evaluateGrid(
    image: unknown,
    instructions: string,
    criteria?: Record<string, string>,
    timeoutMs?: number
  ): Promise<ClefChoiceResult> {
    if (this.mockHandler) {
      return await this.mockHandler(image, instructions);
    }

    if (this.fixtureQueue.length > 0) {
      const fixturePath = this.fixtureQueue[this.fixtureIndex % this.fixtureQueue.length];
      this.fixtureIndex++;
      const rawJson = fs.readFileSync(fixturePath, 'utf-8');
      const data = JSON.parse(rawJson);
      return parseClefResponse(data, this.model, ALL_CELLS);
    }

    if (!this.isLiveConfigured) {
      throw new Error(
        'Cloudflare credentials missing. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN or initialize ClefClient with mock fixtures.'
      );
    }

    let modelPath = this.model;
    if (!modelPath.startsWith('@cf/')) {
      modelPath = `@cf/cloudflare/${modelPath}`;
    }

    const url = `${CLOUDFLARE_API_BASE}/${this.accountId}/ai/run/${modelPath}`;
    const headers = {
      Authorization: `Bearer ${this.apiToken}`,
      'Content-Type': 'application/json',
    };

    const b64 =
      typeof image === 'string'
        ? image.replace(/^data:[^;]+;base64,/, '').trim()
        : Buffer.isBuffer(image)
        ? image.toString('base64')
        : '';
    const payload = buildClefRequest(b64, instructions, criteria, this.model);

    let signal: AbortSignal | undefined;
    if (timeoutMs !== undefined) {
      if (timeoutMs <= 0) {
        signal = AbortSignal.abort(
          new DOMException('Inference timed out before request dispatch', 'TimeoutError')
        );
      } else {
        signal = AbortSignal.timeout(timeoutMs);
      }
    } else {
      const defaultTimeoutMs = Number(process.env.CLEF_TIMEOUT || 120000);
      signal = defaultTimeoutMs > 0 ? AbortSignal.timeout(defaultTimeoutMs) : undefined;
    }

    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal,
    });

    if (!resp.ok) {
      throw new Error(`Workers AI request failed: ${resp.status} ${resp.statusText}`);
    }

    const data = await resp.json();
    return parseClefResponse(data, this.model, ALL_CELLS);
  }
}
