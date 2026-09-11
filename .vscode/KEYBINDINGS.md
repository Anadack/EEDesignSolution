# VS Code Keybindings

## Default Keybindings for This Workspace

To bind the release packaging task to **Ctrl+Shift+R**, add this to your VS Code **user settings** (`~/.config/Code/User/keybindings.json` on Linux/Mac, or `%APPDATA%\Code\User\keybindings.json` on Windows):

```json
{
  "key": "ctrl+shift+r",
  "command": "workbench.action.tasks.runTask",
  "args": "📦 Package Release  [Ctrl+Shift+R]"
}
```

### How to add it:

1. Open VS Code **Command Palette** → `Ctrl+K Ctrl+P` (or `Cmd+K Cmd+P` on Mac)
2. Type **"Open Keyboard Shortcuts (JSON)"** → select it
3. Paste the JSON above into the file
4. Save

### Pre-configured shortcuts:

| Shortcut | Task | What it does |
|---|---|---|
| **Ctrl+Shift+B** | 🚀 Run Full Pipeline | Compile C → run app → generate all docs (already default in VS Code) |
| **Ctrl+Shift+R** | 📦 Package Release | Bundle generated_doc/ into releases/ zip with manifest (add keybinding above) |

### Other tasks available (via Ctrl+Shift+P → "Tasks: Run Task"):

- 📄 Reports only (skip build + run)
- ⚙️ Compile + export only (skip reports)
- 🧹 Clean (remove app + generated files)
- 🧾 Validate ECU JSONs
- 🧪 Run ECU JSON tests
- ✅ CI: Validate + Test
