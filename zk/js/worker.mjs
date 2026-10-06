// Line-oriented JSON worker for the V4 proofs (Groth16 membership and BBS).
// One request per line on stdin, one response per line on stdout.

import { createInterface } from "node:readline";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as snarkjs from "snarkjs";
import { buildPoseidon } from "circomlibjs";
import * as bbs from "@digitalbazaar/bbs-signatures";

const here = path.dirname(fileURLToPath(import.meta.url));
const build = path.join(here, "..", "build");
const WASM = path.join(build, "payee_membership_js", "payee_membership.wasm");
const ZKEY = path.join(build, "membership_final.zkey");
let VKEY = null;

const poseidon = await buildPoseidon();
const F = poseidon.F;
const H = (xs) => F.toString(poseidon(xs.map((x) => BigInt(x))));

const zeroCache = [];
function zeros(depth) {
  if (zeroCache.length === 0) zeroCache.push("0");
  while (zeroCache.length <= depth) {
    const z = zeroCache[zeroCache.length - 1];
    zeroCache.push(H([z, z]));
  }
  return zeroCache;
}

// Sparse left-packed Merkle tree; empty leaves are 0.
function tree(leaves, depth) {
  const z = zeros(depth);
  let level = leaves.map(String);
  const levels = [level];
  for (let d = 0; d < depth; d++) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      const l = level[i];
      const r = i + 1 < level.length ? level[i + 1] : z[d];
      next.push(H([l, r]));
    }
    if (next.length === 0) next.push(z[d + 1]);
    level = next;
    levels.push(level);
  }
  const paths = leaves.map((_, idx) => {
    const elements = [];
    const indices = [];
    let j = idx;
    for (let d = 0; d < depth; d++) {
      const sib = j ^ 1;
      elements.push(sib < levels[d].length ? levels[d][sib] : z[d]);
      indices.push(j & 1);
      j >>= 1;
    }
    return { elements, indices };
  });
  return { root: levels[depth][0], paths };
}

const hex = (u8) => Buffer.from(u8).toString("hex");
const unhex = (h) => new Uint8Array(Buffer.from(h, "hex"));
const CS = "BLS12-381-SHA-256";

async function handle(req) {
  switch (req.op) {
    case "ping":
      return { ok: true };
    case "poseidon":
      return { hash: H(req.inputs) };
    case "tree":
      return tree(req.leaves, req.depth ?? 16);
    case "prove": {
      const t0 = performance.now();
      const { proof, publicSignals } = await snarkjs.groth16.fullProve(req.input, WASM, ZKEY);
      const ms = performance.now() - t0;
      return { proof, publicSignals, ms, bytes: JSON.stringify(proof).length };
    }
    case "verify": {
      if (VKEY === null) VKEY = JSON.parse(readFileSync(path.join(build, "verification_key.json")));
      const t0 = performance.now();
      const ok = await snarkjs.groth16.verify(VKEY, req.publicSignals, req.proof);
      return { ok, ms: performance.now() - t0 };
    }
    case "bbs_keygen": {
      const kp = await bbs.generateKeyPair({ ciphersuite: CS, seed: req.seed ? unhex(req.seed) : undefined });
      return { sk: hex(kp.secretKey), pk: hex(kp.publicKey) };
    }
    case "bbs_sign": {
      const t0 = performance.now();
      const sig = await bbs.sign({
        secretKey: unhex(req.sk), publicKey: unhex(req.pk), header: unhex(req.header ?? ""),
        messages: req.messages.map(unhex), ciphersuite: CS,
      });
      return { sig: hex(sig), ms: performance.now() - t0 };
    }
    case "bbs_derive": {
      const t0 = performance.now();
      const proof = await bbs.deriveProof({
        publicKey: unhex(req.pk), signature: unhex(req.sig), header: unhex(req.header ?? ""),
        messages: req.messages.map(unhex), presentationHeader: unhex(req.ph ?? ""),
        disclosedMessageIndexes: req.disclosed, ciphersuite: CS,
      });
      return { proof: hex(proof), ms: performance.now() - t0, bytes: proof.length };
    }
    case "bbs_verify": {
      const t0 = performance.now();
      const ok = await bbs.verifyProof({
        publicKey: unhex(req.pk), proof: unhex(req.proof), header: unhex(req.header ?? ""),
        presentationHeader: unhex(req.ph ?? ""), disclosedMessages: req.disclosedMessages.map(unhex),
        disclosedMessageIndexes: req.disclosed, ciphersuite: CS,
      });
      return { ok, ms: performance.now() - t0 };
    }
    default:
      throw new Error(`unknown op ${req.op}`);
  }
}

const rl = createInterface({ input: process.stdin });
for await (const line of rl) {
  if (!line.trim()) continue;
  let req;
  try {
    req = JSON.parse(line);
    const res = await handle(req);
    process.stdout.write(JSON.stringify({ id: req.id, ...res }) + "\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({ id: req?.id, error: String(err?.stack ?? err) }) + "\n");
  }
}
if (globalThis.curve_bn128) await globalThis.curve_bn128.terminate();
process.exit(0);
