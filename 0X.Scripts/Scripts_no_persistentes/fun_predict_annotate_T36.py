#!/usr/bin/env python3
import subprocess
import os
import sys

BASE_DIR   = "/srv/TFM/PL-iteracion.05"
MUESTRA    = "T36"
SPECIES    = "Trichoderma sp."
STRAIN     = "T36"
LINEAGE    = "/srv/biodata/busco_downloads/lineages/hypocreales_odb12"

DIR_FUNANN    = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"
GENOME_MASKED = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"

def run(cmd, descripcion=""):
    if descripcion:
        print(f"\n▶ {descripcion}", flush=True)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in process.stdout:
        print(line, end="", flush=True)
    process.wait()
    if process.returncode != 0:
        print(f"\n✗ Error (código {process.returncode})")
        sys.exit(1)
    print(f"\n✓ Completado")

# ── Predict ───────────────────────────────────────────────────
run([
    "funannotate", "predict",
    "-i", GENOME_MASKED,
    "-o", DIR_FUNANN,
    "-s", SPECIES,
    "--strain", STRAIN,
    "--busco_db", LINEAGE,
    "--busco_seed_species", "fusarium_graminearum",
    "--organism", "fungus",
    "--cpus", "16",
], descripcion=f"Predict — {MUESTRA}")

# run([
#     "funannotate", "predict",
#     "-i", GENOME_MASKED,
#     "-o", DIR_FUNANN,
#     "-s", SPECIES,
#     "--strain", STRAIN,
#     "--busco_db", LINEAGE,
#     "--busco_seed_species", "fusarium_graminearum",
#     "--organism", "fungus",
#     "--cpus", "16",
#     #"--weights", "codingquarry:0",
# ], descripcion=f"Predict — {MUESTRA}")

# ── Annotate ──────────────────────────────────────────────────
run([
    "funannotate", "annotate",
    "-i", DIR_FUNANN,
    "--busco_db", LINEAGE,
    "--cpus", "16",
], descripcion=f"Annotate — {MUESTRA}")

print(f"\n✓ Predict + Annotate completos para {MUESTRA}")


# nohup python fun_predict_annotate_T16.py > predict_annotate_T16.log 2>&1 &
# tail -f predict_annotate_T16.log

# correr con 
# "nohup bash pipeline_T22_T36.sh > pipeline_T22_T36.log 2>&1 &"

# luego:
# "tail -f pipeline_T22_T36.log"