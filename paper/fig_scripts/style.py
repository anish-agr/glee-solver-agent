"""Shared figure style: small serif text and Okabe-Ito colors."""
import matplotlib as mpl

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
VERMILION = "#D55E00"
SKY = "#56B4E9"
GREY = "#8a8a8a"
INK = "#1a1a1a"

SERIF = [
    "Liberation Serif",
    "Nimbus Roman",
    "TeX Gyre Termes",
    "Times New Roman",
    "DejaVu Serif",
]


def setup():
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": SERIF,
        "mathtext.fontset": "stix",
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#666666",
        "axes.linewidth": 0.6,
        "xtick.color": "#666666",
        "ytick.color": "#666666",
        "text.color": INK,
        "axes.labelcolor": INK,
        "grid.color": "#dddddd",
        "grid.linewidth": 0.5,
        "lines.linewidth": 1.4,
        "pdf.fonttype": 42,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })
