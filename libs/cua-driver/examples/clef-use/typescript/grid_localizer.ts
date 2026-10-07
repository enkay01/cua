import { type ClefChoiceResult, ClefClient } from './clef_adapter.js';

export const COLUMNS = ['A', 'B', 'C', 'D', 'E'] as const;
export const ROWS = ['1', '2', '3', '4', '5'] as const;
export const ALL_CELLS: string[] = ROWS.flatMap((r) => COLUMNS.map((c) => `${c}${r}`));

export interface CropBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

export interface CellGeometry {
  name: string;
  col: string;
  row: string;
  colIdx: number;
  rowIdx: number;
  cropX0: number;
  cropY0: number;
  cropX1: number;
  cropY1: number;
  cropCenterX: number;
  cropCenterY: number;
  rootCenterX: number;
  rootCenterY: number;
}

export function parseCellName(cellName: string): [number, number] {
  const name = cellName.trim().toUpperCase();
  if (name.length !== 2) {
    throw new Error(`Invalid cell name: "${cellName}". Must be 2 characters (e.g. 'A1', 'E5').`);
  }
  const colChar = name[0];
  const rowChar = name[1];
  const colIdx = COLUMNS.indexOf(colChar as (typeof COLUMNS)[number]);
  if (colIdx === -1) {
    throw new Error(`Invalid column: "${colChar}" in cell "${cellName}". Allowed: ${COLUMNS.join(', ')}`);
  }
  const rowIdx = ROWS.indexOf(rowChar as (typeof ROWS)[number]);
  if (rowIdx === -1) {
    throw new Error(`Invalid row: "${rowChar}" in cell "${cellName}". Allowed: ${ROWS.join(', ')}`);
  }
  return [colIdx, rowIdx];
}

export function areAdjacent(cell1: string, cell2: string): boolean {
  const [c1, r1] = parseCellName(cell1);
  const [c2, r2] = parseCellName(cell2);
  return Math.abs(c1 - c2) <= 1 && Math.abs(r1 - r2) <= 1;
}

export function clampCropWindow(
  centerX: number,
  centerY: number,
  cropW: number,
  cropH: number,
  imageW: number,
  imageH: number
): CropBox {
  if (imageW <= 0 || imageH <= 0) {
    throw new Error(`Image dimensions must be positive, got (${imageW}, ${imageH})`);
  }
  if (cropW <= 0 || cropH <= 0) {
    throw new Error(`Crop dimensions must be positive, got (${cropW}, ${cropH})`);
  }
  if (cropW > imageW || cropH > imageH) {
    throw new Error(
      `Configured crop size (${cropW}, ${cropH}) exceeds image dimensions (${imageW}, ${imageH})`
    );
  }

  const newLeft = cropW === imageW
    ? 0
    : Math.max(0, Math.min(Math.round(centerX - cropW / 2.0), imageW - cropW));

  const newTop = cropH === imageH
    ? 0
    : Math.max(0, Math.min(Math.round(centerY - cropH / 2.0), imageH - cropH));

  const newRight = newLeft + cropW;
  const newBottom = newTop + cropH;

  return {
    left: newLeft,
    top: newTop,
    right: newRight,
    bottom: newBottom,
    width: cropW,
    height: cropH,
    centerX: (newLeft + newRight) / 2.0,
    centerY: (newTop + newBottom) / 2.0,
  };
}

export function getCellGeometry(cellName: string, cropBox: CropBox): CellGeometry {
  const [colIdx, rowIdx] = parseCellName(cellName);
  const w = cropBox.width;
  const h = cropBox.height;

  const x0 = Math.round((colIdx * w) / 5.0);
  const x1 = Math.round(((colIdx + 1) * w) / 5.0);
  const y0 = Math.round((rowIdx * h) / 5.0);
  const y1 = Math.round(((rowIdx + 1) * h) / 5.0);

  const cx = (x0 + x1) / 2.0;
  const cy = (y0 + y1) / 2.0;

  return {
    name: cellName.trim().toUpperCase(),
    col: COLUMNS[colIdx],
    row: ROWS[rowIdx],
    colIdx,
    rowIdx,
    cropX0: x0,
    cropY0: y0,
    cropX1: x1,
    cropY1: y1,
    cropCenterX: cx,
    cropCenterY: cy,
    rootCenterX: cropBox.left + cx,
    rootCenterY: cropBox.top + cy,
  };
}

export function getAllCellGeometries(cropBox: CropBox): Record<string, CellGeometry> {
  const result: Record<string, CellGeometry> = {};
  for (const cell of ALL_CELLS) {
    result[cell] = getCellGeometry(cell, cropBox);
  }
  return result;
}

export interface GridOverlayOptions {
  lineColor?: string;
  lineWidth?: number;
  drawLabels?: boolean;
  labelColor?: string;
  highlightCell?: string;
  highlightColor?: string;
}

export function renderGridSvgOverlay(
  width: number,
  height: number,
  options: GridOverlayOptions = {}
): string {
  const lineColor = options.lineColor || '#00ff78';
  const lineWidth = options.lineWidth || 1;
  const drawLabels = options.drawLabels !== false;
  const labelColor = options.labelColor || '#00ff78';
  const highlightCell = options.highlightCell ? options.highlightCell.trim().toUpperCase() : null;
  const highlightColor = options.highlightColor || '#ff3c3c';

  const lines: string[] = [];

  // Vertical lines
  for (let c = 1; c < 5; c++) {
    const x = Math.round((c * width) / 5.0);
    lines.push(`<line x1="${x}" y1="0" x2="${x}" y2="${height}" stroke="${lineColor}" stroke-width="${lineWidth}" />`);
  }

  // Horizontal lines
  for (let r = 1; r < 5; r++) {
    const y = Math.round((r * height) / 5.0);
    lines.push(`<line x1="0" y1="${y}" x2="${width}" y2="${y}" stroke="${lineColor}" stroke-width="${lineWidth}" />`);
  }

  // Highlight rectangle
  if (highlightCell) {
    const [colIdx, rowIdx] = parseCellName(highlightCell);
    const x0 = Math.round((colIdx * width) / 5.0);
    const x1 = Math.round(((colIdx + 1) * width) / 5.0);
    const y0 = Math.round((rowIdx * height) / 5.0);
    const y1 = Math.round(((rowIdx + 1) * height) / 5.0);
    lines.push(
      `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="none" stroke="${highlightColor}" stroke-width="${Math.max(2, lineWidth + 1)}" />`
    );
  }

  // Labels
  if (drawLabels) {
    for (const cell of ALL_CELLS) {
      const [colIdx, rowIdx] = parseCellName(cell);
      const x0 = Math.round((colIdx * width) / 5.0);
      const y0 = Math.round((rowIdx * height) / 5.0);
      const color = highlightCell === cell ? highlightColor : labelColor;
      lines.push(
        `<text x="${x0 + 4}" y="${y0 + 12}" fill="${color}" font-family="monospace" font-size="10">${cell}</text>`
      );
    }
  }

  return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">${lines.join('')}</svg>`;
}

export function renderGridOverlay(
  image: { width: number; height: number },
  options: GridOverlayOptions = {}
): { width: number; height: number; svg: string } {
  return {
    width: image.width,
    height: image.height,
    svg: renderGridSvgOverlay(image.width, image.height, options),
  };
}

export interface LocalizerImageDimensions {
  width: number;
  height: number;
}

export interface LocalizerImageObject {
  width?: number;
  height?: number;
  base64?: string;
  dataUri?: string;
  buffer?: Buffer;
}

export type LocalizerImageInput =
  | LocalizerImageDimensions
  | LocalizerImageObject
  | Buffer
  | string;

export function getImageDimensionsFromBuffer(buf: Buffer): { width: number; height: number } {
  // PNG: signature 0x89 0x50 0x4e 0x47
  if (
    buf.length >= 24 &&
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47
  ) {
    const width = buf.readUInt32BE(16);
    const height = buf.readUInt32BE(20);
    return { width, height };
  }

  // JPEG: starts with 0xff 0xd8
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
    let offset = 2;
    while (offset < buf.length) {
      if (buf[offset] !== 0xff) {
        offset++;
        continue;
      }
      const marker = buf[offset + 1];
      if (marker >= 0xc0 && marker <= 0xc3) {
        const height = buf.readUInt16BE(offset + 5);
        const width = buf.readUInt16BE(offset + 7);
        return { width, height };
      }
      offset += 2 + buf.readUInt16BE(offset + 2);
    }
  }

  throw new Error('Unsupported image format or failed to read dimensions from buffer');
}

export function stripDataUriPrefix(value: string): string {
  return value.replace(/^data:[^;]+;base64,/, '').trim();
}

export function resolveImageInput(image: LocalizerImageInput): {
  width: number;
  height: number;
  base64?: string;
} {
  if (Buffer.isBuffer(image)) {
    const dims = getImageDimensionsFromBuffer(image);
    return {
      width: dims.width,
      height: dims.height,
      base64: image.toString('base64'),
    };
  }

  if (typeof image === 'string') {
    const rawBase64 = stripDataUriPrefix(image);
    const buf = Buffer.from(rawBase64, 'base64');
    const dims = getImageDimensionsFromBuffer(buf);
    return {
      width: dims.width,
      height: dims.height,
      base64: rawBase64,
    };
  }

  if (typeof image === 'object' && image !== null) {
    let rawBase64: string | undefined;
    if ('base64' in image && typeof (image as { base64?: unknown }).base64 === 'string') {
      rawBase64 = stripDataUriPrefix((image as { base64: string }).base64);
    } else if ('dataUri' in image && typeof (image as { dataUri?: unknown }).dataUri === 'string') {
      rawBase64 = stripDataUriPrefix((image as { dataUri: string }).dataUri);
    } else if ('buffer' in image && Buffer.isBuffer((image as { buffer?: unknown }).buffer)) {
      rawBase64 = (image as { buffer: Buffer }).buffer.toString('base64');
    }

    let width = 'width' in image && typeof (image as { width?: unknown }).width === 'number'
      ? (image as { width: number }).width
      : undefined;
    let height = 'height' in image && typeof (image as { height?: unknown }).height === 'number'
      ? (image as { height: number }).height
      : undefined;

    if ((width === undefined || height === undefined) && rawBase64) {
      const buf = Buffer.from(rawBase64, 'base64');
      const dims = getImageDimensionsFromBuffer(buf);
      width = dims.width;
      height = dims.height;
    }

    if (width === undefined || height === undefined) {
      throw new Error(
        'Image dimensions (width, height) must be provided or derivable from image data'
      );
    }

    return {
      width,
      height,
      base64: rawBase64,
    };
  }

  throw new Error(`Unsupported image input type: ${typeof image}`);
}

export interface IterationRecord {
  level: number;
  cropBox: CropBox;
  winningCell: string;
  confidence: number;
  probabilities: Record<string, number>;
  cellGeometry: CellGeometry;
  result: ClefChoiceResult;
}

export interface LocalizationResult {
  success: boolean;
  status: string;
  targetDescription: string;
  clickX?: number;
  clickY?: number;
  captureId?: string;
  targetPid?: number;
  targetWindowId?: number;
  screenshotW?: number;
  screenshotH?: number;
  iterations: IterationRecord[];
  reason?: string;
  matchesObservation(observation: {
    captureId?: string;
    pid?: number;
    windowId?: number;
    width?: number;
    height?: number;
  }): boolean;
}

export function createLocalizationResult(init: Omit<LocalizationResult, 'matchesObservation'>): LocalizationResult {
  return {
    ...init,
    matchesObservation(obs) {
      if (!init.success) return false;
      if (init.captureId !== undefined && obs.captureId !== init.captureId) {
        return false;
      }
      if (init.targetPid !== undefined && obs.pid !== undefined && obs.pid !== init.targetPid) {
        return false;
      }
      if (init.targetWindowId !== undefined && obs.windowId !== undefined && obs.windowId !== init.targetWindowId) {
        return false;
      }
      if (init.screenshotW !== undefined && obs.width !== undefined && obs.width !== init.screenshotW) {
        return false;
      }
      if (init.screenshotH !== undefined && obs.height !== undefined && obs.height !== init.screenshotH) {
        return false;
      }
      return true;
    },
  };
}

export interface LocalizerOptions {
  numLevels?: number;
  zoomFactor?: number;
  customCropSizes?: [number, number][];
  minConfidence?: number;
  ambiguityMargin?: number;
  deadlineMs?: number;
}

export interface LocalizeRunOptions {
  captureId?: string;
  pid?: number;
  windowId?: number;
  timeoutMs?: number;
}

export class ClefGridLocalizer {
  public client: ClefClient;
  public numLevels: number;
  public zoomFactor: number;
  public customCropSizes?: [number, number][];
  public minConfidence: number;
  public ambiguityMargin: number;
  public deadlineMs: number;

  constructor(client: ClefClient, options: LocalizerOptions = {}) {
    this.client = client;
    this.numLevels = options.numLevels || 3;
    this.zoomFactor = options.zoomFactor || 3.33;
    this.customCropSizes = options.customCropSizes;
    this.minConfidence = options.minConfidence !== undefined ? options.minConfidence : 0.25;
    this.ambiguityMargin = options.ambiguityMargin !== undefined ? options.ambiguityMargin : 0.05;
    this.deadlineMs = options.deadlineMs !== undefined ? options.deadlineMs : 30000;
  }

  private determineCropDimensions(level: number, rootW: number, rootH: number): [number, number] {
    if (level === 1) {
      return [rootW, rootH];
    }
    if (this.customCropSizes && level <= this.customCropSizes.length) {
      return this.customCropSizes[level - 1];
    }
    const scale = Math.pow(this.zoomFactor, level - 1);
    const w = Math.max(40, Math.round(rootW / scale));
    const h = Math.max(30, Math.round(rootH / scale));
    return [w, h];
  }

  public async localize(
    image: LocalizerImageInput,
    targetDescription: string,
    options: LocalizeRunOptions = {}
  ): Promise<LocalizationResult> {
    const resolved = resolveImageInput(image);
    const rootW = resolved.width;
    const rootH = resolved.height;
    const screenshotBase64 = resolved.base64;
    let activeCenterX = rootW / 2.0;
    let activeCenterY = rootH / 2.0;
    const records: IterationRecord[] = [];

    const effectiveTimeout = options.timeoutMs !== undefined ? options.timeoutMs : this.deadlineMs;
    if (effectiveTimeout <= 0) {
      return createLocalizationResult({
        success: false,
        status: 'abstained_timeout',
        targetDescription,
        captureId: options.captureId,
        targetPid: options.pid,
        targetWindowId: options.windowId,
        screenshotW: rootW,
        screenshotH: rootH,
        iterations: records,
        reason: `Inference deadline ${effectiveTimeout}ms exceeded`,
      });
    }
    const startTime = Date.now();
    const deadline = Number.isFinite(effectiveTimeout) ? startTime + effectiveTimeout : Infinity;

    for (let level = 1; level <= this.numLevels; level++) {
      if (Date.now() >= deadline) {
        return createLocalizationResult({
          success: false,
          status: 'abstained_timeout',
          targetDescription,
          captureId: options.captureId,
          targetPid: options.pid,
          targetWindowId: options.windowId,
          screenshotW: rootW,
          screenshotH: rootH,
          iterations: records,
          reason: `Inference deadline ${effectiveTimeout}ms exceeded before level ${level}`,
        });
      }

      const [cropW, cropH] = this.determineCropDimensions(level, rootW, rootH);

      if (cropW > rootW || cropH > rootH) {
        throw new Error(
          `Configured crop size (${cropW}, ${cropH}) exceeds screenshot dimensions (${rootW}, ${rootH})`
        );
      }

      const cropBox = clampCropWindow(activeCenterX, activeCenterY, cropW, cropH, rootW, rootH);
      const overlay = renderGridOverlay({ width: cropW, height: cropH });

      const payloadImage = screenshotBase64 ?? overlay.svg;

      if (deadline !== Infinity) {
        const remainingMs = deadline - Date.now();
        if (remainingMs <= 0) {
          return createLocalizationResult({
            success: false,
            status: 'abstained_timeout',
            targetDescription,
            captureId: options.captureId,
            targetPid: options.pid,
            targetWindowId: options.windowId,
            screenshotW: rootW,
            screenshotH: rootH,
            iterations: records,
            reason: `Inference deadline ${effectiveTimeout}ms exceeded before level ${level}`,
          });
        }
      }

      const remainingTimeMs =
        deadline !== Infinity ? Math.max(1, deadline - Date.now()) : undefined;
      const prompt = `Select the grid cell containing ${targetDescription}`;

      let evalResult: ClefChoiceResult;
      try {
        evalResult = await this.client.evaluateGrid(payloadImage, prompt, undefined, remainingTimeMs);
      } catch (err: unknown) {
        if (
          err instanceof Error &&
          (err.name === 'TimeoutError' ||
            err.name === 'AbortError' ||
            err.message.toLowerCase().includes('timeout') ||
            err.message.toLowerCase().includes('aborted'))
        ) {
          return createLocalizationResult({
            success: false,
            status: 'abstained_timeout',
            targetDescription,
            captureId: options.captureId,
            targetPid: options.pid,
            targetWindowId: options.windowId,
            screenshotW: rootW,
            screenshotH: rootH,
            iterations: records,
            reason: `Inference timed out during level ${level}`,
          });
        }
        throw err;
      }

      const [topCell, topConf] = evalResult.topCandidate;
      if (topConf < this.minConfidence) {
        return createLocalizationResult({
          success: false,
          status: 'abstained_low_confidence',
          targetDescription,
          captureId: options.captureId,
          targetPid: options.pid,
          targetWindowId: options.windowId,
          screenshotW: rootW,
          screenshotH: rootH,
          iterations: records,
          reason: `Top candidate ${topCell} confidence ${topConf.toFixed(3)} below floor ${this.minConfidence}`,
        });
      }

      const nonAdj = evalResult.topNonAdjacentCandidate(topCell);
      if (nonAdj) {
        const [nonAdjCell, nonAdjConf] = nonAdj;
        const margin = topConf - nonAdjConf;
        if (margin < this.ambiguityMargin) {
          return createLocalizationResult({
            success: false,
            status: 'abstained_ambiguous',
            targetDescription,
            captureId: options.captureId,
            targetPid: options.pid,
            targetWindowId: options.windowId,
            screenshotW: rootW,
            screenshotH: rootH,
            iterations: records,
            reason: `Ambiguous candidates: top cell ${topCell} (${topConf.toFixed(3)}) and non-adjacent competitor ${nonAdjCell} (${nonAdjConf.toFixed(3)}) separated by margin ${margin.toFixed(3)} < ${this.ambiguityMargin}`,
          });
        }
      }

      const geom = getCellGeometry(topCell, cropBox);
      records.push({
        level,
        cropBox,
        winningCell: topCell,
        confidence: topConf,
        probabilities: evalResult.probabilities,
        cellGeometry: geom,
        result: evalResult,
      });

      activeCenterX = geom.rootCenterX;
      activeCenterY = geom.rootCenterY;
    }

    const finalRecord = records[records.length - 1];
    return createLocalizationResult({
      success: true,
      status: 'success',
      targetDescription,
      clickX: finalRecord.cellGeometry.rootCenterX,
      clickY: finalRecord.cellGeometry.rootCenterY,
      captureId: options.captureId,
      targetPid: options.pid,
      targetWindowId: options.windowId,
      screenshotW: rootW,
      screenshotH: rootH,
      iterations: records,
    });
  }
}
