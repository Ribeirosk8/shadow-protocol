# ==============================================================================
# SHADOW-Net — SWaP Emulation Container
# ==============================================================================
# Paper §V-A: "the execution environment was containerized via Docker with
# strict CPU and memory limits (0.5 cores, 1GB RAM, simulating a Raspberry Pi
# architecture)."
#
# Build:   docker build -t shadow-smpc .
# Run:     docker run --rm shadow-smpc --soc 85
# ==============================================================================

FROM python:3.11-slim AS runtime

# --- Metadata ----------------------------------------------------------------
LABEL maintainer="Amauri Ribeiro"
LABEL description="SHADOW-Net: SWaP-Aware Dynamic SMPC Cryptographic Engine"
LABEL paper="SHADOW-Net: Delay-Aware Dynamic SMPC in Privacy-Preserving FANETs"

# --- System setup ------------------------------------------------------------
# Prevents Python from buffering stdout/stderr (important for Docker logs)
ENV PYTHONUNBUFFERED=1
# Disable .pyc file generation to save disk in constrained environments
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# --- Install dependencies (cached layer) ------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy application --------------------------------------------------------
COPY shadow_smpc.py .
COPY benchmark_harness.py .
RUN mkdir -p /app/results

# --- Default entrypoint ------------------------------------------------------
# SOC is overridden via docker-compose or CLI: docker run shadow-smpc --soc 50
ENTRYPOINT ["python", "shadow_smpc.py"]
CMD ["--soc", "100"]
