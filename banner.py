#!/usr/bin/env python3
"""
banner.py  --  aioli-streetphere : ecran d'introduction
=======================================================
Logo du collectif, liens, credits et avertissement d'usage,
affiches une fois au lancement du programme.

Aucune dependance : ce module doit fonctionner AVANT le venv
(le module 3D tourne sur le Python systeme).

Utilisation :
    import banner ; banner.show("streetphere")   # depuis un script
    python banner.py streetphere                 # depuis un .bat

Le banner ne s'affiche qu'une fois par lancement : la variable
d'environnement AIOLI_BANNER est posee, les sous-processus la voient
et se taisent. `banner.show(force=True)` passe outre.
"""

import os
import sys

VERSION = "2.4"

SITE      = "aiolicollective.com"
INSTAGRAM = "@aioli.collective"
REPO      = "github.com/aiolicollective/aioli-streetphere"

GUARD_ENV = "AIOLI_BANNER"


# ==============================================================================
#  LOGO
# ==============================================================================

# "> ai.oli/" -- logo v1 du collectif (prompt de terminal)
LOGO_UNICODE = r"""
 ██╗       █████╗ ██╗    ██████╗ ██╗     ██╗    ██╗
 ╚██╗     ██╔══██╗██║   ██╔═══██╗██║     ██║   ██╔╝
  ╚██╗    ███████║██║   ██║   ██║██║     ██║  ██╔╝
  ██╔╝    ██╔══██║██║   ██║   ██║██║     ██║ ██╔╝
 ██╔╝     ██║  ██║██║██╗╚██████╔╝███████╗██║██╔╝
 ╚═╝      ╚═╝  ╚═╝╚═╝╚═╝ ╚═════╝ ╚══════╝╚═╝╚═╝
"""

# Repli pour les consoles qui ne savent pas afficher l'UTF-8
LOGO_ASCII = r"""
 ##          ###    ####      #######  ##       ####       ##
  ##        ## ##    ##      ##     ## ##        ##       ##
   ##      ##   ##   ##      ##     ## ##        ##      ##
    ##    ##     ##  ##      ##     ## ##        ##     ##
   ##     #########  ##      ##     ## ##        ##    ##
  ##      ##     ##  ##  ### ##     ## ##        ##   ##
 ##       ##     ## #### ###  #######  ######## #### ##
"""


# ==============================================================================
#  CAPACITES DU TERMINAL
# ==============================================================================

def _stdout_encoding():
    return (getattr(sys.stdout, "encoding", None) or "").lower()


def _use_utf8():
    """Force l'UTF-8 sur stdout si possible, et dit si le logo passe."""
    try:
        # Python 3.7+ : on repasse stdout en UTF-8 (cmd.exe reste souvent en cp850)
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    enc = _stdout_encoding()
    if not enc:
        return False
    try:
        LOGO_UNICODE.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _use_color():
    """Couleurs ANSI : seulement en vrai terminal, et si non desactivees."""
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    # Windows 10+ : activer le traitement des sequences VT sur la console
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))
    except Exception:
        return False


def _use_links():
    """Liens cliquables (OSC 8) : Windows Terminal, iTerm, VS Code..."""
    if not sys.stdout.isatty():
        return False
    return bool(
        os.environ.get("WT_SESSION")
        or os.environ.get("TERM_PROGRAM")
        or os.environ.get("VSCODE_INJECTION")
    )


# ==============================================================================
#  RENDU
# ==============================================================================

def _build(tool=None):
    utf8  = _use_utf8()
    color = _use_color()
    links = _use_links()

    if color:
        C_LOGO, C_ACC, C_DIM, C_OFF = "\033[1m", "\033[36m", "\033[2m", "\033[0m"
    else:
        C_LOGO = C_ACC = C_DIM = C_OFF = ""

    tee, ell, dot = ("├──", "└──", "·") if utf8 else ("+--", "+--", "-")

    def link(url, label=None):
        label = label or url
        if not links:
            return label
        return "\033]8;;https://%s\033\\%s\033]8;;\033\\" % (url.lstrip("@"), label)

    logo = (LOGO_UNICODE if utf8 else LOGO_ASCII).strip("\n")

    L = [""]
    L += ["%s%s%s" % (C_LOGO, l, C_OFF) for l in logo.split("\n")]
    L += [""]
    L += ["  %scollectif hybride artistes + agents IA %s Marseille%s" % (C_DIM, dot, C_OFF)]
    L += [""]

    title = tool or "streetphere"
    L += ["  %s%s v%s%s  %spanoramas 360 equirectangulaires + environnements 3D a l'echelle%s"
          % (C_ACC, title, VERSION, C_OFF, C_DIM, C_OFF)]
    L += [""]
    L += ["  %s site        %s" % (tee, link(SITE))]
    L += ["  %s instagram   %s" % (tee, link("instagram.com/aioli.collective", INSTAGRAM))]
    L += ["  %s github      %s" % (ell, link(REPO))]
    L += [""]
    L += ["  %ssources   donnees Google Street View / Google Earth %s projet non affilie a Google%s"
          % (C_DIM, dot, C_OFF)]
    L += ["  %s          earth3d : earth-reverse-engineering (retroplasma) %s three.js %s Pillow %s numpy%s"
          % (C_DIM, dot, dot, dot, C_OFF)]
    L += ["  %susage     personnel / recherche, sans garantie %s details : LICENSE et CREDITS.md%s"
          % (C_DIM, dot, C_OFF)]
    L += [""]
    return "\n".join(L)


def show(tool=None, force=False):
    """Affiche le banner, une seule fois par lancement."""
    if not force and os.environ.get(GUARD_ENV):
        return
    os.environ[GUARD_ENV] = "1"
    try:
        print(_build(tool))
        sys.stdout.flush()
    except Exception:
        # Un banner ne doit jamais empecher le programme de tourner
        print("\n  > ai.oli/  %s  %s\n" % (SITE, REPO))


if __name__ == "__main__":
    show(sys.argv[1] if len(sys.argv) > 1 else None, force=True)
