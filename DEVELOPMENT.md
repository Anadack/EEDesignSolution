# EE_Architect_Design — Development Setup Guide

This document covers how to set up a development environment for contributing to the EE_Architect_Design framework.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Environment Setup](#environment-setup)
3. [Building the Framework](#building-the-framework)
4. [Running Tests](#running-tests)
5. [Development Workflow](#development-workflow)
6. [Code Style & Standards](#code-style--standards)
7. [Contributing](#contributing)

---

## System Requirements

### **Linux/Unix (Recommended)**
- **OS**: Ubuntu 18.04+, Debian 10+, CentOS 7+, or equivalent
- **Compiler**: GCC 7.0+ or Clang 6.0+
- **Build Tools**:
  - `build-essential` (or equivalent)
  - `make` (optional, for convenience)
  - `git` (for version control)
- **Python**: 3.7+ (for documentation generators)
  - `python3-pip` (for package management)
- **Shell**: Bash 4.0+ (for `run.sh`)

### **Windows**
- **OS**: Windows 10+ or Windows Server 2016+
- **Compiler**: GCC (via MinGW or WSL2) or MSVC
- **Shell**: PowerShell 5.0+ (for `run.ps1`) or WSL2 bash
- **Python**: 3.7+ (for documentation generators)

### **macOS**
- **OS**: macOS 10.14+
- **Compiler**: Xcode Command Line Tools (GCC/Clang)
- **Python**: 3.7+
- **Shell**: Bash 4.0+

---

## Environment Setup

### **1. Clone the Repository**

```bash
git clone https://github.com/anadack/ee_architect_design.git
cd ee_architect_design
```

### **2. Install System Dependencies**

#### **Ubuntu/Debian**
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    python3 \
    python3-pip \
    python3-venv
```

#### **CentOS/RHEL**
```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    git \
    python3 \
    python3-devel \
    python3-pip
```

#### **macOS (with Homebrew)**
```bash
brew install gcc git python3
```

#### **Windows (WSL2 or MinGW)**
```powershell
# WSL2 (recommended)
wsl --install Ubuntu
# Then run Ubuntu/Debian commands above

# OR MinGW via Chocolatey
choco install gcc python3 git
```

### **3. Install Python Dependencies**

```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: Check if `requirements.txt` exists. If not, the framework has **zero external dependencies** beyond standard Python library.

### **4. Verify Installation**

```bash
# Check C compiler
gcc --version

# Check Python
python3 --version

# Check git
git --version
```

---

## Building the Framework

### **Quick Start (Automated)**

#### **Linux/Unix**
```bash
./run.sh
```

#### **Windows PowerShell**
```powershell
.\run.ps1
```

This executes the **7-step build pipeline**:
1. Clean previous builds
2. Compile C framework (gcc)
3. Run the application
4. Validate architecture
5. Generate reports (73 Python generators)
6. Create console bundle
7. Display summary

### **Step-by-Step (Manual)**

#### **1. Compile the C Framework**

```bash
gcc -Wall -Wextra -O2 -std=c11 \
    -Iinc \
    src/*.c -o app -lm
```

**Flags explained**:
- `-Wall -Wextra`: Show all warnings
- `-O2`: Optimization level 2
- `-std=c11`: C11 standard
- `-Iinc`: Include directory
- `-lm`: Link math library
- `-o app`: Output executable name

#### **2. Run the Application**

```bash
./app
```

Or with arguments:
```bash
./app --root . --input examples/tractor_base.json --outdir generated_doc/exports
```

**Common arguments**:
- `--root .`: Working directory (for library discovery)
- `--input FILE.json`: Architecture JSON to process
- `--outdir PATH`: Output directory for reports
- `--config JSON`: Configuration overrides

#### **3. Generate Documentation**

```bash
python3 tools/scripts/generate_all_architecture_docs.py --root .
```

This runs all **73 generators** in sequence to produce:
- HTML diagrams (dataflow, network, pinout)
- CSV exports (signals, communications, wiring)
- JSON reports (architecture, validation, estimation)
- Interactive viewers (architecture console, configuration validator)

---

## Running Tests

### **Unit Tests**

```bash
cd qa
./run_tests.sh
```

**Test files**:
- `test_library_import_export.c` — Validates sensor/actuator JSON round-trip
- `test_es3_ecu_import.c` — Tests ECU pinout import and generation

**Expected output**:
```
[TEST] library_import_export ... PASS
[TEST] es3_ecu_import ... PASS
```

### **Integration Tests**

```bash
# Full architecture validation
./app --root . --input generated_doc/exports/exported_architecture.json

# Check verify report
cat generated_doc/exports/verify_report.txt
```

**Expected**: 0 critical errors (warnings are OK for reference data)

### **Architecture Validation**

Run **21 verification rules** (V1-V13, B1-B8):

```bash
python3 tools/scripts/verify_architecture.py \
    --input generated_doc/exports/exported_architecture.json \
    --detailed
```

---

## Development Workflow

### **1. Create a Feature Branch**

```bash
git checkout -b feature/your-feature-name
```

**Branch naming**: `feature/`, `bugfix/`, `docs/`, `refactor/`

### **2. Make Changes**

#### **For C code** (`src/*.c`, `inc/*.h`):
- Follow K&R style with 2-space indentation
- Add Doxygen comments for public functions
- Use `uint32_t`, `bool`, enums (no magic numbers)
- Test with `gcc -Wall -Wextra` (zero warnings required)

#### **For Python generators** (`tools/scripts/*.py`):
- Import from `eec_archdoc_common` for shared utilities
- Use `pathlib.Path` (not `os.path`)
- Add error handling with try/except
- Log progress with `print(f"[GENERATOR_NAME] ...")`
- Register in `generate_all_architecture_docs.py`

#### **For documentation** (`.md` files):
- Use Markdown with syntax highlighting for code blocks
- Keep line width ≤ 100 characters
- Include examples and use cases

### **3. Test Your Changes**

```bash
# Rebuild
./run.sh --skip-build false

# Run specific generator test
python3 tools/scripts/generate_signal_dictionary_html.py --root .

# Validate output
ls -lh generated_doc/architecture_html/signal_dictionary.html
```

### **4. Commit with Clear Messages**

```bash
git add .
git commit -m "Add feature: descriptive title

Longer explanation of what changed and why.
Include any breaking changes or important notes.

Fixes #123 (if applicable)"
```

### **5. Push and Create Pull Request**

```bash
git push -u origin feature/your-feature-name
```

Then open a PR on GitHub with:
- **Title**: One-line summary
- **Description**: What changed and why
- **Testing**: How to verify the change

---

## Code Style & Standards

### **C Code Standards**

**Naming**:
```c
// Types: PascalCase with _t suffix
typedef struct EEC_Signal_s {
    uint32_t id;           // Variables: snake_case
    bool is_mapped;        // Booleans: is_/has_ prefix
} EEC_Signal_t;

// Constants: UPPER_SNAKE_CASE
#define EEC_ECU_MAX_CAN_ADDRESSES 10U
```

**Comments**:
```c
/**
 * @brief Short description of function.
 * @param param1 Description of parameter 1.
 * @return Description of return value.
 */
int EEC_Signal_Validate(const EEC_Signal_t *signal);

// Inline comments explain WHY, not WHAT
if (signal->is_mapped) {
    // Only ground pins can accept multiple connections (star topology)
    count++;
}
```

**Error Handling**:
```c
// Check allocations
EEC_Signal_t *sig = malloc(sizeof(EEC_Signal_t));
if (!sig) {
    fprintf(stderr, "Error: allocation failed\n");
    return NULL;
}

// Return NULL or error code, never assert in library code
if (count > MAX_LIMIT) {
    return -1;  // Or: return NULL;
}
```

### **Python Code Standards**

**Style**: PEP 8 with 4-space indentation

```python
# Imports: standard library, then third-party, then local
import json
from pathlib import Path
from eec_archdoc_common import html_page, kpi_row

# Functions: snake_case
def extract_signals_from_architecture(arch: dict) -> list[dict]:
    """Extract signal list from architecture JSON.
    
    Args:
        arch: Architecture dictionary.
    
    Returns:
        List of signal dictionaries.
    """
    signals = []
    for sig in arch.get('signals', []):
        signals.append({
            'id': sig.get('id'),
            'name': sig.get('name'),
        })
    return signals

# Error handling: log and continue
try:
    result = process_data(arch)
except KeyError as e:
    print(f"[WARN] Missing field: {e}")
    result = default_value
```

### **Documentation Standards**

- **README.md**: Overview, quick start, directory structure
- **DESIGN_SYSTEM.md**: UI/UX guidelines, CSS variables, customization
- **DEVELOPMENT.md** (this file): Setup, testing, contributing
- **Code comments**: Explain WHY, not WHAT
- **Examples**: Real use cases with input/output

---

## Contributing

### **Before Contributing**

1. **Check existing issues** — Avoid duplicate work
2. **Read DESIGN_SYSTEM.md** — Understand design philosophy
3. **Review README.md** — Get familiar with architecture
4. **Run tests** — Ensure your environment works

### **Contribution Types**

#### **Bug Fixes**
- Reference the issue number: `Fixes #123`
- Include before/after behavior
- Add test case if applicable

#### **New Generators**
- Follow `tools/scripts/generate_*.py` pattern
- Use `eec_archdoc_common` for shared utilities
- Register in `generate_all_architecture_docs.py`
- Add entry to DOCS list in `generate_full_architecture_documentation_index.py`
- Document what it generates in comments

#### **C Framework Extensions**
- Add public API in `inc/EEC_*.h` with Doxygen comments
- Implement in `src/EEC_*.c`
- Add validation rule if needed (V14+, B9+)
- Test with `qa/test_*.c`

#### **Documentation**
- Update README.md for user-facing changes
- Update DEVELOPMENT.md for internal changes
- Add examples for new features

### **Code Review Checklist**

Before submitting a PR, verify:

- [ ] Code compiles with `gcc -Wall -Wextra` (zero warnings)
- [ ] All tests pass: `qa/run_tests.sh`
- [ ] Python generators execute without errors
- [ ] Generated HTML/CSV output is valid
- [ ] Comments explain WHY, not WHAT
- [ ] No hardcoded architecture-specific values
- [ ] Git history is clean (atomic commits)

---

## Troubleshooting

### **"gcc: command not found"**
```bash
# Install build tools
sudo apt-get install build-essential  # Debian/Ubuntu
brew install gcc                      # macOS
```

### **"Python version too old"**
```bash
python3 --version
# Update if < 3.7
python3.11 -m pip install --upgrade pip
```

### **"Generated HTML is blank"**
- Serve via HTTP server: `python3 -m http.server 8000`
- Open in browser: `http://localhost:8000/generated_doc/...html`
- Check browser console for JavaScript errors

### **Tests fail with "library not found"**
```bash
# Ensure library path is correct
ls -la library/systems/
ls -la library/sensors/
ls -la library/actuators/
```

---

## Getting Help

- **Documentation**: Read `README.md`, `DESIGN_SYSTEM.md`
- **Examples**: Check `library/systems/` and `examples/`
- **Issues**: GitHub issue tracker
- **Discussions**: GitHub discussions board

---

## Quick Reference

| Task | Command |
|------|---------|
| **Build** | `./run.sh` |
| **Build (skip run)** | `./run.sh --skip-run` |
| **Run tests** | `cd qa && ./run_tests.sh` |
| **Generate docs** | `python3 tools/scripts/generate_all_architecture_docs.py --root .` |
| **Validate architecture** | `./app --root .` |
| **Start feature branch** | `git checkout -b feature/name` |
| **Commit** | `git commit -m "Descriptive message"` |
| **Push** | `git push -u origin feature/name` |

---

**Last Updated**: June 29, 2026  
**Maintainer**: Anadack Temtching Dassi  
**License**: See LICENSE file
