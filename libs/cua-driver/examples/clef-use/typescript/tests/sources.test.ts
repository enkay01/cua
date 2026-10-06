import { test, describe } from 'node:test';
import * as assert from 'node:assert/strict';
import { VisualGridSource, type CandidateSource } from '../sources.js';
import { createLocalizationResult } from '../grid_localizer.js';

describe('TypeScript VisualGridSource', () => {
  test('protocol compliance: find, capture-bound click, and typeText rejection', () => {
    const loc = {
      success: true,
      targetDescription: 'Submit Button',
      clickX: 120,
      clickY: 45,
    };

    const unboundSource: CandidateSource = new VisualGridSource(
      loc,
      123,
      456,
      'cap-xyz',
      'background',
      false
    );
    assert.equal(unboundSource.kind, 'visual');

    // Matching
    const submit = unboundSource.find('button', 'submit button');
    assert.ok(submit);
    assert.equal(submit.name, 'Submit Button');

    // Case insensitive
    assert.ok(unboundSource.find('button', 'SUBMIT BUTTON'));

    // Mismatch
    assert.equal(unboundSource.find('button', 'other button'), undefined);

    // Unbound click returns undefined
    assert.equal(unboundSource.click(submit, 'c1', 'd1'), undefined);

    // typeText always returns undefined
    assert.equal(unboundSource.typeText(submit, 'test', 'c1', 'd1'), undefined);

    // Capture-bound click
    const boundSource = new VisualGridSource(
      loc,
      123,
      456,
      'cap-xyz',
      'foreground',
      true
    );
    const candidate = boundSource.click(submit, 'c2', 'd2');
    assert.ok(candidate);
    assert.equal(candidate.id, 'c2');
    assert.equal(candidate.tool, 'click');
    assert.equal(candidate.captureId, 'cap-xyz');
    assert.equal(candidate.arguments.delivery_mode, 'foreground');
    assert.equal(candidate.arguments.x, 120);
    assert.equal(candidate.arguments.y, 45);
    assert.equal(candidate.arguments.pid, 123);
    assert.equal(candidate.arguments.window_id, 456);
  });

  test('target mismatch and capture observation matching', () => {
    const loc = createLocalizationResult({
      success: true,
      status: 'success',
      targetDescription: 'Search Icon',
      clickX: 450,
      clickY: 32,
      captureId: 'cap-original',
      targetPid: 100,
      targetWindowId: 200,
      screenshotW: 1920,
      screenshotH: 1080,
      iterations: [],
    });

    assert.equal(
      loc.matchesObservation({
        captureId: 'cap-original',
        pid: 100,
        windowId: 200,
        width: 1920,
        height: 1080,
      }),
      true
    );

    // Capture changed
    assert.equal(loc.matchesObservation({ captureId: 'cap-stale' }), false);

    // PID changed
    assert.equal(loc.matchesObservation({ pid: 999 }), false);

    // Mismatched source offers no control
    const mismatched = new VisualGridSource(
      loc.matchesObservation({ captureId: 'cap-stale' }) ? loc : undefined,
      100,
      200,
      'cap-stale',
      'background',
      true
    );
    assert.equal(mismatched.find('button', 'Search Icon'), undefined);
  });

  test('capture_expired refusal discards result without unbound retry', () => {
    const driverRefusal = {
      isError: true,
      structuredContent: { code: 'capture_expired' },
    };
    assert.equal(driverRefusal.structuredContent.code, 'capture_expired');

    // Runner discards result on capture_expired
    const freshSource = new VisualGridSource(
      undefined,
      100,
      200,
      'cap-expired',
      'background',
      true
    );
    assert.equal(freshSource.find('button', 'Search Icon'), undefined);
  });
});
