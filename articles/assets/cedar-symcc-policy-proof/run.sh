#!/usr/bin/env bash
# Reproduces every command in the article, end to end.
# Verified on macOS 15 / arm64.
#
#   ./run.sh
#
# Downloads ~120MB (two Cedar binaries + cvc5). No compilation needed.
set -euo pipefail

WORK="${WORK:-$(mktemp -d)}"
CEDAR_TAG="cedar-policy-cli-v4.12.0"
CVC5_TAG="cvc5-1.3.4"

echo "workdir: $WORK"
cd "$WORK"

# ---------------------------------------------------------------------------
# 1. The default binary ships `symcc` in --help but cannot run it.
# ---------------------------------------------------------------------------
echo
echo "== 1. default binary: symcc is present but gated off =="
curl -sL -o cedar.tar.xz \
  "https://github.com/cedar-policy/cedar/releases/download/${CEDAR_TAG}/cedar-policy-cli-aarch64-apple-darwin.tar.xz"
tar xf cedar.tar.xz
./cedar-policy-cli-aarch64-apple-darwin/cedar --version
# Expected: Error: subcommand `symcc` is experimental, but this executable was
#           not built with `analyze` experimental feature enabled
./cedar-policy-cli-aarch64-apple-darwin/cedar symcc || true

# ---------------------------------------------------------------------------
# 2. The same release also ships experimental binaries with analyze,tpe
#    enabled. Use those. Building from source is unnecessary.
# ---------------------------------------------------------------------------
echo
echo "== 2. experimental binary =="
curl -sL -o cedar-exp.tar.xz \
  "https://github.com/cedar-policy/cedar/releases/download/${CEDAR_TAG}/cedar-policy-cli-experimental-aarch64-apple-darwin.tar.xz"
tar xf cedar-exp.tar.xz
xattr -dr com.apple.quarantine cedar-policy-cli-experimental-aarch64-apple-darwin 2>/dev/null || true
CEDAR="$WORK/cedar-policy-cli-experimental-aarch64-apple-darwin/cedar"
"$CEDAR" language-version
"$CEDAR" symcc --help | head -5

# ---------------------------------------------------------------------------
# 3. The CLI can only drive CVC5 (the Rust library also supports Z3).
# ---------------------------------------------------------------------------
echo
echo "== 3. cvc5 =="
curl -sL -o cvc5.zip \
  "https://github.com/cvc5/cvc5/releases/download/${CVC5_TAG}/cvc5-macOS-arm64-static.zip"
unzip -oq cvc5.zip
xattr -dr com.apple.quarantine cvc5-macOS-arm64-static 2>/dev/null || true
export CVC5="$WORK/cvc5-macOS-arm64-static/bin/cvc5"
"$CVC5" --version | head -1

# ---------------------------------------------------------------------------
# 4. Schema and the three policy sets.
# ---------------------------------------------------------------------------
mkdir -p demo && cd demo

cat > schema.cedarschema <<'EOF'
entity User in [Team] = {
  "isAdmin": Bool,
  "level": Long,
};

entity Team;

entity Doc in [Team] = {
  "public": Bool,
  "classification": Long,
};

action view appliesTo {
  principal: User,
  resource: Doc,
};
EOF

cat > old.cedar <<'EOF'
permit (principal, action == Action::"view", resource)
when { principal.isAdmin };

permit (principal, action == Action::"view", resource)
when { resource.public };

permit (principal, action == Action::"view", resource)
when { principal.level >= resource.classification };
EOF

cat > new.cedar <<'EOF'
permit (principal, action == Action::"view", resource)
when {
  principal.isAdmin ||
  resource.public ||
  principal.level >= resource.classification
};
EOF

# Same as new.cedar with an off-by-one: >= became >.
sed 's/principal.level >= resource.classification/principal.level > resource.classification/' \
  new.cedar > buggy.cedar

echo
echo "== 4. validate (type checking only, says nothing about equivalence) =="
"$CEDAR" validate --schema schema.cedarschema --policies old.cedar
"$CEDAR" validate --schema schema.cedarschema --policies new.cedar

SYMCC=("$CEDAR" symcc
  --schema schema.cedarschema
  --principal-type User
  --action 'Action::"view"'
  --resource-type Doc)

# ---------------------------------------------------------------------------
# 5. Prove the refactor equivalent. Expected: VERIFIED, in ~0.01s.
# ---------------------------------------------------------------------------
echo
echo "== 5. equivalent: old vs new =="
time "${SYMCC[@]}" equivalent --policies1 old.cedar --policies2 new.cedar

# ---------------------------------------------------------------------------
# 6. Break it. Expected: DOES NOT HOLD, with a counterexample at the
#    equality boundary (level == classification).
# ---------------------------------------------------------------------------
echo
echo "== 6. equivalent: old vs buggy =="
"${SYMCC[@]}" equivalent --policies1 old.cedar --policies2 buggy.cedar || true

# ---------------------------------------------------------------------------
# 7. Which direction is wider? Run implies both ways.
#    buggy => old holds; old => buggy does not. So buggy is strictly narrower,
#    i.e. the change tightens access rather than widening it.
# ---------------------------------------------------------------------------
echo
echo "== 7a. implies: buggy => old (expect VERIFIED) =="
"${SYMCC[@]}" implies --policies1 buggy.cedar --policies2 old.cedar || true

echo
echo "== 7b. implies: old => buggy (expect counterexample) =="
"${SYMCC[@]}" implies --policies1 old.cedar --policies2 buggy.cedar || true

echo
echo "done. workdir kept at $WORK"
