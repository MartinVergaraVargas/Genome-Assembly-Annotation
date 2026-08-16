#!/usr/bin/env python3
"""
fun_predict_ipr_annotate.py
Pipeline completo post-enmascaramiento para una cepa:
  1. funannotate predict
  2. InterProScan sobre las proteínas predichas
  3. funannotate annotate — primera pasada (falla en BUSCO, es esperado)
  4. BUSCO manual sobre genome.proteins.fasta
  5. Copia de la tabla BUSCO donde funannotate la espera
  6. funannotate annotate final — integra IPR + BUSCO

Uso:
    python3 fun_predict_ipr_annotate.py H5258 "Trichoderma sp." H5258
    python3 fun_predict_ipr_annotate.py H10603 "Trichoderma sp." H10603
    nohup python3 fun_predict_ipr_annotate.py H5258 "Trichoderma sp." H5258 \
        > predict_ipr_annotate_H5258.log 2>&1 &
"""

import subprocess
import sys
import os
import shutil
import glob

# ── Argumentos ────────────────────────────────────────────────
if len(sys.argv) < 4:
    print("Uso: python3 fun_predict_ipr_annotate.py <MUESTRA> <SPECIES> <STRAIN>")
    print('     Ej: python3 fun_predict_ipr_annotate.py H5258 "Trichoderma sp." H5258')
    sys.exit(1)

MUESTRA = sys.argv[1]
SPECIES = sys.argv[2]
STRAIN  = sys.argv[3]

# ── Rutas fijas ───────────────────────────────────────────────
#BASE_DIR  = "/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"
IPR_SH    = "/srv/biodata/interproscan_db/interproscan-5.77-108.0/interproscan.sh"
LINEAGE   = "/srv/biodata/busco_downloads/lineages/hypocreales_odb12"
CPUS      = "16"

# ── Rutas derivadas de la cepa ────────────────────────────────
DIR_FUNANN    = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"
GENOME_MASKED = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"
PREDICT_DIR   = f"{DIR_FUNANN}/predict_results"
ANNOTATE_MISC = f"{DIR_FUNANN}/annotate_misc"

# Rutas del workaround BUSCO
PROTEINS_FASTA  = f"{ANNOTATE_MISC}/genome.proteins.fasta"
BUSCO_OUT_DIR   = f"{ANNOTATE_MISC}/run_busco_test"
BUSCO_TABLE     = f"{BUSCO_OUT_DIR}/run_hypocreales_odb12/full_table.tsv"
BUSCO_DEST_DIR  = f"{ANNOTATE_MISC}/run_busco"
BUSCO_DEST_FILE = f"{BUSCO_DEST_DIR}/full_table_busco.tsv"

# Ruta del XML de InterProScan
IPR_XML = f"{DIR_FUNANN}/interproscan_{MUESTRA}.xml"

# ── Entornos ──────────────────────────────────────────────────
# funannotate y BUSCO viven en entornos conda distintos
env_fun  = os.environ.copy()   # funannotate ya está en PATH con el entorno activado
env_busco = os.environ.copy()
env_busco["PATH"] = "/opt/miniconda3/envs/busco/bin:" + env_busco["PATH"]  # sigue necesario: entorno distinto
env_sys  = os.environ.copy()

# ── Helpers ───────────────────────────────────────────────────
def banner(texto):
    linea = "─" * 60
    print(f"\n{linea}", flush=True)
    print(f"  {texto}", flush=True)
    print(f"{linea}\n", flush=True)

def run(cmd, descripcion="", allow_failure=False, env=None):
    if env is None:
        env = env_fun   # funannotate es el default
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
        if allow_failure:
            print(f"\n⚠  Terminó con código {process.returncode} (esperado en este paso)")
            return False
        else:
            print(f"\n✗ Error (código {process.returncode})")
            sys.exit(1)
    print(f"\n✓ Completado")
    return True

def find_proteins_fa(predict_dir, muestra):
    """
    Busca dinámicamente el .proteins.fa en predict_results/.
    funannotate lo nombra con el nombre taxonómico completo, que no conocemos
    de antemano para cepas nuevas.
    """
    patron = os.path.join(predict_dir, "*.proteins.fa")
    candidatos = glob.glob(patron)
    if not candidatos:
        return None
    if len(candidatos) > 1:
        print(f"⚠  Encontrados varios .proteins.fa en {predict_dir}:")
        for c in candidatos:
            print(f"   {c}")
        print(f"   Usando: {candidatos[0]}")
    return candidatos[0]

# ── Verificaciones previas ────────────────────────────────────
banner(f"INICIO PIPELINE — {MUESTRA}")

if not os.path.isfile(GENOME_MASKED):
    print(f"✗ No se encontró el genoma enmascarado: {GENOME_MASKED}")
    print("  Asegúrate de haber corrido fun_initcleansortmask.py antes.")
    sys.exit(1)

print(f"Muestra  : {MUESTRA}")
print(f"Species  : {SPECIES}")
print(f"Strain   : {STRAIN}")
print(f"Genoma   : {GENOME_MASKED}")

# ─────────────────────────────────────────────────────────────
# PASO 1: funannotate predict
# ─────────────────────────────────────────────────────────────
banner(f"PASO 1 — funannotate predict ({MUESTRA})")

run([
    "funannotate", "predict",
    "-i", GENOME_MASKED,
    "-o", DIR_FUNANN,
    "-s", SPECIES,
    "--strain", STRAIN,
    "--busco_db", LINEAGE,
    "--busco_seed_species", "fusarium_graminearum",
    "--organism", "fungus",
    "--cpus", CPUS,
], descripcion=f"funannotate predict — {MUESTRA}", env=env_fun)

# ─────────────────────────────────────────────────────────────
# PASO 2: InterProScan sobre proteínas predichas
# ─────────────────────────────────────────────────────────────
banner(f"PASO 2 — InterProScan ({MUESTRA})")

# Buscar el .proteins.fa dinámicamente (el nombre incluye el taxón)
proteins_fa = find_proteins_fa(PREDICT_DIR, MUESTRA)
if proteins_fa is None:
    print(f"✗ No se encontró ningún .proteins.fa en {PREDICT_DIR}")
    print("  El predict no generó resultados. Revisa el log.")
    sys.exit(1)
print(f"  Proteínas encontradas: {proteins_fa}")

# InterProScan es idempotente: si el XML ya existe, se salta
if os.path.isfile(IPR_XML):
    print(f"\n⚠  Ya existe {IPR_XML} — saltando InterProScan")
else:
    os.makedirs(f"{DIR_FUNANN}/ipr_temp", exist_ok=True)
    run([
        IPR_SH,
        "-i", proteins_fa,
        "-f", "XML",
        "-o", IPR_XML,
        "-goterms",
        "-pa",
        "-cpu", CPUS,
        "-T", f"{DIR_FUNANN}/ipr_temp",
    ], descripcion=f"InterProScan — {MUESTRA}", env=env_sys)

# ─────────────────────────────────────────────────────────────
# PASO 3: funannotate annotate — primera pasada (falla en BUSCO)
# ─────────────────────────────────────────────────────────────
banner(f"PASO 3 — funannotate annotate primera pasada ({MUESTRA})")
print("  (Se espera que falle en la etapa BUSCO — es normal)")

run([
    "funannotate", "annotate",
    "-i", DIR_FUNANN,
    "--busco_db", LINEAGE,
    "--cpus", CPUS,
], descripcion=f"funannotate annotate primera pasada — {MUESTRA}",
   allow_failure=True, env=env_fun)

# Verificar que el annotate llegó a generar genome.proteins.fasta
if not os.path.isfile(PROTEINS_FASTA):
    print(f"\n✗ No se encontró: {PROTEINS_FASTA}")
    print("  El annotate no llegó a generar las proteínas. Revisa el log.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# PASO 4: BUSCO manual sobre genome.proteins.fasta
# ─────────────────────────────────────────────────────────────
banner(f"PASO 4 — BUSCO manual ({MUESTRA})")

run([
    "busco",
    "-i", PROTEINS_FASTA,
    "-o", "run_busco_test",
    "--out_path", ANNOTATE_MISC,
    "-l", LINEAGE,
    "-m", "proteins",
    "-c", CPUS,
    "--offline",
    "--force",
], descripcion=f"BUSCO sobre proteínas — {MUESTRA}", env=env_busco)

# ─────────────────────────────────────────────────────────────
# PASO 5: Copiar tabla BUSCO donde funannotate la espera
# ─────────────────────────────────────────────────────────────
banner(f"PASO 5 — Copiar tabla BUSCO ({MUESTRA})")

if not os.path.isfile(BUSCO_TABLE):
    print(f"✗ No se generó la tabla BUSCO esperada: {BUSCO_TABLE}")
    sys.exit(1)

os.makedirs(BUSCO_DEST_DIR, exist_ok=True)
shutil.copy(BUSCO_TABLE, BUSCO_DEST_FILE)
print(f"✓ Tabla BUSCO copiada:")
print(f"  origen  : {BUSCO_TABLE}")
print(f"  destino : {BUSCO_DEST_FILE}")

# ─────────────────────────────────────────────────────────────
# PASO 6: funannotate annotate final — integra IPR + BUSCO
# ─────────────────────────────────────────────────────────────
banner(f"PASO 6 — funannotate annotate final ({MUESTRA})")

run([
    "funannotate", "annotate",
    "-i", DIR_FUNANN,
    "--busco_db", LINEAGE,
    "--iprscan", IPR_XML,
    "--cpus", CPUS,
], descripcion=f"funannotate annotate final — {MUESTRA}", env=env_fun)

# ─────────────────────────────────────────────────────────────
banner(f"PIPELINE COMPLETO — {MUESTRA}")
print(f"  Resultados: {DIR_FUNANN}/annotate_results/")