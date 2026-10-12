import test from 'node:test';
import assert from 'node:assert/strict';
import { Backend } from '../host/backend.mjs';

test('lab refuses every backend operation before invoking privileged processes', async () => {
  const previous = process.env.CG_LAB;
  process.env.CG_LAB = '1';
  try {
    for (const op of ['doctor', 'start', 'stop', 'recover', 'pair', 'status']) {
      await assert.rejects(new Backend().call(op), /Laboratório/);
    }
  } finally {
    if (previous === undefined) delete process.env.CG_LAB;
    else process.env.CG_LAB = previous;
  }
});
