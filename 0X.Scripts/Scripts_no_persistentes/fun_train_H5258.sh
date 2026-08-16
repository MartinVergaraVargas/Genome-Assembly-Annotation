#!/usr/bin/env bash
# =============================================================================
# Funannotate train — H5258
#
# Lanzamiento recomendado (con el entorno funannotate ya activado):
#   conda activate funannotate
#   nohup bash fun_train_H5258.sh > /dev/null 2>&1 &
#   tail -f /srv/TFM/PL-iteracion.05/04.Funannotate/H5258/fun_train_H5258_*.log
# =============================================================================

set -euo pipefail

BASE_DIR="/srv/TFM/PL-iteracion.05"
MUESTRA="H5258"
SRA="${BASE_DIR}/00.Archivos_principales/SRA-seq/T_asperellum"

DIR_FUNANN="${BASE_DIR}/04.Funannotate/${MUESTRA}"
GENOME_MASKED="${DIR_FUNANN}/${MUESTRA}_masked.fasta"
LOG_FILE="${DIR_FUNANN}/fun_train_${MUESTRA}_$(date +%Y%m%d_%H%M%S).log"

LEFT="${SRA}/all_left_asperellum_fun.fastq.gz"
RIGHT="${SRA}/all_right_asperellum_fun.fastq.gz"

# ── Verificaciones previas ────────────────────────────────────────────────────
if [[ ! -f "${GENOME_MASKED}" ]]; then
    echo "✗ No se encuentra el genoma enmascarado: ${GENOME_MASKED}"
    exit 1
fi

if [[ ! -f "${LEFT}" || ! -f "${RIGHT}" ]]; then
    echo "✗ No se encuentran los reads RNA-seq en: ${SRA}"
    echo "  Esperados: all_left_asperellum_fun.fastq.gz"
    echo "             all_right_asperellum_fun.fastq.gz"
    exit 1
fi

mkdir -p "${DIR_FUNANN}"

# Trinity escribe trinity_out_dir/ en el CWD — lo fijamos dentro de la cepa
cd "${DIR_FUNANN}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando funannotate train — ${MUESTRA}" | tee "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Genoma  : ${GENOME_MASKED}" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] RNA-seq : ${LEFT}" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log     : ${LOG_FILE}" | tee -a "${LOG_FILE}"

export _JAVA_OPTIONS="-Xmx26g"

funannotate train \
    -i  "${GENOME_MASKED}" \
    -o  "${DIR_FUNANN}" \
    --left  "${LEFT}" \
    --right "${RIGHT}" \
    --species  "Trichoderma sp." \
    --strain   "${MUESTRA}" \
    --cpus     16 \
    --memory   26G \
    --no_normalize_reads \
    2>&1 | tee -a "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ funannotate train completado — ${MUESTRA}" | tee -a "${LOG_FILE}"