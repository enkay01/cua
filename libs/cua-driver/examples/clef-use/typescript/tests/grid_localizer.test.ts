import { test, describe } from 'node:test';
import * as assert from 'node:assert/strict';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ClefClient, createClefChoiceResult } from '../clef_adapter.js';
import { ClefGridLocalizer } from '../grid_localizer.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, '../../fixtures');

describe('TypeScript ClefGridLocalizer', () => {
  test('three-level hierarchical zoom success with golden fixtures', async () => {
    const fixturePaths = [
      path.join(FIXTURES_DIR, 'clef-localization-level1.json'),
      path.join(FIXTURES_DIR, 'clef-localization-level2.json'),
      path.join(FIXTURES_DIR, 'clef-localization-level3.json'),
    ];
    const client = new ClefClient({ mockFixturePaths: fixturePaths });
    const localizer = new ClefGridLocalizer(client, {
      numLevels: 3,
      customCropSizes: [
        [1290, 803],
        [387, 240],
        [115, 71],
      ],
    });

    const result = await localizer.localize(
      { width: 1290, height: 803 },
      'monitor icon in the menu bar',
      { captureId: 'cap-ts-1', pid: 55, windowId: 2 }
    );

    assert.equal(result.success, true);
    assert.equal(result.status, 'success');
    assert.equal(result.iterations.length, 3);
    assert.equal(result.captureId, 'cap-ts-1');
    assert.equal(result.targetPid, 55);
    assert.equal(result.targetWindowId, 2);
    assert.equal(result.screenshotW, 1290);
    assert.equal(result.screenshotH, 803);

    // Winning cell E1
    assert.equal(result.iterations[0].winningCell, 'E1');
    assert.equal(result.iterations[1].winningCell, 'E1');
    assert.equal(result.iterations[2].winningCell, 'E1');

    assert.ok(result.clickX !== undefined && result.clickX >= 1200 && result.clickX <= 1290);
    assert.ok(result.clickY !== undefined && result.clickY >= 0 && result.clickY <= 50);
  });

  test('abstain on low confidence', async () => {
    const client = new ClefClient({
      mockHandler: () =>
        createClefChoiceResult('C3', 0.15, { C3: 0.15, A1: 0.05 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, { minConfidence: 0.3 });
    const result = await localizer.localize({ width: 500, height: 500 }, 'missing element');

    assert.equal(result.success, false);
    assert.equal(result.status, 'abstained_low_confidence');
    assert.ok(result.reason?.includes('below floor'));
  });

  test('abstain on direct non-adjacent ambiguity', async () => {
    const client = new ClefClient({
      mockHandler: () =>
        createClefChoiceResult('A1', 0.42, { A1: 0.42, E5: 0.4 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, { ambiguityMargin: 0.05 });
    const result = await localizer.localize({ width: 500, height: 500 }, 'ambiguous icon');

    assert.equal(result.success, false);
    assert.equal(result.status, 'abstained_ambiguous');
    assert.ok(result.reason?.includes('Ambiguous candidates'));
  });

  test('allow close scores when adjacent and non-adjacent is far', async () => {
    const client = new ClefClient({
      mockHandler: () =>
        createClefChoiceResult('B2', 0.42, { B2: 0.42, C2: 0.4, E5: 0.1 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, { numLevels: 1, ambiguityMargin: 0.05 });
    const result = await localizer.localize({ width: 500, height: 500 }, 'straddling icon');

    assert.equal(result.success, true);
    assert.equal(result.status, 'success');
  });

  test('abstain when adjacent runner-up has close non-adjacent third place', async () => {
    const client = new ClefClient({
      mockHandler: () =>
        createClefChoiceResult('B2', 0.42, { B2: 0.42, C2: 0.4, E5: 0.39 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, { numLevels: 1, ambiguityMargin: 0.05 });
    const result = await localizer.localize({ width: 500, height: 500 }, 'bimodal straddle');

    assert.equal(result.success, false);
    assert.equal(result.status, 'abstained_ambiguous');
    assert.ok(result.reason?.includes('E5'));
  });

  test('timeout deadline exceeded returns abstained_timeout', async () => {
    const client = new ClefClient({
      mockHandler: async () => {
        await new Promise((r) => setTimeout(r, 40));
        return createClefChoiceResult('C3', 0.8, { C3: 0.8 }, 'mock', {});
      },
    });
    const localizer = new ClefGridLocalizer(client, { numLevels: 3, deadlineMs: 20 });
    const result = await localizer.localize({ width: 500, height: 500 }, 'slow button');

    assert.equal(result.success, false);
    assert.equal(result.status, 'abstained_timeout');
    assert.ok(result.reason?.includes('deadline'));
  });

  test('capture and observation matching', async () => {
    const client = new ClefClient({
      mockHandler: () =>
        createClefChoiceResult('C3', 0.9, { C3: 0.9 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, { numLevels: 1 });
    const result = await localizer.localize(
      { width: 800, height: 600 },
      'button',
      { captureId: 'cap-99', pid: 101, windowId: 202 }
    );

    assert.equal(result.success, true);
    assert.equal(
      result.matchesObservation({
        captureId: 'cap-99',
        pid: 101,
        windowId: 202,
        width: 800,
        height: 600,
      }),
      true
    );

    // Mismatches
    assert.equal(result.matchesObservation({ captureId: 'cap-other' }), false);
    assert.equal(result.matchesObservation({ pid: 999 }), false);
    assert.equal(result.matchesObservation({ windowId: 999 }), false);
    assert.equal(result.matchesObservation({ width: 1024 }), false);
  });

  test('oversized crop rejection throws before model submission', async () => {
    const client = new ClefClient({
      mockHandler: () => createClefChoiceResult('C3', 0.9, { C3: 0.9 }, 'mock', {}),
    });
    const localizer = new ClefGridLocalizer(client, {
      numLevels: 2,
      customCropSizes: [
        [200, 200],
        [500, 500],
      ],
    });

    await assert.rejects(
      () => localizer.localize({ width: 200, height: 200 }, 'test'),
      /exceeds screenshot dimensions/
    );
  });
});
