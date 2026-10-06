#!/usr/bin/env bash
# Build the V4 membership circuit and a Groth16 test setup.
# The ceremony uses fixed entropy so the artifact is reproducible; it is a
# test setup only and must not be used to protect real payments.
set -euo pipefail
cd "$(dirname "$0")"
SNARKJS="node js/node_modules/snarkjs/build/cli.cjs"
mkdir -p build
if [ ! -d js/node_modules ]; then (cd js && npm ci --no-audit --no-fund); fi
npx --prefix js circom2 circuits/payee_membership.circom --r1cs --wasm --sym -o build
if [ ! -f build/pot14_final.ptau ]; then
  $SNARKJS powersoftau new bn128 14 build/pot14_0000.ptau
  $SNARKJS powersoftau contribute build/pot14_0000.ptau build/pot14_0001.ptau --name="meridian-test-1" -e="meridian fixed test entropy 1"
  $SNARKJS powersoftau prepare phase2 build/pot14_0001.ptau build/pot14_final.ptau
fi
$SNARKJS groth16 setup build/payee_membership.r1cs build/pot14_final.ptau build/membership_0000.zkey
$SNARKJS zkey contribute build/membership_0000.zkey build/membership_final.zkey --name="meridian-test-2" -e="meridian fixed test entropy 2"
$SNARKJS zkey export verificationkey build/membership_final.zkey build/verification_key.json
sha256sum build/membership_final.zkey build/verification_key.json 2>/dev/null || shasum -a 256 build/membership_final.zkey build/verification_key.json
