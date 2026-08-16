#!/usr/bin/env python3
import subprocess
import os
import sys
import shutil

BASE_DIR   = "/srv/TFM/PL-iteracion.05"
MUESTRA    = "T36"
SPECIES    = "Trichoderma sp."
STRAIN     = "T36"
LINEAGE    = "/srv/biodata/busco_downloads/lineages/hypocreales_odb12"

DIR_FUNANN       = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"
GENOME_MASKED    = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"
ANNOTATE_MISC    = f"{DIR_FUNANN}/annotate_misc"
BUSCO_OUT_DIR    = f"{ANNOTATE_MISC}/run_busco_test"
BUSCO_TABLE      = f"{BUSCO_OUT_DIR}/run_hypocreales_odb12/full_table.tsv"
BUSCO_DEST_DIR   = f"{ANNOTATE_MISC}/run_busco"
BUSCO_DEST_FILE  = f"{BUSCO_DEST_DIR}/full_table_busco.tsv"
PROTEINS_FASTA   = f"{ANNOTATE_MISC}/genome.proteins.fasta"

env = os.environ.copy()
env["PATH"] = "/opt/miniconda3/envs/funannotate/bin:" + env["PATH"]

def run(cmd, descripcion="", allow_failure=False):
    if descripcion:
        print(f"\n▶ {descripcion}", flush=True)
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
        if allow_failure:
            print(f"\n⚠ Terminó con código {process.returncode} (esperado en este paso)")
            return False
        else:
            print(f"\n✗ Error (código {process.returncode})")
            sys.exit(1)
    print(f"\n✓ Completado")
    return True

# ── 1. Predict ────────────────────────────────────────────────
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

# ── 2. Primer annotate (fallará en BUSCO, es esperado) ────────
print("\n▶ Annotate — primera pasada (fallará en BUSCO, es esperado)")
run([
    "funannotate", "annotate",
    "-i", DIR_FUNANN,
    "--busco_db", LINEAGE,
    "--cpus", "16",
], allow_failure=True)

# ── 3. Verificar que genome.proteins.fasta existe ─────────────
if not os.path.isfile(PROTEINS_FASTA):
    print(f"\n✗ No se encontró {PROTEINS_FASTA}")
    print("  El annotate no llegó a generar las proteínas. Revisa el log.")
    sys.exit(1)

print(f"\n▶ BUSCO manual sobre proteínas predichas")

# ── 4. Correr BUSCO manualmente ───────────────────────────────
run([
    "busco",
    "-i", PROTEINS_FASTA,
    "-o", "run_busco_test",
    "--out_path", ANNOTATE_MISC,
    "-l", LINEAGE,
    "-m", "proteins",
    "-c", "16",
    "--offline",
    "--force",
], descripcion="BUSCO sobre proteínas")

# ── 5. Copiar resultado donde annotate lo espera ──────────────
if not os.path.isfile(BUSCO_TABLE):
    print(f"\n✗ No se generó el archivo: {BUSCO_TABLE}")
    sys.exit(1)

os.makedirs(BUSCO_DEST_DIR, exist_ok=True)
shutil.copy(BUSCO_TABLE, BUSCO_DEST_FILE)
print(f"\n✓ BUSCO copiado a: {BUSCO_DEST_FILE}")

# ── 6. Segundo annotate (ahora con BUSCO listo) ───────────────
run([
    "funannotate", "annotate",
    "-i", DIR_FUNANN,
    "--busco_db", LINEAGE,
    "--cpus", "16",
], descripcion=f"Annotate final — {MUESTRA}")

print(f"\n✓ Predict + Annotate completos para {MUESTRA}")
