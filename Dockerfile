# MERIDIAN artifact: reproduces every table and figure from fixed seeds.
#
#   docker compose run --rm meridian            # full run -> ./results
#   docker compose run --rm meridian-quick      # smoke run
#   docker compose run --rm tests
#
# Built for linux/amd64 (the Tamarin release binary is x86_64).

FROM python:3.12-slim-bookworm

ARG NODE_VERSION=22.13.1
ARG TAMARIN_VERSION=1.12.0
ARG PROVERIF_VERSION=2.05

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf \
    PROVERIF=/opt/proverif/proverif

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils build-essential git \
        ocaml-nox maude libgmp10 libffi8 libtinfo6 zlib1g graphviz \
    && rm -rf /var/lib/apt/lists/*

# Node.js (circom2 WASM compiler, snarkjs, BBS)
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
      | tar -xJ -C /opt \
    && ln -s /opt/node-v${NODE_VERSION}-linux-x64/bin/node /usr/local/bin/node \
    && ln -s /opt/node-v${NODE_VERSION}-linux-x64/bin/npm /usr/local/bin/npm \
    && ln -s /opt/node-v${NODE_VERSION}-linux-x64/bin/npx /usr/local/bin/npx

# Tamarin prover
RUN curl -fsSL "https://github.com/tamarin-prover/tamarin-prover/releases/download/${TAMARIN_VERSION}/tamarin-prover-${TAMARIN_VERSION}-linux64-ubuntu.tar.gz" \
      | tar -xz -C /usr/local/bin tamarin-prover \
    && tamarin-prover --version | head -1

# ProVerif (built from source, no interactive mode)
RUN mkdir -p /opt && cd /opt \
    && curl -fsSL "https://bblanche.gitlabpages.inria.fr/proverif/proverif${PROVERIF_VERSION}.tar.gz" | tar -xz \
    && mv proverif${PROVERIF_VERSION} proverif && cd proverif && ./build -nointeract

WORKDIR /app

# Python dependencies (CPU-only torch for the embedding model)
COPY requirements.lock pyproject.toml ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1 \
    && grep -v '^torch==' requirements.lock > /tmp/req.txt \
    && pip install -r /tmp/req.txt

# Node dependencies and the Groth16 test setup
COPY zk/ zk/
RUN cd zk/js && npm ci --no-audit --no-fund && cd /app && bash zk/setup.sh

COPY . .
RUN pip install --no-deps -e . \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

ENV HF_HUB_OFFLINE=1

CMD ["python", "-m", "experiments.run_all"]
