import { test, describe } from 'node:test';
import * as assert from 'node:assert/strict';
import {
  COLUMNS,
  ROWS,
  ALL_CELLS,
  parseCellName,
  areAdjacent,
  clampCropWindow,
  getCellGeometry,
  getAllCellGeometries,
  renderGridSvgOverlay,
} from '../grid_localizer.js';

describe('TypeScript grid math', () => {
  test('parseCellName parses valid and throws on invalid', () => {
    assert.deepEqual(parseCellName('A1'), [0, 0]);
    assert.deepEqual(parseCellName('E5'), [4, 4]);
    assert.deepEqual(parseCellName('c3'), [2, 2]);
    assert.deepEqual(parseCellName(' B4 '), [1, 3]);

    assert.throws(() => parseCellName('F1'), /Invalid column/);
    assert.throws(() => parseCellName('A6'), /Invalid row/);
    assert.throws(() => parseCellName('A'), /Must be 2 characters/);
    assert.throws(() => parseCellName('A11'), /Must be 2 characters/);
  });

  test('areAdjacent detects neighbors correctly', () => {
    assert.equal(areAdjacent('C3', 'C3'), true);
    assert.equal(areAdjacent('C3', 'C2'), true);
    assert.equal(areAdjacent('C3', 'C4'), true);
    assert.equal(areAdjacent('C3', 'B3'), true);
    assert.equal(areAdjacent('C3', 'D3'), true);
    assert.equal(areAdjacent('C3', 'B2'), true);
    assert.equal(areAdjacent('C3', 'D4'), true);

    assert.equal(areAdjacent('A1', 'C1'), false);
    assert.equal(areAdjacent('A1', 'A3'), false);
    assert.equal(areAdjacent('A1', 'E5'), false);
    assert.equal(areAdjacent('D1', 'A5'), false);
  });

  test('clampCropWindow handles centered crops', () => {
    const box = clampCropWindow(500, 400, 400, 300, 1000, 800);
    assert.equal(box.left, 300);
    assert.equal(box.top, 250);
    assert.equal(box.right, 700);
    assert.equal(box.bottom, 550);
    assert.equal(box.width, 400);
    assert.equal(box.height, 300);
  });

  test('clampCropWindow never shrinks at top-left and bottom-right', () => {
    const tl = clampCropWindow(0, 0, 300, 200, 1280, 720);
    assert.equal(tl.left, 0);
    assert.equal(tl.top, 0);
    assert.equal(tl.right, 300);
    assert.equal(tl.bottom, 200);

    const br = clampCropWindow(1280, 720, 300, 200, 1280, 720);
    assert.equal(br.left, 980);
    assert.equal(br.top, 520);
    assert.equal(br.right, 1280);
    assert.equal(br.bottom, 720);
  });

  test('clampCropWindow rejects oversized crops', () => {
    assert.throws(() => clampCropWindow(100, 100, 2000, 500, 1280, 720), /exceeds image dimensions/);
    assert.throws(() => clampCropWindow(100, 100, 500, 1500, 1280, 720), /exceeds image dimensions/);
  });

  test('fractional center and edge fixtures match Python outcomes', () => {
    const box = clampCropWindow(387.5, 241.5, 100, 80, 500, 400);
    assert.equal(box.left, 338);
    assert.equal(box.top, 202);
    assert.equal(box.width, 100);
    assert.equal(box.height, 80);

    const edge = clampCropWindow(50.0, 40.0, 100, 80, 500, 400);
    assert.equal(edge.left, 0);
    assert.equal(edge.top, 0);
    assert.equal(edge.right, 100);
    assert.equal(edge.bottom, 80);
  });

  test('cell geometry partitions 5x5 correctly', () => {
    const cropBox = {
      left: 100,
      top: 200,
      right: 600,
      bottom: 700,
      width: 500,
      height: 500,
      centerX: 350,
      centerY: 450,
    };

    const geometries = getAllCellGeometries(cropBox);
    assert.equal(Object.keys(geometries).length, 25);

    const a1 = geometries['A1'];
    assert.equal(a1.cropX0, 0);
    assert.equal(a1.cropX1, 100);
    assert.equal(a1.cropY0, 0);
    assert.equal(a1.cropY1, 100);
    assert.equal(a1.rootCenterX, 150);
    assert.equal(a1.rootCenterY, 250);

    const e5 = geometries['E5'];
    assert.equal(e5.cropX0, 400);
    assert.equal(e5.cropX1, 500);
    assert.equal(e5.rootCenterX, 550);
    assert.equal(e5.rootCenterY, 650);
  });

  test('renderGridSvgOverlay produces valid SVG with cells', () => {
    const svg = renderGridSvgOverlay(250, 250, { highlightCell: 'E1' });
    assert.ok(svg.includes('<svg width="250" height="250"'));
    assert.ok(svg.includes('<text'));
    assert.ok(svg.includes('E1</text>'));
    assert.ok(svg.includes('<rect'));
  });
});
