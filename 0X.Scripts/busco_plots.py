#!/usr/bin/env python3
# =============================================================================
# Genera gráficos BUSCO individuales y comparativo a partir de los JSON
# Uso: python3 busco_plots.py
# =============================================================================

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

# ── Rutas ─────────────────────────────────────────────────────────────────────
BUSCO_DIR  = "/srv/TFM/PL-iteracion.05/04.BUSCO"
OUTPUT_DIR = "/srv/TFM/PL-iteracion.05/04.BUSCO/figures"
CEPAS      = ["T16", "T22", "T36"]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Colores estándar BUSCO ────────────────────────────────────────────────────
COLORS = {
    "S": "#1D9E75",   # Complete single-copy  — verde
    "D": "#085041",   # Complete duplicated   — verde oscuro
    "F": "#EF9F27",   # Fragmented            — naranja
    "M": "#E24B4A",   # Missing               — rojo
}

# ── Función: leer JSON ────────────────────────────────────────────────────────
def parse_busco_json(cepa):
    json_path = os.path.join(
        BUSCO_DIR, f"{cepa}_busco",
        f"short_summary.specific.hypocreales_odb12.{cepa}_busco.json"
    )
    with open(json_path) as f:
        data = json.load(f)

    r = data["results"]

    return {
        "cepa":  cepa,
        "total": r["n_markers"],
        "S":     r["Single copy BUSCOs"],
        "D":     r["Multi copy BUSCOs"],
        "F":     r["Fragmented BUSCOs"],
        "M":     r["Missing BUSCOs"],
        "S_pct": r["Single copy percentage"],
        "D_pct": r["Multi copy percentage"],
        "F_pct": r["Fragmented percentage"],
        "M_pct": r["Missing percentage"],
    }

# ── Función: etiqueta resumen estilo BUSCO ────────────────────────────────────
def busco_label(d):
    return (
        f"C:{d['S_pct']+d['D_pct']:.1f}% "
        f"[S:{d['S_pct']:.1f}%, D:{d['D_pct']:.1f}%], "
        f"F:{d['F_pct']:.1f}%, "
        f"M:{d['M_pct']:.1f}%, "
        f"n:{d['total']}"
    )

# ── Función: dibujar una barra BUSCO horizontal ───────────────────────────────
def draw_bar(ax, y, data, bar_height=0.6):
    left = 0
    for key in ["S", "D", "F", "M"]:
        pct = data[f"{key}_pct"]
        ax.barh(y, pct, left=left, height=bar_height,
                color=COLORS[key], edgecolor="white", linewidth=0.4)
        if pct > 3:
            ax.text(left + pct / 2, y, f"{pct:.1f}%",
                    ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold")
        left += pct

# ── Leer datos de las tres cepas ──────────────────────────────────────────────
datasets = [parse_busco_json(c) for c in CEPAS]

# ── Plots individuales ────────────────────────────────────────────────────────
for d in datasets:
    fig, ax = plt.subplots(figsize=(10, 2.5))

    draw_bar(ax, 0, d, bar_height=0.5)

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 0.6)
    ax.set_xlabel("% BUSCOs", fontsize=10)
    ax.set_yticks([])
    ax.set_title(
        f"{d['cepa']} — BUSCO hypocreales_odb12\n{busco_label(d)}",
        fontsize=10, pad=10
    )
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.xaxis.set_tick_params(labelsize=9)

    # Leyenda
    legend = [
        mpatches.Patch(color=COLORS["S"], label=f"Complete single-copy (S): {d['S']}"),
        mpatches.Patch(color=COLORS["D"], label=f"Complete duplicated (D): {d['D']}"),
        mpatches.Patch(color=COLORS["F"], label=f"Fragmented (F): {d['F']}"),
        mpatches.Patch(color=COLORS["M"], label=f"Missing (M): {d['M']}"),
    ]
    ax.legend(handles=legend, loc="lower center",
              bbox_to_anchor=(0.5, -0.7), ncol=2,
              fontsize=8, frameon=False)

    fig.tight_layout()

    for fmt in ["png", "pdf"]:
        out = os.path.join(OUTPUT_DIR, f"{d['cepa']}_busco.{fmt}")
        fig.savefig(out, dpi=200, bbox_inches="tight")
        print(f"  → {out}")

    plt.close(fig)

# ── Plot comparativo ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 4))

for i, d in enumerate(datasets):
    draw_bar(ax, i, d, bar_height=0.6)
    ax.text(-1, i, d["cepa"], ha="right", va="center",
            fontsize=10, fontweight="bold")
    ax.text(101, i, busco_label(d), ha="left", va="center", fontsize=7.5,
            color="#444444")

ax.set_xlim(0, 100)
ax.set_ylim(-0.7, len(CEPAS) - 0.3)
ax.set_xlabel("% BUSCOs", fontsize=10)
ax.set_yticks([])
ax.set_title(
    "Comparativa BUSCO — T16 · T22 · T36\nhypocreales_odb12",
    fontsize=11, pad=12
)
ax.spines[["top", "left", "right"]].set_visible(False)
ax.xaxis.set_tick_params(labelsize=9)

legend = [
    mpatches.Patch(color=COLORS["S"], label="Complete single-copy (S)"),
    mpatches.Patch(color=COLORS["D"], label="Complete duplicated (D)"),
    mpatches.Patch(color=COLORS["F"], label="Fragmented (F)"),
    mpatches.Patch(color=COLORS["M"], label="Missing (M)"),
]
ax.legend(handles=legend, loc="lower center",
          bbox_to_anchor=(0.5, -0.35), ncol=4,
          fontsize=9, frameon=False)

fig.tight_layout()

for fmt in ["png", "pdf"]:
    out = os.path.join(OUTPUT_DIR, f"busco_comparative_T16_T22_T36.{fmt}")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"  → {out}")

plt.close(fig)

print("\nListo. Figuras en:", OUTPUT_DIR)
