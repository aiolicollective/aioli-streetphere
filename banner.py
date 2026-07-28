#!/usr/bin/env python3
"""
banner.py  --  aioli-streetphere: intro screen
==============================================
Collective logo, links, credits and usage disclaimer,
shown once when the program starts.

No dependency: this module must work BEFORE the venv exists
(the 3D module runs on the system Python).

Usage:
    import banner ; banner.show("streetphere")   # from a script
    python banner.py streetphere                 # from a .bat

The banner is shown only once per run: the AIOLI_BANNER environment
variable is set, sub-processes see it and stay quiet.
`banner.show(force=True)` overrides that.
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

# "> ai.oli/" -- v1 logo of the collective (a terminal prompt)
LOGO_UNICODE = r"""
 ██╗       █████╗ ██╗    ██████╗ ██╗     ██╗    ██╗
 ╚██╗     ██╔══██╗██║   ██╔═══██╗██║     ██║   ██╔╝
  ╚██╗    ███████║██║   ██║   ██║██║     ██║  ██╔╝
  ██╔╝    ██╔══██║██║   ██║   ██║██║     ██║ ██╔╝
 ██╔╝     ██║  ██║██║██╗╚██████╔╝███████╗██║██╔╝
 ╚═╝      ╚═╝  ╚═╝╚═╝╚═╝ ╚═════╝ ╚══════╝╚═╝╚═╝
"""

# Fallback for consoles that cannot display UTF-8
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
#  TERMINAL CAPABILITIES
# ==============================================================================

def _stdout_encoding():
    return (getattr(sys.stdout, "encoding", None) or "").lower()


def _use_utf8():
    """Forces UTF-8 on stdout if possible, and tells whether the logo fits."""
    try:
        # Python 3.7+: switch stdout back to UTF-8 (cmd.exe often stays on cp850)
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
    """ANSI colours: only in a real terminal, and only if not disabled."""
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    # Windows 10+: enable VT sequence processing on the console
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
    """Clickable links (OSC 8): Windows Terminal, iTerm, VS Code..."""
    if not sys.stdout.isatty():
        return False
    return bool(
        os.environ.get("WT_SESSION")
        or os.environ.get("TERM_PROGRAM")
        or os.environ.get("VSCODE_INJECTION")
    )


# ==============================================================================
#  RENDERING
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
    L += ["  %shybrid collective of artists + AI agents %s Marseille%s" % (C_DIM, dot, C_OFF)]
    L += [""]

    title = tool or "streetphere"
    L += ["  %s%s v%s%s  %s2:1 equirectangular 360 panoramas + true-to-scale 3D environments%s"
          % (C_ACC, title, VERSION, C_OFF, C_DIM, C_OFF)]
    L += [""]
    L += ["  %s site        %s" % (tee, link(SITE))]
    L += ["  %s instagram   %s" % (tee, link("instagram.com/aioli.collective", INSTAGRAM))]
    L += ["  %s github      %s" % (ell, link(REPO))]
    L += [""]
    L += ["  %ssources   Google Street View / Google Earth data %s project not affiliated with Google%s"
          % (C_DIM, dot, C_OFF)]
    L += ["  %s          earth3d : earth-reverse-engineering (retroplasma) %s three.js %s Pillow %s numpy%s"
          % (C_DIM, dot, dot, dot, C_OFF)]
    L += ["  %susage     personal / research, without warranty %s details: LICENSE and CREDITS.md%s"
          % (C_DIM, dot, C_OFF)]
    L += [""]
    return "\n".join(L)


def show(tool=None, force=False):
    """Shows the banner, only once per run."""
    if not force and os.environ.get(GUARD_ENV):
        return
    os.environ[GUARD_ENV] = "1"
    try:
        print(_build(tool))
        sys.stdout.flush()
    except Exception:
        # A banner must never keep the program from running
        print("\n  > ai.oli/  %s  %s\n" % (SITE, REPO))


if __name__ == "__main__":
    show(sys.argv[1] if len(sys.argv) > 1 else None, force=True)
