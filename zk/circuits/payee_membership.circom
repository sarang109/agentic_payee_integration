pragma circom 2.1.0;

// V4 private payee membership.
//
// The Merchant Transparency Log keeps, per brand, a Poseidon Merkle root over
// leaves that summarise an admitted committed route:
//
//   leaf = Poseidon(brand, payee, termCommit, railsMask, curMask, ceiling,
//                   mccMask, geoMask, notBefore, notAfter)
//
// The prover shows that some leaf under `root` names the brand and payee the
// verifier sees, and that its scope contains the payment tuple, without
// revealing the scope, the leaf position or any intermediary.
// termCommit is a hiding commitment to the terminal account.

include "../js/node_modules/circomlib/circuits/poseidon.circom";
include "../js/node_modules/circomlib/circuits/comparators.circom";
include "../js/node_modules/circomlib/circuits/bitify.circom";

template SelectBit(n) {
    signal input mask;
    signal input idx;
    signal output out;

    component bits = Num2Bits(n);
    bits.in <== mask;
    component eq[n];
    signal acc[n + 1];
    acc[0] <== 0;
    for (var i = 0; i < n; i++) {
        eq[i] = IsEqual();
        eq[i].in[0] <== idx;
        eq[i].in[1] <== i;
        acc[i + 1] <== acc[i] + eq[i].out * bits.out[i];
    }
    out <== acc[n];
}

template PayeeMembership(depth) {
    // public inputs
    signal input root;
    signal input brand;
    signal input payee;
    signal input termCommit;
    signal input rail;
    signal input currency;
    signal input amount;
    signal input mcc;
    signal input geo;
    signal input t;

    // private inputs
    signal input railsMask;
    signal input curMask;
    signal input ceiling;
    signal input mccMask;
    signal input geoMask;
    signal input notBefore;
    signal input notAfter;
    signal input pathElements[depth];
    signal input pathIndices[depth];

    component leaf = Poseidon(10);
    leaf.inputs[0] <== brand;
    leaf.inputs[1] <== payee;
    leaf.inputs[2] <== termCommit;
    leaf.inputs[3] <== railsMask;
    leaf.inputs[4] <== curMask;
    leaf.inputs[5] <== ceiling;
    leaf.inputs[6] <== mccMask;
    leaf.inputs[7] <== geoMask;
    leaf.inputs[8] <== notBefore;
    leaf.inputs[9] <== notAfter;

    component h[depth];
    signal cur[depth + 1];
    signal left[depth];
    signal right[depth];
    cur[0] <== leaf.out;
    for (var i = 0; i < depth; i++) {
        pathIndices[i] * (1 - pathIndices[i]) === 0;
        left[i] <== cur[i] + pathIndices[i] * (pathElements[i] - cur[i]);
        right[i] <== pathElements[i] + pathIndices[i] * (cur[i] - pathElements[i]);
        h[i] = Poseidon(2);
        h[i].inputs[0] <== left[i];
        h[i].inputs[1] <== right[i];
        cur[i + 1] <== h[i].out;
    }
    root === cur[depth];

    component r = SelectBit(16);
    r.mask <== railsMask;
    r.idx <== rail;
    r.out === 1;

    component c = SelectBit(32);
    c.mask <== curMask;
    c.idx <== currency;
    c.out === 1;

    component m = SelectBit(64);
    m.mask <== mccMask;
    m.idx <== mcc;
    m.out === 1;

    component g = SelectBit(64);
    g.mask <== geoMask;
    g.idx <== geo;
    g.out === 1;

    component amt = LessEqThan(64);
    amt.in[0] <== amount;
    amt.in[1] <== ceiling;
    amt.out === 1;

    component nb = LessEqThan(40);
    nb.in[0] <== notBefore;
    nb.in[1] <== t;
    nb.out === 1;

    component na = LessEqThan(40);
    na.in[0] <== t;
    na.in[1] <== notAfter;
    na.out === 1;
}

component main {public [root, brand, payee, termCommit, rail, currency, amount, mcc, geo, t]} = PayeeMembership(16);
