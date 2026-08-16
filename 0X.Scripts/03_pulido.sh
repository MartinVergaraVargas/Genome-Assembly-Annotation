#!/usr/bin/env bash
# =============================================================================
# Uso: bash 03_pulido.sh T16
#      bash 03_pulido.sh T22
#      nohup bash 03_pulido.sh T16 &
# =============================================================================

set -euo pipefail

# ── Cepa (obligatorio) ────────────────────────────────────────────────────────
CEPA="${1:?Indica la cepa como argumento. Ej: bash 03_pulido.sh T16}"

# ── Rutas ─────────────────────────────────────────────────────────────────────
#BASE_DIR="/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"

SPADES_DIR="${BASE_DIR}/02.SPAdes_Assembly/${CEPA}"
TRIM_DIR="${BASE_DIR}/01.Trimmomatic/${CEPA}"
OUTPUT_DIR="${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}"
mkdir -p "${OUTPUT_DIR}"

LOG_FILE="${OUTPUT_DIR}/${CEPA}_pilon_$(date +%Y%m%d_%H%M%S).log"

R1="${TRIM_DIR}/${CEPA}_1_paired.fastq.gz"
R2="${TRIM_DIR}/${CEPA}_2_paired.fastq.gz"

EMAIL="your-email@example.com"
THREADS=16
MAX_ROUNDS=2   # Fijado en 2 rondas de pulido
export _JAVA_OPTIONS="-Xmx26g"   # RAM máxima para la JVM de Pilon

# ── Activar Conda ─────────────────────────────────────────────────────────────
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate /opt/miniconda3/envs/pilon

# ── Preparar salida ───────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando Pilon iterativo — Cepa: ${CEPA}" | tee -a "${LOG_FILE}"

# ── Ensamblaje inicial (scaffolds de SPAdes) ──────────────────────────────────
INITIAL_COPY="${OUTPUT_DIR}/${CEPA}_scaffolds_initial.fasta"
cp "${SPADES_DIR}/scaffolds.fasta" "${INITIAL_COPY}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ensamblaje inicial copiado: ${INITIAL_COPY}" | tee -a "${LOG_FILE}"
CURRENT_ASSEMBLY="${INITIAL_COPY}"

# ── Loop de polishing iterativo ───────────────────────────────────────────────
for ROUND in $(seq 1 "${MAX_ROUNDS}"); do

    ROUND_DIR="${OUTPUT_DIR}/round_${ROUND}"
    mkdir -p "${ROUND_DIR}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ── Ronda ${ROUND} ──" | tee -a "${LOG_FILE}"

    # 1. Indexar el ensamblaje actual
    bwa index "${CURRENT_ASSEMBLY}" 2>&1 | tee -a "${LOG_FILE}"

    # 2. Mapear lecturas y generar BAM ordenado
    BAM="${ROUND_DIR}/mapping_round${ROUND}.bam"
    bwa mem -t "${THREADS}" "${CURRENT_ASSEMBLY}" "${R1}" "${R2}" \
        | samtools sort -@ "${THREADS}" -o "${BAM}" \
        2>&1 | tee -a "${LOG_FILE}"
    samtools index "${BAM}" 2>&1 | tee -a "${LOG_FILE}"

    # 3. Ejecutar Pilon
    if pilon \
        --genome "${CURRENT_ASSEMBLY}" \
        --frags "${BAM}" \
        --output "${CEPA}_pilon_round${ROUND}" \
        --outdir "${ROUND_DIR}" \
        --changes \
        --fix all \
        --threads "${THREADS}" \
        2>&1 | tee -a "${LOG_FILE}"; then

        CHANGES_FILE="${ROUND_DIR}/${CEPA}_pilon_round${ROUND}.changes"
        CHANGES=$(wc -l < "${CHANGES_FILE}")
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ronda ${ROUND}: ${CHANGES} cambios." | tee -a "${LOG_FILE}"

        # 4. Limpiar BAM para ahorrar espacio
        rm -f "${BAM}" "${BAM}.bai"

        # 5. Limpiar sufijos _pilon acumulados en los headers de los contigs
        sed -i '/^>/ s/_pilon//g' "${ROUND_DIR}/${CEPA}_pilon_round${ROUND}.fasta"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Headers limpiados en ronda ${ROUND}." | tee -a "${LOG_FILE}"

        # 6. Comprobar convergencia
        if [[ "${CHANGES}" -eq 0 ]]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sin cambios en ronda ${ROUND}. Convergencia alcanzada." | tee -a "${LOG_FILE}"
            break
        fi

        # 7. El output de esta ronda es el input de la siguiente
        CURRENT_ASSEMBLY="${ROUND_DIR}/${CEPA}_pilon_round${ROUND}.fasta"

    else
        ERROR_MSG="$(tail -20 "${LOG_FILE}")"
        echo "${ERROR_MSG}" | mail -s "[ERROR] Pilon ronda ${ROUND} - ${CEPA}" "${EMAIL}"
        exit 1
    fi

done

# ── Copiar ensamblaje final con nombre limpio ─────────────────────────────────
FINAL_ASSEMBLY="${OUTPUT_DIR}/${CEPA}_assembly_final.fasta"
cp "${CURRENT_ASSEMBLY}" "${FINAL_ASSEMBLY}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ensamblaje final: ${FINAL_ASSEMBLY}" | tee -a "${LOG_FILE}"

# ── Notificación ──────────────────────────────────────────────────────────────
TOTAL_ROUNDS=$((ROUND))
echo "Pilon completado para ${CEPA} en ${TOTAL_ROUNDS} ronda(s). Ensamblaje final: ${FINAL_ASSEMBLY} — Log: ${LOG_FILE}" \
    | mail -s "[PIPELINE OK] Pilon - ${CEPA}" "${EMAIL}"


# #!/usr/bin/env bash
# # =============================================================================
# # Uso: bash 03_pilon.sh T16
# #      bash 03_pilon.sh T22
# #      nohup bash 03_pilon.sh T16 &
# # =============================================================================

# set -euo pipefail

# # ── Cepa (obligatorio) ────────────────────────────────────────────────────────
# CEPA="${1:?Indica la cepa como argumento. Ej: bash 03_pilon.sh T16}"

# # ── Rutas ─────────────────────────────────────────────────────────────────────
# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# BASE_DIR="$(realpath "${SCRIPT_DIR}/../../")"

# SPADES_DIR="${BASE_DIR}/02.SPAdes/${CEPA}/recomendado-careful_${CEPA}"
# TRIM_DIR="${BASE_DIR}/01.Trimmomatic/${CEPA}/recomendado_${CEPA}"
# OUTPUT_DIR="${BASE_DIR}/03.Pilon/${CEPA}/recomendado-careful_${CEPA}"
# LOG_FILE="${OUTPUT_DIR}/${CEPA}_pilon_$(date +%Y%m%d_%H%M%S).log"

# R1="${TRIM_DIR}/${CEPA}_1_paired.fastq.gz"
# R2="${TRIM_DIR}/${CEPA}_2_paired.fastq.gz"

# EMAIL="your-email@example.com"
# THREADS=16
# MAX_ROUNDS=3   # Límite de seguridad; el loop para antes si no hay más cambios
# export _JAVA_OPTIONS="-Xmx26g"   # RAM máxima para la JVM de Pilon

# # ── Activar Conda ─────────────────────────────────────────────────────────────
# source /opt/miniconda3/etc/profile.d/conda.sh
# conda activate /opt/miniconda3/envs/pilon

# # ── Preparar salida ───────────────────────────────────────────────────────────
# mkdir -p "${OUTPUT_DIR}"

# echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando Pilon iterativo — Cepa: ${CEPA}" | tee -a "${LOG_FILE}"

# # ── Ensamblaje inicial (scaffolds de SPAdes) ──────────────────────────────────
# CURRENT_ASSEMBLY="${SPADES_DIR}/scaffolds.fasta"

# # ── Loop de polishing iterativo ───────────────────────────────────────────────
# for ROUND in $(seq 1 "${MAX_ROUNDS}"); do

#     ROUND_DIR="${OUTPUT_DIR}/round_${ROUND}"
#     mkdir -p "${ROUND_DIR}"

#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] ── Ronda ${ROUND} ──" | tee -a "${LOG_FILE}"

#     # 1. Indexar el ensamblaje actual
#     bwa index "${CURRENT_ASSEMBLY}" 2>&1 | tee -a "${LOG_FILE}"

#     # 2. Mapear lecturas y generar BAM ordenado
#     BAM="${ROUND_DIR}/mapping_round${ROUND}.bam"
#     bwa mem -t "${THREADS}" "${CURRENT_ASSEMBLY}" "${R1}" "${R2}" \
#         | samtools sort -@ "${THREADS}" -o "${BAM}" \
#         2>&1 | tee -a "${LOG_FILE}"
#     samtools index "${BAM}" 2>&1 | tee -a "${LOG_FILE}"

#     # 3. Ejecutar Pilon
#     if pilon \
#         --genome "${CURRENT_ASSEMBLY}" \
#         --frags "${BAM}" \
#         --output "${CEPA}_pilon_round${ROUND}" \
#         --outdir "${ROUND_DIR}" \
#         --changes \
#         --fix all \
#         --threads "${THREADS}" \
#         2>&1 | tee -a "${LOG_FILE}"; then

#         CHANGES_FILE="${ROUND_DIR}/${CEPA}_pilon_round${ROUND}.changes"
#         CHANGES=$(wc -l < "${CHANGES_FILE}")
#         echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ronda ${ROUND}: ${CHANGES} cambios." | tee -a "${LOG_FILE}"

#         # 4. Limpiar BAM para ahorrar espacio
#         rm -f "${BAM}" "${BAM}.bai"

#         # 5. Comprobar convergencia
#         if [[ "${CHANGES}" -eq 0 ]]; then
#             echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sin cambios en ronda ${ROUND}. Convergencia alcanzada." | tee -a "${LOG_FILE}"
#             break
#         fi

#         # 6. El output de esta ronda es el input de la siguiente
#         CURRENT_ASSEMBLY="${ROUND_DIR}/${CEPA}_pilon_round${ROUND}.fasta"

#     else
#         ERROR_MSG="$(tail -20 "${LOG_FILE}")"
#         echo "${ERROR_MSG}" | mail -s "[ERROR] Pilon ronda ${ROUND} - ${CEPA}" "${EMAIL}"
#         exit 1
#     fi

# done

# # ── Copiar ensamblaje final con nombre limpio ─────────────────────────────────
# FINAL_ASSEMBLY="${OUTPUT_DIR}/${CEPA}_assembly_final.fasta"
# cp "${CURRENT_ASSEMBLY}" "${FINAL_ASSEMBLY}"

# echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ensamblaje final: ${FINAL_ASSEMBLY}" | tee -a "${LOG_FILE}"

# # ── Notificación ──────────────────────────────────────────────────────────────
# TOTAL_ROUNDS=$((ROUND))
# echo "Pilon completado para ${CEPA} en ${TOTAL_ROUNDS} ronda(s). Ensamblaje final: ${FINAL_ASSEMBLY} — Log: ${LOG_FILE}" \
#     | mail -s "[PIPELINE OK] Pilon - ${CEPA}" "${EMAIL}"