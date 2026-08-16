#!/usr/bin/env python3
"""
fun_initcleansortmask.py
Corre funannotate clean → sort → mask para una cepa.

Uso:
    python3 fun_initcleansortmask.py H5258
    python3 fun_initcleansortmask.py H10603
    nohup python3 fun_initcleansortmask.py H5258 > cleansortmask_H5258.log 2>&1 &
"""

import subprocess
import os
import sys

# ─── Argumento obligatorio ────────────────────────────────────
if len(sys.argv) < 2:
    print("Uso: python3 fun_initcleansortmask.py <CEPA>")
    print("     Ej: python3 fun_initcleansortmask.py H5258")
    sys.exit(1)

MUESTRA = sys.argv[1]

# ─── Rutas base ───────────────────────────────────────────────
#BASE_DIR   = "/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"
DIR_FUNANN = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"

# ─── Input: FASTA filtrado por longitud (≥3000 bp, producido por 04_filtrado.sh) ─
GENOME_FILT = f"{BASE_DIR}/03.Pulido_y_filtrado/{MUESTRA}/{MUESTRA}_filtered_3000.fasta"

# ─── Outputs intermedios y final ──────────────────────────────
GENOME_CLEAN  = f"{DIR_FUNANN}/{MUESTRA}_clean.fasta"
GENOME_SORTED = f"{DIR_FUNANN}/{MUESTRA}_sorted.fasta"
GENOME_MASKED = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"

# ─── Entorno funannotate ──────────────────────────────────────
env = os.environ.copy()
env["PATH"] = "/opt/miniconda3/envs/funannotate/bin:" + env["PATH"]
env["PASAHOME"] = "/opt/miniconda3/envs/funannotate/opt/pasa-2.5.3"


# ─── Helper ───────────────────────────────────────────────────
def run(cmd, descripcion=""):
    if descripcion:
        print(f"\n▶ {descripcion}", flush=True)
    print(f"  CMD: {' '.join(cmd)}\n", flush=True)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    for line in process.stdout:
        print(line, end="", flush=True)
    process.wait()
    if process.returncode != 0:
        print(f"\n✗ Error (código {process.returncode})")
        sys.exit(1)
    print(f"\n✓ Completado")

# ─── Verificar input ──────────────────────────────────────────
if not os.path.isfile(GENOME_FILT):
    print(f"✗ No se encontró el FASTA de entrada: {GENOME_FILT}")
    print("  Asegúrate de haber corrido 04_filtrado.sh antes.")
    sys.exit(1)

os.makedirs(DIR_FUNANN, exist_ok=True)

print(f"Muestra       : {MUESTRA}")
print(f"FASTA entrada : {GENOME_FILT}")
print(f"Directorio    : {DIR_FUNANN}")

# ─── Clean ────────────────────────────────────────────────────
# Elimina contigs redundantes (duplicados por cobertura)
run([
    "funannotate", "clean",
    "-i", GENOME_FILT,
    "-o", GENOME_CLEAN,
    "--minlen", "500",
    "--pident", "95",
    "--cov",    "95",
], descripcion=f"Funannotate clean — {MUESTRA}")

# ─── Sort ─────────────────────────────────────────────────────
# Renombra headers a scaffold_1, scaffold_2... (funannotate es sensible a headers complejos)
run([
    "funannotate", "sort",
    "-i", GENOME_CLEAN,
    "-o", GENOME_SORTED,
    "-b", "scaffold",
    "--minlen", "0",
], descripcion=f"Funannotate sort — {MUESTRA}")

# ─── Mask ─────────────────────────────────────────────────────
# Soft-masking de repeticiones (minúsculas)
run([
    "funannotate", "mask",
    "-i", GENOME_SORTED,
    "-o", GENOME_MASKED,
    "--cpus", "16",
], descripcion=f"Funannotate mask — {MUESTRA}")

print(f"\n✓ clean → sort → mask completos para {MUESTRA}")
print(f"  FASTA enmascarado: {GENOME_MASKED}")


