import { test, describe } from 'node:test';
import * as assert from 'node:assert/strict';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  ALL_CELLS,
  ClefClient,
  buildClefRequest,
  parseClefResponse,
} from '../clef_adapter.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, '../../fixtures');

describe('TypeScript Clef adapter', () => {
  test('golden fixtures parse properly', () => {
    for (const level of [1, 2, 3]) {
      const fixturePath = path.join(FIXTURES_DIR, `clef-localization-level${level}.json`);
      assert.ok(fs.existsSync(fixturePath), `Missing fixture ${fixturePath}`);

      const data = JSON.parse(fs.readFileSync(fixturePath, 'utf-8'));
      const result = parseClefResponse(data, '@cf/cloudflare/clef', ALL_CELLS);

      assert.equal(result.choice, 'E1');
      assert.ok(result.confidence > 0.7);
      assert.ok('E1' in result.probabilities);
      assert.equal(Object.keys(result.probabilities).length, 25);
    }
  });

  test('fixture replay queue in ClefClient works offline', async () => {
    const fixturePaths = [
      path.join(FIXTURES_DIR, 'clef-localization-level1.json'),
      path.join(FIXTURES_DIR, 'clef-localization-level2.json'),
      path.join(FIXTURES_DIR, 'clef-localization-level3.json'),
    ];
    const client = new ClefClient({ mockFixturePaths: fixturePaths });

    const r1 = await client.evaluateGrid('dummy', 'test target');
    const r2 = await client.evaluateGrid('dummy', 'test target');
    const r3 = await client.evaluateGrid('dummy', 'test target');

    assert.equal(r1.choice, 'E1');
    assert.equal(r2.choice, 'E1');
    assert.equal(r3.choice, 'E1');
  });

  test('non-adjacent competitor lookup skips adjacent neighbors', () => {
    const data = {
      result: {
        answers: {
          target_cell: {
            choice: 'C3',
            probabilities: {
              C3: 0.5,
              C2: 0.3, // adjacent (up)
              B3: 0.15, // adjacent (left)
              A1: 0.05, // non-adjacent
            },
          },
        },
      },
    };
    const result = parseClefResponse(data, 'clef', ALL_CELLS);
    assert.deepEqual(result.topCandidate, ['C3', 0.5]);
    assert.deepEqual(result.runnerUpCandidate, ['C2', 0.3]);
    assert.deepEqual(result.topNonAdjacentCandidate('C3'), ['A1', 0.05]);
  });

  test('buildClefRequest formats valid Workers AI payload', () => {
    const req = buildClefRequest('aW1hZ2U=', 'Locate search icon', undefined, '@cf/cloudflare/clef');
    assert.equal(req.model, 'clef');
    assert.ok(String(req.state).includes('Locate target: Locate search icon'));
    const questions = req.questions as Record<string, any>;
    assert.equal(questions.target_cell.instructions, 'Locate search icon');
  });

  test('rejects malformed responses without network', () => {
    assert.throws(() => parseClefResponse('not-an-object'), /Invalid response payload/);

    assert.throws(
      () =>
        parseClefResponse({
          result: {
            answers: {
              target_cell: {
                choice: 'A1',
                probabilities: { Z9: 0.9 },
              },
            },
          },
        }),
      /Unknown cell score/
    );

    assert.throws(
      () =>
        parseClefResponse({
          result: {
            answers: {
              target_cell: {
                choice: 'A1',
                probabilities: { A1: 'not-a-number' },
              },
            },
          },
        }),
      /Non-numeric probability/
    );

    assert.throws(
      () =>
        parseClefResponse({
          result: {
            answers: {
              target_cell: {
                choice: 'A1',
                probabilities: { A1: Infinity },
              },
            },
          },
        }),
      /Non-finite probability/
    );

    assert.throws(
      () =>
        parseClefResponse({
          result: {
            answers: {
              target_cell: {
                choice: 'A1',
                probabilities: { A1: -0.2 },
              },
            },
          },
        }),
      /Probability out of range/
    );

    assert.throws(
      () =>
        parseClefResponse({
          result: {
            answers: {
              target_cell: {},
            },
          },
        }),
      /Malformed response/
    );
  });
});
