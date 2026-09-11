#!/usr/bin/env python3
"""PreToolUse(Bash) safety net for UNATTENDED autonomous runs.

Fires on EVERY Bash tool call in EVERY permission mode -- including
`--permission-mode auto` and `bypassPermissions`, where the interactive
"Do you want to proceed?" prompts and (in bypass mode) the allow/deny RULES
are skipped. Hooks still run, so this is the shell-independent hard stop for
the handful of things an unattended data-analysis build must never do:

  1. Destroy files / the machine        (rm -rf, del /s, format, dd, shutdown, ...)
  2. Reach the network / exfiltrate      (curl, wget, scp, Invoke-WebRequest, ...)
  3. Mutate the environment mid-run      (pip/conda/npm install)  -> set up the venv FIRST
  4. Publish or rewrite history          (git push, git reset --hard, git clean)

Exit 0 = allow (defer to normal permission flow). Exit 2 = BLOCK; the stderr
message is shown to Claude so it can adapt instead of stalling. It stays
stdlib-only (json/re/sys) so ANY python on PATH can run it; it never needs the
analysis venv. Reads of data/secrets are handled by the deny-list, not here --
this hook only blocks WRITES/DELETES and dangerous verbs.

To harden further, add patterns to the lists below. To relax (e.g. allow a
specific network fetch), do it INTERACTIVELY, not by weakening this file.
"""
import sys, json, re


def load():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def deny(reason):
    sys.stderr.write("[autonomous guard] BLOCKED: " + reason +
                     "\n  -> If this is genuinely needed, do it in an interactive "
                     "(attended) session, not an unattended run.\n")
    sys.exit(2)


ev = load()
cmd = (ev.get("tool_input", {}) or {}).get("command", "") or ""
c = cmd.replace("\\", "/")   # normalize Windows separators for matching
low = c.lower()

# 1) destructive filesystem / system verbs -------------------------------------
DESTRUCTIVE = [
    r"\brm\s+-[a-z]*[rf]", r"\brm\s+-[a-z]*f\b", r"\brmdir\b", r"\bunlink\b",
    r"\bdel\s+/[sq]", r"\berase\b", r"\brd\s+/s", r"\bshred\b",
    r"\bmkfs\b", r"\bdd\s+if=", r"\bformat\b", r"\bformat-volume\b",
    r"\bremove-item\b", r"\bclear-content\b", r"\brmtree\b",
    r"\bsudo\b", r"\bdoas\b", r"\brunas\b",
    r"\bshutdown\b", r"\breboot\b", r"\bhalt\b", r"\bstop-computer\b",
    r":\(\)\s*\{",                                   # fork bomb
    r"\b(chmod|chown)\s+-[a-z]*r",                   # recursive perms
    r">\s*/dev/sd", r"\bmormat\b",
]
for pat in DESTRUCTIVE:
    if re.search(pat, low):
        deny(f"destructive command pattern '{pat}'.")

# 2) network egress / remote transfer ------------------------------------------
NET = [r"\bcurl\b", r"\bwget\b", r"\binvoke-webrequest\b", r"\biwr\b",
       r"\binvoke-restmethod\b", r"\birm\s+http", r"\bscp\b", r"\bsftp\b",
       r"\bftp\b", r"\bnc\b", r"\bncat\b", r"\btelnet\b",
       r"\bstart-bitstransfer\b", r"\bssh\b"]
for pat in NET:
    if re.search(pat, low):
        deny(f"network/egress command '{pat}'. Analysis runs offline.")

# 3) environment mutation (do venv setup BEFORE the unattended run) -------------
INSTALL = [r"\bpip\s+install\b", r"\bpip3\s+install\b", r"pip\s+install\b",
           r"\bconda\s+(install|create|remove|update)\b", r"\bnpm\s+(install|i)\b",
           r"\bpoetry\s+add\b", r"\buv\s+(pip\s+)?(install|add)\b",
           r"\bmamba\s+install\b", r"\bapt(-get)?\s+install\b"]
for pat in INSTALL:
    if re.search(pat, low):
        deny(f"package install '{pat}'. Prepare the venv before the run; do not "
             f"change the environment mid-flight.")

# 4) publishing / history rewrite ----------------------------------------------
if re.search(r"\bgit\s+push\b", low):
    deny("git push -- publishing stays a human action.")
if re.search(r"\bgit\s+.*--force\b", low) or re.search(r"\bgit\s+reset\s+--hard\b", low) \
        or re.search(r"\bgit\s+clean\b", low):
    deny("git force/reset --hard/clean -- destructive to the working tree/history.")

sys.exit(0)
