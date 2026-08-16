#!/usr/bin/env bash
# Uso: bash 04_filtrado.sh H5258
#      nohup bash 04_filtrado.sh H10603 &

set -euo pipefail

CEPA="${1:?Indica la cepa como argumento. Ej: bash 04_filtrado.sh H5258}"

#BASE_DIR="/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"

INPUT_FASTA="${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/${CEPA}_assembly_final.fasta"
OUTPUT_DIR="${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}"
OUTPUT_FASTA="${OUTPUT_DIR}/${CEPA}_filtered_3000.fasta"
LOG_FILE="${OUTPUT_DIR}/${CEPA}_filtrado_$(date +%Y%m%d_%H%M%S).log"

source /opt/miniconda3/etc/profile.d/conda.sh
conda activate /opt/miniconda3/envs/seqkit

mkdir -p "${OUTPUT_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando filtrado — Cepa: ${CEPA}" | tee -a "${LOG_FILE}"

seqkit sort --by-length --reverse "${INPUT_FASTA}" \
    2>>"${LOG_FILE}" \
    | seqkit seq --min-len 3000 \
    -o "${OUTPUT_FASTA}" \
    2>>"${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Completado." | tee -a "${LOG_FILE}"
echo "  Contigs totales antes del filtro:" | tee -a "${LOG_FILE}"
grep -c "^>" "${INPUT_FASTA}" | tee -a "${LOG_FILE}"
echo "  Contigs ≥3000 bp tras el filtro:" | tee -a "${LOG_FILE}"
grep -c "^>" "${OUTPUT_FASTA}" | tee -a "${LOG_FILE}"