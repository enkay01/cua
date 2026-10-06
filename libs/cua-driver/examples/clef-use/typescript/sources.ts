export type SourceKind = 'page' | 'visual' | 'ax';
export type VisualDelivery = 'foreground' | 'background';

export interface Candidate {
  id: string;
  description: string;
  tool: string | null;
  arguments: Record<string, unknown>;
  captureId?: string;
  screenshotReference?: unknown;
  source?: SourceKind;
  snapshotId?: string;
}

export interface Control<THandle = unknown> {
  source: SourceKind;
  role: string;
  name: string;
  value?: unknown;
  handle: THandle;
}

export interface CandidateSource {
  readonly kind: SourceKind;
  find(role: string, name: string): Control | undefined;
  click(control: Control, candidateId: string, description: string): Candidate | undefined;
  typeText(
    control: Control,
    text: string,
    candidateId: string,
    description: string
  ): Candidate | undefined;
}

function asciiLower(value: string): string {
  return value.toLowerCase();
}

export class VisualGridSource implements CandidateSource {
  readonly kind = 'visual' as const;

  constructor(
    readonly localization:
      | {
          success: boolean;
          targetDescription?: string;
          clickX?: number;
          clickY?: number;
        }
      | undefined,
    readonly pid: number,
    readonly windowId: number,
    readonly captureId: string,
    readonly delivery: VisualDelivery = 'background',
    readonly captureBound = false,
    readonly screenshotReference?: unknown
  ) {}

  find(role: string, name: string): Control | undefined {
    if (!this.localization || !this.localization.success) {
      return undefined;
    }
    const locCaptureId = (this.localization as { captureId?: string }).captureId;
    if (locCaptureId !== undefined && locCaptureId !== this.captureId) {
      return undefined;
    }
    const targetDesc = this.localization.targetDescription || '';
    if (asciiLower(targetDesc) !== asciiLower(name)) {
      return undefined;
    }
    return {
      source: 'visual',
      role,
      name: targetDesc,
      value: undefined,
      handle: this.localization,
    };
  }

  click(control: Control, candidateId: string, description: string): Candidate | undefined {
    if (!this.captureBound) return undefined;
    if (!this.localization || !this.localization.success) return undefined;
    const locCaptureId = (this.localization as { captureId?: string }).captureId;
    if (locCaptureId !== undefined && locCaptureId !== this.captureId) {
      return undefined;
    }
    const { clickX, clickY } = this.localization;
    if (clickX === undefined || clickY === undefined) return undefined;

    return {
      id: candidateId,
      description,
      tool: 'click',
      arguments: {
        pid: this.pid,
        window_id: this.windowId,
        x: clickX,
        y: clickY,
        capture_id: this.captureId,
        delivery_mode: this.delivery,
      },
      captureId: this.captureId,
      screenshotReference: this.screenshotReference,
      source: 'visual',
    };
  }

  typeText(): undefined {
    return undefined;
  }
}
