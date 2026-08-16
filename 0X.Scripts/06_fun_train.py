#!/usr/bin/env python3
import subprocess
import os

# ─── Configuración ────────────────────────────────────────────
import sys
#BASE_DIR       = "/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"
MUESTRA        = "T36"
SRA            = f"{BASE_DIR}/00.Archivos_principales/SRA-seq"
GENOME_MASKED  = f"{BASE_DIR}/04.Funannotate/{MUESTRA}/{MUESTRA}_masked.fasta"
DIR_FUNANN     = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"

cmd = [
    "funannotate", "train",
    "-i", GENOME_MASKED,
    "-o", DIR_FUNANN,
    "--left",  f"{SRA}/all_left_asperellum_hamatum.fastq.gz",
    "--right", f"{SRA}/all_right_asperellum_hamatum.fastq.gz",

    # "--left",
    #     f"{SRA}/SRR12495788_1.fastq.gz",
    #     f"{SRA}/SRR12495790_1.fastq.gz",
    #     f"{SRA}/SRR34502155_1.fastq.gz",
    # "--right",
    #     f"{SRA}/SRR12495788_2.fastq.gz",
    #     f"{SRA}/SRR12495790_2.fastq.gz",
    #     f"{SRA}/SRR34502155_2.fastq.gz",
    "--species", "Trichoderma sp.",
    "--strain", MUESTRA,
    "--cpus", "16",
    "--memory", "26G",
    "--no_normalize_reads"
    # "--no_trimmomatic"
]

print(f"▶ Funannotate train — {MUESTRA}")
print(f"  CMD: {' '.join(cmd)}\n")

os.makedirs(DIR_FUNANN, exist_ok=True)
os.chdir(DIR_FUNANN)   # Trinity escribe trinity_out_dir/ en el CWD — mejor dentro de la cepa

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    # sin env= : hereda el entorno activado completo, con todas las variables
)

for line in process.stdout:
    print(line, end="", flush=True)

process.wait()

if process.returncode != 0:
    print(f"\n✗ Error (código {process.returncode})")
    sys.exit(process.returncode)
else:
    print("\n✓ Completado")



# "asociacion para del desarrollo rural de sierra magina"