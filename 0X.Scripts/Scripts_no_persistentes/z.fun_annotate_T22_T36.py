
#!/usr/bin/env python3
import subprocess
import os
import sys

BASE_DIR   = "/srv/TFM/PL-iteracion.05"
SRA_ASP    = f"{BASE_DIR}/00.Archivos_principales/SRA-seq/T_asperellum"
SRA_HAM    = f"{BASE_DIR}/00.Archivos_principales/SRA-seq/T_hamatum"
LINEAGE    = "hypocreales_odb12"

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

def anotar_cepa(MUESTRA, SPECIES, STRAIN):
    print(f"\n{'='*60}")
    print(f"  Iniciando anotación: {MUESTRA}")
    print(f"{'='*60}\n")

    DIR_FUNANN    = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"
    GENOME_FILT   = f"{BASE_DIR}/03.Pulido_y_filtrado/{MUESTRA}/{MUESTRA}_filtered_3000.fasta"
    GENOME_CLEAN  = f"{DIR_FUNANN}/{MUESTRA}_clean.fasta"
    GENOME_SORTED = f"{DIR_FUNANN}/{MUESTRA}_sorted.fasta"
    GENOME_MASKED = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"

    os.makedirs(DIR_FUNANN, exist_ok=True)

    # ── 1. Clean ──────────────────────────────────────────────
    run([
        "funannotate", "clean",
        "-i", GENOME_FILT,
        "-o", GENOME_CLEAN,
        "--minlen", "500",
        "--pident", "95",
        "--cov", "95",
    ], descripcion=f"Clean — {MUESTRA}")

    # ── 2. Sort ───────────────────────────────────────────────
    run([
        "funannotate", "sort",
        "-i", GENOME_CLEAN,
        "-o", GENOME_SORTED,
        "-b", "scaffold",
        "--minlen", "0",
    ], descripcion=f"Sort — {MUESTRA}")

    # ── 3. Mask ───────────────────────────────────────────────
    run([
        "funannotate", "mask",
        "-i", GENOME_SORTED,
        "-o", GENOME_MASKED,
        "--cpus", "16",
    ], descripcion=f"Mask — {MUESTRA}")

    # ── 4. Train ──────────────────────────────────────────────
    run([
        "funannotate", "train",
        "-i", GENOME_MASKED,
        "-o", DIR_FUNANN,
        "--left",
            f"{SRA_ASP}/SRR12495788_1_fixed.fastq.gz",
            f"{SRA_ASP}/SRR12495790_1_fixed.fastq.gz",
            f"{SRA_ASP}/SRR34502155_1_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975571_1_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975598_1_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975614_1_fixed.fastq.gz",
        "--right",
            f"{SRA_ASP}/SRR12495788_2_fixed.fastq.gz",
            f"{SRA_ASP}/SRR12495790_2_fixed.fastq.gz",
            f"{SRA_ASP}/SRR34502155_2_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975571_2_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975598_2_fixed.fastq.gz",
            f"{SRA_HAM}/SRR1975614_2_fixed.fastq.gz",
        "--species", SPECIES,
        "--strain", STRAIN,
        "--cpus", "16",
        "--memory", "26G",
        "--no_normalize_reads",
    ], descripcion=f"Train — {MUESTRA}")

    # ── 5. Predict ────────────────────────────────────────────
    run([
        "funannotate", "predict",
        "-i", GENOME_MASKED,
        "-o", DIR_FUNANN,
        "-s", SPECIES,
        "--strain", STRAIN,
        "--busco_db", LINEAGE,
        "--busco_seed_species", "fusarium_graminearum",
        "--organism", "fungal",
        "--cpus", "16",
    ], descripcion=f"Predict — {MUESTRA}")

    # ── 6. Annotate ───────────────────────────────────────────
    run([
        "funannotate", "annotate",
        "-i", DIR_FUNANN,
        "--busco_db", LINEAGE,
        "--cpus", "16",
    ], descripcion=f"Annotate — {MUESTRA}")

    print(f"\n✓ Anotación completa para {MUESTRA}")

# ─── Correr para T22 y T36 ────────────────────────────────────
anotar_cepa("T22", "Trichoderma sp", "T22")
anotar_cepa("T36", "Trichoderma sp", "T36")
# 
# 
# #!/usr/bin/env python3
# import subprocess
# import os
# import sys

# BASE_DIR     = "/srv/TFM/PL-iteracion.05"
# ENVS         = "/opt/miniconda3/envs"
# SRA_ASP      = f"{BASE_DIR}/00.Archivos_principales/SRA-seq/T_asperellum"
# SRA_HAM      = f"{BASE_DIR}/00.Archivos_principales/SRA-seq/T_hamatum"
# LINEAGE      = "hypocreales_odb12"
# BUSCO_PATH   = "/srv/biodata/busco_downloads"
# FUNANN_DB    = "/srv/biodata/funannotate_db"

# def run(cmd, descripcion="", log_prefix=""):
#     if descripcion:
#         print(f"\n▶ {descripcion}", flush=True)
#     process = subprocess.Popen(
#         cmd,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,
#         text=True
#     )
#     for line in process.stdout:
#         print(line, end="", flush=True)
#     process.wait()
#     if process.returncode != 0:
#         print(f"\n✗ Error (código {process.returncode})")
#         sys.exit(1)
#     else:
#         print(f"\n✓ Completado")
#     return process.returncode

# def anotar_cepa(MUESTRA, SPECIES, STRAIN):
#     print(f"\n{'='*60}")
#     print(f"  Iniciando anotación: {MUESTRA}")
#     print(f"{'='*60}\n")

#     DIR_FUNANN     = f"{BASE_DIR}/04.Funannotate/{MUESTRA}"
#     GENOME_FILT    = f"{BASE_DIR}/03.Pulido_y_filtrado/{MUESTRA}/{MUESTRA}_filtered_3000.fasta"
#     GENOME_CLEAN   = f"{DIR_FUNANN}/{MUESTRA}_clean.fasta"
#     GENOME_SORTED  = f"{DIR_FUNANN}/{MUESTRA}_sorted.fasta"
#     GENOME_MASKED  = f"{DIR_FUNANN}/{MUESTRA}_masked.fasta"

#     os.makedirs(DIR_FUNANN, exist_ok=True)

#     # ── 1. Clean ──────────────────────────────────────────────
#     run([
#         "funannotate", "clean",
#         "-i", GENOME_FILT,
#         "-o", GENOME_CLEAN,
#         "--minlen", "500",
#         "--pident", "95",
#         "--cov", "95",
#     ], descripcion=f"Clean — {MUESTRA}")

#     # ── 2. Sort ───────────────────────────────────────────────
#     run([
#         "funannotate", "sort",
#         "-i", GENOME_CLEAN,
#         "-o", GENOME_SORTED,
#         "-b", "scaffold",
#         "--minlen", "0",
#     ], descripcion=f"Sort — {MUESTRA}")

#     # ── 3. Mask ───────────────────────────────────────────────
#     run([
#         "funannotate", "mask",
#         "-i", GENOME_SORTED,
#         "-o", GENOME_MASKED,
#         "--cpus", "16",
#     ], descripcion=f"Mask — {MUESTRA}")

#     # ── 4. Train ──────────────────────────────────────────────
#     # Para T22 y T36 (especie desconocida) usamos RNA-seq de ambas especies
#     run([
#         "funannotate", "train",
#         "-i", GENOME_MASKED,
#         "-o", DIR_FUNANN,
#         "--left",
#             f"{SRA_ASP}/SRR12495788_1_fixed.fastq.gz",
#             f"{SRA_ASP}/SRR12495790_1_fixed.fastq.gz",
#             f"{SRA_ASP}/SRR34502155_1_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975571_1_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975598_1_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975614_1_fixed.fastq.gz",
#         "--right",
#             f"{SRA_ASP}/SRR12495788_2_fixed.fastq.gz",
#             f"{SRA_ASP}/SRR12495790_2_fixed.fastq.gz",
#             f"{SRA_ASP}/SRR34502155_2_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975571_2_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975598_2_fixed.fastq.gz",
#             f"{SRA_HAM}/SRR1975614_2_fixed.fastq.gz",
#         "--species", SPECIES,
#         "--strain", STRAIN,
#         "--cpus", "16",
#         "--memory", "26G",
#         "--no_normalize_reads",
#     ], descripcion=f"Train — {MUESTRA}")

#     # ── 5. Predict ────────────────────────────────────────────
#     run([
#         "funannotate", "predict",
#         "-i", GENOME_MASKED,
#         "-o", DIR_FUNANN,
#         "-s", SPECIES,
#         "--strain", STRAIN,
#         "--busco_db", "hypocreales_odb12",
#         "--busco_seed_species","fusarium_graminearum",
#         "--organism", "fungal",
#         "--cpus", "16",
#     ], descripcion=f"Predict — {MUESTRA}")

#     # ── 6. Annotate ───────────────────────────────────────────
#     run([
#         "funannotate", "annotate",
#         "-i", DIR_FUNANN,
#         "--busco_db", LINEAGE,
#         "--cpus", "16",
#     ], descripcion=f"Annotate — {MUESTRA}")

#     print(f"\n✓ Anotación completa para {MUESTRA}")

# # ─── Correr para T22 y T36 ────────────────────────────────────
# anotar_cepa("T22", "Trichoderma sp", "T22")
# anotar_cepa("T36", "Trichoderma sp", "T36")
