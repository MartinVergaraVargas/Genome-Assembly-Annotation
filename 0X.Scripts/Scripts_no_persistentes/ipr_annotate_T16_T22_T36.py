#!/usr/bin/env python3
"""
ipr_annotate_T16_T22_T36.py
Corre InterProScan + funannotate annotate para las 3 cepas de Trichoderma.
Requisito: activar el entorno funannotate antes de correr este script.

Uso:
    nohup python3 ipr_annotate_T16_T22_T36.py > ipr_annotate.log 2>&1 &
    tail -f ipr_annotate.log
"""

import subprocess
import sys
import os

# ── Configuración global ──────────────────────────────────────────────────────
BASE_DIR    = "/srv/TFM/PL-iteracion.05/04.Funannotate"
IPR_SH      = "/srv/biodata/interproscan_db/interproscan-5.77-108.0/interproscan.sh"
LINEAGE     = "/srv/biodata/busco_downloads/lineages/hypocreales_odb12"
CPUS        = "14"

CEPAS = [
    # {
    #     "muestra"  : "T16",
    #     "dir"      : f"{BASE_DIR}/T16",
    #     "proteins" : f"{BASE_DIR}/T16/predict_results/Trichoderma_asperellum_T16.proteins.fa",
    #     "species"  : "Trichoderma asperellum",
    #     "strain"   : "T16",
    # },
    # {
    #     "muestra"  : "T22",
    #     "dir"      : f"{BASE_DIR}/T22",
    #     "proteins" : f"{BASE_DIR}/T22/predict_results/Trichoderma_sp._T22.proteins.fa",
    #     "species"  : "Trichoderma sp.",
    #     "strain"   : "T22",
    # },
    {
        "muestra"  : "T36",
        "dir"      : f"{BASE_DIR}/T36",
        "proteins" : f"{BASE_DIR}/T36/predict_results/Trichoderma_sp._T36.proteins.fa",
        "species"  : "Trichoderma sp.",
        "strain"   : "T36",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def banner(texto):
    linea = "─" * 60
    print(f"\n{linea}", flush=True)
    print(f"  {texto}", flush=True)
    print(f"{linea}", flush=True)

def run(cmd, descripcion=""):
    if descripcion:
        print(f"\n▶ {descripcion}", flush=True)
    print(f"  CMD: {' '.join(cmd)}\n", flush=True)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in process.stdout:
        print(line, end="", flush=True)
    process.wait()
    if process.returncode != 0:
        print(f"\n✗ Error (código {process.returncode})")
        sys.exit(1)
    print(f"\n✓ Completado")

# ── Pipeline por cepa ─────────────────────────────────────────────────────────
def procesar_cepa(cepa):
    muestra  = cepa["muestra"]
    dir_fun  = cepa["dir"]
    proteins = cepa["proteins"]
    ipr_xml  = f"{dir_fun}/interproscan_{muestra}.xml"

    banner(f"CEPA {muestra}")

    # Verificar que el archivo de proteínas existe
    if not os.path.isfile(proteins):
        print(f"✗ No se encontró: {proteins}")
        sys.exit(1)

    # ── Paso 1: InterProScan ──────────────────────────────────────────────────
    # Solo corre si el XML no existe ya (permite retomar si el script se interrumpe)
    if os.path.isfile(ipr_xml):
        print(f"\n⚠ Ya existe {ipr_xml} — saltando InterProScan para {muestra}")
    else:
        run([
            IPR_SH,
            "-i", proteins,
            "-f", "XML",
            "-o", ipr_xml,
            "-goterms",
            "-pa",
            "-cpu", CPUS,
            "-T", f"{dir_fun}/ipr_temp",
        ], descripcion=f"InterProScan — {muestra}")

    # ── Paso 2: funannotate annotate ──────────────────────────────────────────
    run([
        "funannotate", "annotate",
        "-i", dir_fun,
        "--busco_db", LINEAGE,
        "--iprscan", ipr_xml,
        "--cpus", CPUS,
    ], descripcion=f"funannotate annotate — {muestra}")

    print(f"\n✓ Cepa {muestra} completada")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    for cepa in CEPAS:
        procesar_cepa(cepa)

    banner("TODAS LAS CEPAS COMPLETADAS")
    print("Resultados en:")
    for cepa in CEPAS:
        print(f"  {cepa['dir']}/annotate_results/")