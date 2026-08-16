#!/usr/bin/env python3
import subprocess
import os
import sys

# ─── Configuración ────────────────────────────────────────────
BASE_DIR  = "/srv/TFM/PL-iteracion.05"
SRA_DIR   = f"{BASE_DIR}/00.Archivos_principales/SRA-seq"
LEFT      = f"{SRA_DIR}/all_left_T22_T36.fastq.gz"
RIGHT     = f"{SRA_DIR}/all_right_T22_T36.fastq.gz"

MUESTRAS = {"T36": {"species": "Trichoderma sp.", "strain": "T36"},
}

env = os.environ.copy()
env["PATH"] = "/opt/miniconda3/envs/funannotate/bin:" + env["PATH"]

def run_training(muestra, species, strain):
    genome_masked = f"{BASE_DIR}/04.Funannotate/{muestra}/{muestra}_masked.fasta"
    dir_funann    = f"{BASE_DIR}/04.Funannotate/{muestra}"

    cmd = [
        "funannotate", "train",
        "-i", genome_masked,
        "-o", dir_funann,
        "--left",    LEFT,
        "--right",   RIGHT,
        "--species", species,
        "--strain",  strain,
        "--cpus",    "14",
        "--memory",  "26G",
        "--no_normalize_reads",
    ]

    print(f"\n▶ Funannotate train — {muestra}")
    print(f"  CMD: {' '.join(cmd)}\n", flush=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )

    for line in process.stdout:
        print(line, end="", flush=True)

    process.wait()

    if process.returncode != 0:
        print(f"\n✗ Error en {muestra} (código {process.returncode})")
        sys.exit(1)

    print(f"\n✓ Training completado — {muestra}")

# ─── Ejecutar en secuencia ─────────────────────────────────────
for muestra, params in MUESTRAS.items():
    run_training(muestra, params["species"], params["strain"])

print("\n✓ Training completado para T22 y T36")