#!/usr/bin/env bash
# =============================================================================
# Parámetros de Trimmomatic — llamado desde main.sh
# =============================================================================

set -euo pipefail

CEPA="${1:?Cepa no especificada.}"

# ── Rutas ─────────────────────────────────────────────────────────────────────
#BASE_DIR="/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"

INPUT_DIR="${BASE_DIR}/00.Archivos_principales/Secuencias_Illumina/${CEPA}"
OUTPUT_DIR="${BASE_DIR}/01.Trimmomatic/${CEPA}"
mkdir -p "${OUTPUT_DIR}"

LOG_FILE="${OUTPUT_DIR}/${CEPA}_trimmomatic_$(date +%Y%m%d_%H%M%S).log"

ADAPTERS="/opt/miniconda3/envs/trimmomatic/share/trimmomatic-0.40-0/adapters/TruSeq3-PE.fa"
THREADS=16
export _JAVA_OPTIONS="-Xmx26g"

source /opt/miniconda3/etc/profile.d/conda.sh
conda activate /opt/miniconda3/envs/trimmomatic


echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando Trimmomatic — Cepa: ${CEPA}" | tee -a "${LOG_FILE}"

trimmomatic PE \
    -threads "${THREADS}" \
    -phred33 \
    -trimlog "${OUTPUT_DIR}/${CEPA}_trimlog.txt" \
    -summary "${OUTPUT_DIR}/${CEPA}_summary.txt" \
    "${INPUT_DIR}/${CEPA}_1.fastq.gz" \
    "${INPUT_DIR}/${CEPA}_2.fastq.gz" \
    "${OUTPUT_DIR}/${CEPA}_1_paired.fastq.gz" \
    "${OUTPUT_DIR}/${CEPA}_1_unpaired.fastq.gz" \
    "${OUTPUT_DIR}/${CEPA}_2_paired.fastq.gz" \
    "${OUTPUT_DIR}/${CEPA}_2_unpaired.fastq.gz" \
    ILLUMINACLIP:"${ADAPTERS}":2:30:10:2:true \
    LEADING:3 \
    TRAILING:3 \
    SLIDINGWINDOW:4:15 \
    MINLEN:36 \
    2>&1 | tee -a "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finalizado. Log: ${LOG_FILE}" | tee -a "${LOG_FILE}"