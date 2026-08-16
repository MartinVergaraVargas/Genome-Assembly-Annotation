#!/usr/bin/env bash
# =============================================================================
# Uso: bash 02_spades.sh T16
#      bash 02_spades.sh T22
#      nohup bash 02_spades.sh T16 &
# =============================================================================

set -euo pipefail

# ── Cepa (obligatorio) ────────────────────────────────────────────────────────
CEPA="${1:?Indica la cepa como argumento. Ej: bash 02_spades.sh T16}"

# ── Rutas ─────────────────────────────────────────────────────────────────────
#BASE_DIR="/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"

TRIM_DIR="${BASE_DIR}/01.Trimmomatic/${CEPA}"
OUTPUT_DIR="${BASE_DIR}/02.SPAdes_Assembly/${CEPA}"
mkdir -p "${OUTPUT_DIR}"

LOG_FILE="${OUTPUT_DIR}/${CEPA}_spades_$(date +%Y%m%d_%H%M%S).log"

EMAIL="your-email@example.com"
THREADS=16
MEMORY=26   # GB disponibles para SPAdes

# ── Activar Conda ─────────────────────────────────────────────────────────────
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate /opt/miniconda3/envs/spades

# ── Preparar salida ───────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando SPAdes — Cepa: ${CEPA}" | tee -a "${LOG_FILE}"

# ── SPAdes ────────────────────────────────────────────────────────────────────
if spades.py \
    --careful \
    --cov-cutoff auto \
    -t "${THREADS}" \
    -m "${MEMORY}" \
    -1 "${TRIM_DIR}/${CEPA}_1_paired.fastq.gz" \
    -2 "${TRIM_DIR}/${CEPA}_2_paired.fastq.gz" \
    -s "${TRIM_DIR}/${CEPA}_1_unpaired.fastq.gz" \
    -o "${OUTPUT_DIR}" \
    2>&1 | tee -a "${LOG_FILE}"; then
 
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finalizado. Log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
    echo "SPAdes completado para ${CEPA}. Ensamblaje en: ${OUTPUT_DIR}/scaffolds.fasta — Log: ${LOG_FILE}" \
        | mail -s "[PIPELINE OK] SPAdes - ${CEPA}" "${EMAIL}"
else
    ERROR_MSG="$(tail -20 "${LOG_FILE}")"
    echo "${ERROR_MSG}" | mail -s "[ERROR] SPAdes - ${CEPA}" "${EMAIL}"
    exit 1
fi