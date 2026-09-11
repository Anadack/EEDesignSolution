#!/usr/bin/env python3
"""Signal naming convention validator for E/E Architect Design v4.

Convention: <SYSTEM>_<Function>_[<POSITION>_]<TYPE>
  SYSTEM   : 2-8 uppercase letters only  (e.g. SBRK, PBRK, AWD, DRVC)
  Function : CamelCase, starts uppercase  (e.g. ActrPresr, CluPedlPosn)
  POSITION : optional, from known set     (e.g. LE, RI, RELE, FR, RE)
  TYPE     : 2-8 uppercase letters only  (e.g. SNSR, SWT, EVHS, HS, LS)

One warning is emitted per non-compliant signal name, showing the current
name and a best-effort proposed correction.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Convention constants
# ---------------------------------------------------------------------------

KNOWN_POSITIONS: frozenset[str] = frozenset({
    'LE', 'RI', 'RELE', 'RERI', 'FR', 'RE', 'FRLE', 'FRRI',
    'FL', 'RL', 'RR', 'LH', 'RH', 'L', 'R',
    'FRONT', 'REAR', 'LEFT', 'RIGHT', 'CENTER', 'CTR',
})

KNOWN_TYPES: frozenset[str] = frozenset({
    # Sensors / actuators
    'SNSR', 'SWT', 'EVHS', 'EVLS', 'RELE', 'HS', 'LS', 'CMD', 'VLV',
    'SOL', 'COIL', 'ACT', 'MTR', 'PUMP', 'VALVE', 'FUSE', 'RELN',
    'PWM', 'LED', 'BUS', 'CTRL', 'MCU', 'ECU',
    # Signal types
    'TEMP', 'PRES', 'ANGL', 'SPD', 'CUR', 'POS', 'FRC', 'THR', 'TRQ',
    'PWR', 'GND', 'REF', 'SIG', 'OUT', 'IN',
    # Interface types used as TYPE suffix
    'CAN', 'LIN', 'ETH', 'SENT',
    # Relay / signal-lamp / buzzer (mixed-case exception: Buz)
    'REL', 'SIGN', 'Buz',
})

# Patterns that are clearly power/ground infrastructure → exempt from naming check
_INFRA_RE = re.compile(
    r'^(CAN_H|CAN_L|CAN_GND|CAN_SHLD|CAN_VPLUS(?:_[\w]+)?|'
    r'LIN_H|LIN_L|LIN_GND|'
    r'POWER_GND|SUPPLY_GND|SUPPLY_\w+|'
    r'BATT(?:_[\w]+)?|GND(?:_[\w]+)?|VCC(?:_[\w]+)?|VIN(?:_[\w]+)?)$',
    re.IGNORECASE)

# Valid token patterns
_SYSTEM_RE  = re.compile(r'^[A-Z]{2,8}$')
# CamelCase, optionally prefixed with a lowercase 'e' meaning "electronic"
# (e.g. eTBA, eLSPmp1Ctrl), or a leading ordinal digit (e.g. 3rdCirc), as
# used throughout the CEA3 naming convention.
_FUNCTION_RE = re.compile(
    r'^(e[A-Z][A-Za-z0-9]{1,29}|[A-Z][A-Za-z0-9]{1,30}|\d+[A-Za-z][A-Za-z0-9]{1,29})$')
_TYPE_RE    = re.compile(r'^([A-Z]{2,8}|Buz)$')
# A single Function token may itself span several underscore-separated
# CamelCase words (e.g. Ext_Lifting, Ext_Lowering) — used to validate the
# middle (non-position) tokens of a signal name individually.
_FUNC_PART_RE = re.compile(r'^(e[A-Z][A-Za-z0-9]*|[A-Z][A-Za-z0-9]*|\d+[A-Za-z][A-Za-z0-9]*)$')


# Measurement-unit suffixes in raw device names → TYPE mapping
_MEAS_MAP: dict[str, str] = {
    '4_20MA': 'SNSR', '4_20MV': 'SNSR', '4_20V': 'SNSR',
    '0_10V': 'SNSR', '0_5V': 'SNSR', '0_20V': 'SNSR', '0_4MA': 'SNSR',
    '4MA': 'SNSR', '20MA': 'SNSR', '10V': 'SNSR',
    'SUPPLY': 'PWR', 'PLUS': 'PWR', 'VPLUS': 'PWR',
    '24V': 'PWR', '12V': 'PWR', '5V': 'PWR', '9_36V': 'PWR', '9_32V': 'PWR',
    'GND': 'GND', '0V': 'GND', 'GND1': 'GND', 'GND2': 'GND',
    'CMD': 'CMD', 'COMMAND': 'CMD',
    'HS': 'HS', 'LS': 'LS',
    'OUT': 'SNSR', 'OUT1': 'SNSR', 'OUT2': 'SNSR', 'PNP': 'SNSR', 'NPN': 'SNSR',
    'LOOP': 'SNSR', 'SHIELD': 'SNSR', 'SHLD': 'SNSR',
    'CAN_H': 'CAN', 'CAN_L': 'CAN', 'CAN_GND': 'CAN', 'CAN_SHLD': 'CAN',
    'CAN': 'CAN',
    'UB': 'PWR', 'UB1': 'PWR', 'UB2': 'PWR',
    'REL': 'REL', 'RELAY': 'REL',
    'SIGN': 'SIGN', 'SIGNAL': 'SIGN',
    'BUZ': 'Buz', 'BUZZER': 'Buz',
}

# Short letter sequences that are unit abbreviations (not function descriptors)
_UNIT_SHORTS: frozenset[str] = frozenset({
    'ma', 'mv', 'v', 'a', 'hz', 'deg', 'bar', 'db',
    'pnp', 'npn', 'ub', 'h', 'l', 'lp',
})

# ---------------------------------------------------------------------------
# Compliance checker
# ---------------------------------------------------------------------------

def _is_compliant(name: str) -> bool:
    """Return True if signal name matches <SYSTEM>_<Function>[_<POSITION>]_<TYPE>.

    Function may be a single CamelCase token (ActrPresr) or span several
    underscore-separated CamelCase tokens treated as one compound function
    (Ext_Lifting, Ext_Lowering), as seen throughout the CEA3 convention.
    """
    parts = name.split('_')
    if len(parts) < 3:
        return False
    system, typ = parts[0], parts[-1]
    if not _SYSTEM_RE.match(system) or not _TYPE_RE.match(typ):
        return False
    middle = parts[1:-1]
    if not middle:
        return False
    if len(middle) >= 2 and middle[-1].upper() in KNOWN_POSITIONS:
        func_parts = middle[:-1]
    else:
        func_parts = middle
    if not func_parts:
        return False
    return all(_FUNC_PART_RE.match(fp) for fp in func_parts)


def _is_exempt(name: str) -> bool:
    """Bus infrastructure and trivial power/ground signals → skip validation."""
    return bool(_INFRA_RE.match(name))


# ---------------------------------------------------------------------------
# Proposal generator
# ---------------------------------------------------------------------------

def _to_camel(tokens: list[str]) -> str:
    """Join tokens into CamelCase, preserving mixed-case tokens and downcasing ALL-CAPS."""
    out = []
    for t in tokens:
        if re.match(r'^[\d_.]+$', t):
            continue
        cleaned = re.sub(r'[\d_.]+$', '', t)
        if not cleaned:
            continue
        if cleaned.isupper():
            # All-caps → CamelCase (Switch, Push, …)
            out.append(cleaned.capitalize())
        elif re.search(r'[A-Z]', cleaned[1:]):
            # Already has internal uppercase → preserve as-is (capitalize first)
            out.append(cleaned[0].upper() + cleaned[1:])
        else:
            out.append(cleaned.capitalize())
    return ''.join(out) or 'Unknown'


def _guess_type(tokens: list[str]) -> str:
    """Heuristically pick a TYPE code from the token list (right-to-left priority)."""
    for t in reversed(tokens):
        upper = t.upper()
        if upper in _MEAS_MAP:
            return _MEAS_MAP[upper]
        # Direct match in known types
        if upper in KNOWN_TYPES:
            return upper
        # Voltage pattern → PWR
        if re.match(r'^\d+V$', upper):
            return 'PWR'
        # Current pattern → SNSR
        if re.match(r'^\d+MA$', upper):
            return 'SNSR'
    return 'SNSR'  # default: assume sensor


def _guess_system(tokens: list[str]) -> str:
    """Pick the best SYSTEM abbreviation from the token list (left-to-right priority)."""
    for t in tokens:
        upper = t.upper()
        # Skip measurement/unit tokens
        if upper in _MEAS_MAP:
            continue
        # Skip known TYPE tokens
        if upper in KNOWN_TYPES:
            continue
        # Keep only letters (strip digits from model numbers like HAT1200 → HAT)
        letters_only = re.sub(r'[^A-Za-z]', '', t).upper()
        if 2 <= len(letters_only) <= 8:
            return letters_only[:6]
    return 'SYS'


def _guess_position(tokens: list[str]) -> str | None:
    """Return a POSITION token if found among middle tokens."""
    for t in tokens[1:-1]:  # skip first (system) and last (type candidate)
        if t.upper() in KNOWN_POSITIONS:
            return t.upper()
    return None


def propose_name(name: str) -> str:
    """Generate a best-effort compliant name from a non-compliant signal name.

    Handles two common patterns:
    - Missing SYSTEM prefix: e.g. ``DirCoilCmd_HS`` → ``??_DirCoilCmd_HS``
    - Device-model-based names: e.g. ``HAT1200_Angle_4_20mA`` → ``HAT_Angle_SNSR``
    """
    raw_parts = name.split('_')

    # --- Special case: signal looks like  Function_TYPE  (only missing SYSTEM)
    # Criteria: exactly 2 parts, second is a known TYPE, first is CamelCase
    if len(raw_parts) == 2:
        f, t = raw_parts
        if _FUNCTION_RE.match(f) and t.upper() in KNOWN_TYPES:
            return f"??_{f}_{t.upper()}"

    # --- Special case: already has SYSTEM_Function_TYPE but SYSTEM is lowercase
    if len(raw_parts) == 3:
        s, f, t = raw_parts
        if _SYSTEM_RE.match(s.upper()) and _FUNCTION_RE.match(f) and t.upper() in KNOWN_TYPES:
            return f"{s.upper()}_{f}_{t.upper()}"

    # --- General case ---

    # Step 1: extract system (first meaningful token, letters only)
    system = _guess_system(raw_parts)

    # Step 2: extract type (right-most matching token)
    typ = _guess_type(raw_parts)

    # Step 3: look for a position in middle tokens
    pos = _guess_position(raw_parts)

    # Step 4: build function tokens (everything that's not system, type, position, or unit)
    func_tokens = []
    for t in raw_parts:
        u = t.upper()
        # Skip the token we chose as SYSTEM
        letters_only = re.sub(r'[^A-Za-z]', '', t).upper()
        if letters_only == system:
            continue
        # Skip position token
        if pos and u == pos:
            continue
        # Skip pure measurement/unit tokens
        if u in _MEAS_MAP:
            continue
        if u in KNOWN_TYPES:
            continue
        # Skip pure numeric tokens
        if re.match(r'^[\d_.]+$', t):
            continue
        # Strip model-number digits/underscores, keep letters
        clean = re.sub(r'[\d_.]+', '', t)
        if not clean:
            continue
        # Skip single-char remnants (model number letter suffixes like '424C' → 'C')
        if len(clean) <= 1:
            continue
        # Skip short unit abbreviations that leaked from measurement tokens
        if clean.lower() in _UNIT_SHORTS:
            continue
        # Skip tokens that are purely a voltage/current measurement pattern after stripping
        if re.match(r'^[0-9]*[mMuU]?[AVav]$', clean):
            continue
        func_tokens.append(clean)

    func = _to_camel(func_tokens) if func_tokens else 'Functn'
    # Cap function length to keep names reasonable
    if len(func) > 20:
        func = func[:20]

    if pos:
        return f"{system}_{func}_{pos}_{typ}"
    return f"{system}_{func}_{typ}"


# ---------------------------------------------------------------------------
# Architecture signal collector
# ---------------------------------------------------------------------------

def _collect_signals(arch: dict) -> list[tuple[str, str, str, str]]:
    """Collect (system, device, pin, signal_name) tuples from an architecture dict."""
    records: list[tuple[str, str, str, str]] = []

    # Systems → devices → pins
    for sys_data in arch.get('systems', []):
        if not isinstance(sys_data, dict):
            continue
        sys_name = str(sys_data.get('name', ''))
        for dev_data in sys_data.get('devices', []):
            if not isinstance(dev_data, dict):
                continue
            dev_name = str(dev_data.get('name', ''))
            for pin in dev_data.get('pins', []):
                if not isinstance(pin, dict):
                    continue
                sig = pin.get('signal', {})
                name = (sig.get('name', '') if isinstance(sig, dict)
                        else (sig if isinstance(sig, str) else ''))
                name = str(name).strip()
                if name and name not in ('', '-', 'N/A', 'NC', 'nc', 'none', 'None'):
                    pin_label = str(pin.get('name', pin.get('number', '')))
                    records.append((sys_name, dev_name, pin_label, name))

    # ECUs → pins
    for ecu_data in arch.get('ecus', []):
        if not isinstance(ecu_data, dict):
            continue
        ecu_name = str(ecu_data.get('name', ''))
        for pin in ecu_data.get('pins', []):
            if not isinstance(pin, dict):
                continue
            sig = pin.get('signal', {})
            name = (sig.get('name', '') if isinstance(sig, dict)
                    else (sig if isinstance(sig, str) else ''))
            name = str(name).strip()
            if name and name not in ('', '-', 'N/A', 'NC', 'nc', 'none', 'None'):
                pin_label = str(pin.get('name', pin.get('physical_number', '')))
                records.append(('ECU', ecu_name, pin_label, name))

    return records


# ---------------------------------------------------------------------------
# Public API — used by other report generators and run.sh
# ---------------------------------------------------------------------------

def validate_architecture(arch: dict, *, source: str = '', emit: bool = True) -> list[dict]:
    """Validate all signal names in *arch* against the naming convention.

    Returns a list of warning dicts (one per unique non-compliant signal):
      {signal, proposed, locations: [(system, device, pin), ...]}

    If *emit* is True, warnings are also printed to stderr.
    """
    records = _collect_signals(arch)

    # Group by signal name to collect locations and emit only ONE warning each
    from collections import defaultdict
    by_name: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for sys_name, dev_name, pin_label, sig_name in records:
        by_name[sig_name].append((sys_name, dev_name, pin_label))

    warnings: list[dict] = []
    for sig_name, locations in sorted(by_name.items()):
        if _is_exempt(sig_name):
            continue
        if _is_compliant(sig_name):
            continue
        proposed = propose_name(sig_name)
        warnings.append({
            'signal':   sig_name,
            'proposed': proposed,
            'locations': locations,
        })

    if emit and warnings:
        src = f" [{source}]" if source else ''
        print(f"\n[WARN] Signal naming convention violations{src} "
              f"({len(warnings)} signal(s)):", file=sys.stderr)
        for w in warnings:
            locs = ', '.join(
                f"{s}/{d}" for s, d, _ in w['locations'][:3]
            )
            if len(w['locations']) > 3:
                locs += f" +{len(w['locations'])-3} more"
            print(
                f"  CURRENT  : {w['signal']}\n"
                f"  PROPOSED : {w['proposed']}\n"
                f"  WHERE    : {locs}\n",
                file=sys.stderr,
            )

    return warnings


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse, json

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root', help='Workspace root (auto-detected if omitted)')
    p.add_argument('--input', help='Architecture JSON file (overrides auto-detection)')
    p.add_argument('--config', help='Path to eec_report_config.v4.json')
    p.add_argument('--fail-on-warn', action='store_true',
                   help='Exit with code 1 if any warnings are found (useful for CI)')
    args = p.parse_args()

    # Locate the architecture JSON
    try:
        from eec_report_common import resolve_root, load_config, first_existing, get_architecture, load_json
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from eec_report_common import resolve_root, load_config, first_existing, get_architecture, load_json

    root = resolve_root(args.root)
    cfg  = load_config(Path(args.config) if args.config else None)

    if args.input:
        arch_path = Path(args.input)
        if not arch_path.is_absolute():
            arch_path = root / arch_path
    else:
        arch_path = first_existing(root, cfg.get('architecture_json_candidates', []))
        if arch_path is None:
            print('[ERROR] No architecture JSON found. Pass --input or check config.', file=sys.stderr)
            return 2

    print(f'[INFO] Validating signal names in {arch_path.relative_to(root)}', file=sys.stderr)

    data = load_json(arch_path)
    arch = get_architecture(data)

    warnings = validate_architecture(arch, source=str(arch_path.name))

    total_signals: set[str] = set()
    for rec in _collect_signals(arch):
        total_signals.add(rec[3])

    compliant = len(total_signals) - len(warnings)
    exempt    = sum(1 for s in total_signals if _is_exempt(s))
    checked   = len(total_signals) - exempt

    print(
        f'\n[SUMMARY] {len(total_signals)} unique signal(s) total | '
        f'{exempt} exempt (infra) | '
        f'{checked} checked | '
        f'{compliant} compliant | '
        f'{len(warnings)} warning(s)',
        file=sys.stderr,
    )

    if not warnings:
        print('[OK] All signals comply with naming convention.', file=sys.stderr)
        return 0

    if args.fail_on_warn:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
