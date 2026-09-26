# OpenCLI ⚡

> **A lightweight, single-file command-line toolkit for everyday computing.**

OpenCLI is a fast, dependency-light interactive CLI written in Python. It brings common system, development, productivity, networking, web, and utility tasks into one consistent terminal interface.

No giant framework.
No bloated GUI.
No 15 different tools for shit you can handle with one command.

Just **OpenCLI**.

---

## ✨ Features

### 🖥️ System Monitoring

Inspect your machine directly from the terminal:

* System overview
* CPU usage
* Per-core CPU usage
* CPU frequency
* RAM usage
* Swap usage
* Disk usage
* Network interfaces
* Running processes
* Temperature sensors
* System uptime
* Hostname
* OS and architecture information

Examples:

```bash
system
system cpu
system memory
system disk
system network
system processes
system live
```

---

### 🧮 Calculator

OpenCLI includes a safe expression evaluator based on Python's AST rather than blindly executing arbitrary Python code.

Supports:

* `+`
* `-`
* `*`
* `/`
* `//`
* `%`
* `**`
* Unary `+` / `-`
* `sqrt`
* `sin`
* `cos`
* `tan`
* `log`
* `log2`
* `log10`
* `exp`
* `floor`
* `ceil`
* `min`
* `max`
* `abs`
* `round`
* `pi`
* `e`
* `tau`

```bash
calc 2 + 2
calc sqrt(144)
calc 2**10
calc sin(pi/2)
calc log10(1000)
```

---

### 📁 File Search

Search directories without having to remember complicated `find` syntax.

Supports:

* Case-sensitive or insensitive searches
* Glob patterns
* Maximum result limits
* Maximum search depth
* Automatic skipping of common junk directories

Commonly skipped directories include:

```text
.git
node_modules
__pycache__
.venv
venv
.mypy_cache
.pytest_cache
.tox
```

Example:

```bash
find "*.py"
find README
find config --depth 2
```

---

### 🌐 Web Search

Search the web directly from your terminal through DuckDuckGo.

```bash
search "Python decorators"
search "Arch Linux package management"
```

OpenCLI returns titles, snippets, and URLs.

---

### 📚 Wikipedia

Look up Wikipedia articles directly from the terminal.

```bash
wiki Python
wiki Linux
wiki Alan Turing
```

OpenCLI automatically searches Wikipedia when an exact article title isn't found.

---

### 🌍 Browser Launcher

Open websites directly in your default browser.

```bash
open example.com
open https://github.com
```

URLs without a protocol automatically receive `https://`.

---

### 📝 Notes

Keep lightweight persistent notes using SQLite.

```bash
note add "Finish networking project"
note list
note remove 3
note clear
```

Notes contain:

* ID
* Text
* Creation timestamp

---

### ✅ Todo List

Built-in persistent todo management.

```bash
todo add "Finish README"
todo list
todo done 1
todo undone 1
todo remove 1
todo clear-done
```

Todos track:

* ID
* Description
* Completion state
* Creation timestamp
* Completion timestamp

---

### 🔧 Git Helpers

Quick Git repository information without leaving OpenCLI.

```bash
git status
git branches
git log
git log --limit 20
```

Current functionality:

| Command        | Purpose                  |
| -------------- | ------------------------ |
| `git status`   | Show working tree status |
| `git branches` | List branches            |
| `git log`      | Show recent commits      |

OpenCLI automatically checks whether Git is installed and whether the current directory is actually a Git repository.

---

### 📦 Project Discovery

Find development projects under configured project roots.

OpenCLI recognizes projects using common project markers such as:

```text
.git
pyproject.toml
setup.py
package.json
Cargo.toml
go.mod
pom.xml
build.gradle
Gemfile
composer.json
CMakeLists.txt
```

Run:

```bash
projects
projects --depth 5
```

Example output:

```text
Name        Type             Path
----------  ---------------  ------------------------
OpenCLI     python           /home/user/OpenCLI
Website     node             /home/user/projects/site
Engine      rust             /home/user/projects/engine
```

---

### ⚙️ Configuration

OpenCLI stores configuration separately from the source code.

View everything:

```bash
config show
```

Get one value:

```bash
config get history_size
```

Change a value:

```bash
config set history_size 2000
```

Default configuration includes:

```text
default_search_dir = ~
max_search_results = 20
history_size = 1000
```

Project roots can also be configured through the configuration's `project_roots` value.

Secrets are deliberately rejected by the configuration system rather than being stored as normal configuration values.

---

### 🌦️ Weather

Get current weather information through `wttr.in`.

```bash
weather
weather Bengaluru
weather London
weather Tokyo
```

---

### 🌐 Network Utilities

OpenCLI includes small networking utilities.

#### Public IP information

```bash
net ip
```

Displays information such as:

* Public IP
* City
* Region
* Country
* Organization

#### DNS lookup

```bash
net dns example.com
```

Example:

```text
example.com -> 93.184.216.34
```

---

### 🔌 HTTP Client

Make quick HTTP GET requests from the terminal.

```bash
http get https://example.com
```

If the response contains JSON, OpenCLI pretty-prints it.

Otherwise, it displays a limited portion of the response body.

---

### 🔐 Hashing

Calculate hashes from either text or files.

Supported algorithms:

```text
MD5
SHA-256
```

Examples:

```bash
hash md5 "hello world"
hash sha256 "hello world"
hash sha256 ./file.txt
```

If the supplied target is a file, OpenCLI hashes the file contents.

---

### 🔤 Text Utilities

OpenCLI contains lightweight text-processing utilities.

These are intended for quick terminal operations rather than replacing a full text-processing environment.

---

### ⏱️ Timer & Stopwatch

Useful timing utilities are available directly inside OpenCLI.

```bash
timer
stopwatch
```

These provide simple terminal-based timing functionality without needing another application.

---

### 🧹 Terminal Utilities

Clear the terminal:

```bash
clear
```

Exit OpenCLI:

```bash
exit
```

Get general help:

```bash
help
```

Get help for a specific command:

```bash
help system
help calc
help git
help config
```

---

# 🚀 Installation

## Requirements

OpenCLI requires:

* **Python 3.10+**
* `psutil`
* `requests`

The original application checks for these dependencies at startup.

Install them with:

```bash
pip install psutil requests
```

Or:

```bash
python -m pip install psutil requests
```

---

## 📥 Running OpenCLI

Clone/download the project and run:

```bash
python opencli.py
```

You can also execute individual commands directly:

```bash
python opencli.py help
python opencli.py calc "2 + 2"
python opencli.py system memory
```

The application is designed as a **single Python file**, making it easy to move between machines without managing a complicated project structure.

---

# 🖥️ Interactive Mode

Launch OpenCLI without arguments:

```bash
python opencli.py
```

You'll enter the interactive shell.

From there:

```text
> help
> system
> calc sqrt(256)
> projects
> git status
> todo list
> exit
```

Commands use a consistent syntax and support quoted arguments.

For example:

```bash
calc "sqrt(144) + 10"
search "how does TCP work"
note add "Remember to push changes"
```

---

# 📖 Command Reference

| Command     | Description                       |
| ----------- | --------------------------------- |
| `help`      | Show OpenCLI help                 |
| `system`    | System information and monitoring |
| `find`      | Search for files/directories      |
| `search`    | Web search                        |
| `wiki`      | Wikipedia lookup                  |
| `open`      | Open a URL in the browser         |
| `note`      | Persistent notes                  |
| `todo`      | Persistent todo list              |
| `calc`      | Mathematical calculator           |
| `projects`  | Discover development projects     |
| `git`       | Git repository helpers            |
| `config`    | Configuration management          |
| `weather`   | Current weather                   |
| `net`       | Network utilities                 |
| `http`      | HTTP GET client                   |
| `hash`      | Hash text/files                   |
| `text`      | Text utilities                    |
| `timer`     | Timer                             |
| `stopwatch` | Stopwatch                         |
| `clear`     | Clear terminal                    |

---

# 🧩 Command Tree

```text
OpenCLI
│
├── help
│
├── system
│   ├── live
│   ├── memory
│   ├── cpu
│   ├── disk
│   ├── network
│   └── processes
│
├── find
├── search
├── wiki
├── open
│
├── note
│   ├── add
│   ├── list
│   ├── remove
│   └── clear
│
├── todo
│   ├── add
│   ├── list
│   ├── done
│   ├── undone
│   ├── remove
│   └── clear-done
│
├── calc
├── projects
│
├── git
│   ├── status
│   ├── branches
│   └── log
│
├── config
│   ├── show
│   ├── get
│   └── set
│
├── weather
│
├── net
│   ├── ip
│   └── dns
│
├── http
│   └── get
│
├── hash
│   ├── md5
│   └── sha256
│
├── text
│   ├── b64enc
│   ├── b64dec
│   └── json
│
├── timer
├── stopwatch
└── clear
```

---

# 🎨 Terminal UI

OpenCLI provides a lightweight terminal interface with:

* ANSI colors
* Bold headers
* Progress bars
* Tables
* Terminal-width awareness
* Cursor control
* Windows ANSI support
* Automatic color detection

The color system uses a small predefined palette and automatically disables colors when the terminal doesn't support them.

You can also force or disable color behavior through environment variables:

```bash
FORCE_COLOR=1
NO_COLOR=1
```

---

# 💾 Data & Configuration

OpenCLI keeps persistent application data outside the source file.

On Linux/macOS-style systems, configuration defaults to:

```text
~/.config/opencli/
```

Data defaults to:

```text
~/.local/share/opencli/
```

On Windows, OpenCLI uses the appropriate `APPDATA` / `LOCALAPPDATA` locations.

Persistent data includes things such as:

* Configuration
* Command history
* Notes
* Todos
* SQLite database data

---

# 🏗️ Architecture

Despite being a single file, OpenCLI is organized into several logical layers.

```text
┌───────────────────────────────┐
│          Interactive UI       │
├───────────────────────────────┤
│       Command / Router        │
├───────────────────────────────┤
│           Services            │
│                               │
│ System │ Files │ Search       │
│ Wiki   │ Git   │ Projects     │
│ Notes  │ Todos │ Network      │
├───────────────────────────────┤
│       Persistence Layer       │
│          SQLite / JSON        │
├───────────────────────────────┤
│         Python Runtime        │
└───────────────────────────────┘
```

### Command system

Commands are represented through structured objects:

```text
Command
├── name
├── description
├── arguments
├── options
├── aliases
└── subcommands
```

Subcommands use the same structured approach.

This makes adding new commands significantly cleaner than putting everything inside one enormous `if/elif` block.

---

# 🔒 Safety

OpenCLI intentionally avoids executing arbitrary Python expressions for the calculator.

The calculator parses expressions with Python's AST module and evaluates only explicitly permitted:

* Operators
* Functions
* Constants

Large exponents are also restricted.

This means:

```bash
calc 2 + 2
```

is fine, while arbitrary Python code is not treated as a valid calculator expression.

---

# 🌐 External Services

Some OpenCLI features require an internet connection.

| Feature     | External service              |
| ----------- | ----------------------------- |
| Web search  | DuckDuckGo Instant Answer API |
| Wikipedia   | Wikipedia API                 |
| Weather     | wttr.in                       |
| Public IP   | ipinfo.io                     |
| HTTP client | Target URL                    |

Offline functionality such as local calculations, notes, todos, system information, file searching, Git inspection, hashing, and project discovery does not inherently require these web services.

---

# 🛠️ Development

The project intentionally keeps its runtime architecture simple.

There are no mandatory heavyweight frameworks.

Core Python modules handle:

* Parsing
* Filesystem operations
* SQLite
* Git subprocesses
* Hashing
* Networking
* Browser launching
* JSON
* Terminal interaction

External Python dependencies are limited to:

```text
psutil
requests
```

---

## Adding a Command

Commands follow the existing `Command` / `Subcommand` architecture.

A command generally consists of:

1. A handler function
2. A `Command` definition
3. Optional arguments/options
4. Registration in the command registry

This keeps command behavior separated from routing and argument parsing.

---

# 🐛 Troubleshooting

### `psutil is required`

Install the dependency:

```bash
python -m pip install psutil
```

### `requests is required`

Install:

```bash
python -m pip install requests
```

### Git commands fail

Make sure Git is installed and available on `PATH`:

```bash
git --version
```

Also make sure you're running the command inside a Git repository:

```bash
git status
```

### Network commands fail

Check your internet connection. Services such as weather, web search, Wikipedia, and public-IP lookup require network access.

### Colors don't appear

OpenCLI automatically detects whether the terminal supports color.

You can force colors:

```bash
FORCE_COLOR=1
```

Or disable them:

```bash
NO_COLOR=1
```

---

# 🗺️ Roadmap

Potential future improvements:

* [ ] More system-monitoring modules
* [ ] More file-management commands
* [ ] Richer Git operations
* [ ] Better terminal autocomplete
* [ ] Command aliases
* [ ] Plugin system
* [ ] Configurable themes
* [ ] Better interactive menus
* [ ] More networking utilities
* [ ] More developer tooling
* [ ] Optional AI integration
* [ ] Shell integration
* [ ] Cross-platform packaging
* [ ] Standalone executable builds

---

# 🤝 Contributing

Contributions are welcome.

Before adding a feature, keep the project's core philosophy in mind:

> **Useful functionality without unnecessary complexity.**

Prefer:

* Small focused functions
* Standard-library solutions where practical
* Clear command interfaces
* Explicit error handling
* Minimal dependencies
* Cross-platform behavior
* Readable terminal output

Avoid turning OpenCLI into a giant framework just because it can be done.

---

# 📄 License

Add your project's license here.

For example:

```text
MIT License
```

or include a separate `LICENSE` file in the repository.

---

# ⚡ Quick Start

```bash
# Install dependencies
python -m pip install psutil requests

# Start OpenCLI
python opencli.py

# Inside OpenCLI
help
system
system memory
calc sqrt(144)
find "*.py"
projects
git status
todo add "Build something cool"
todo list
weather Bengaluru
net dns github.com
hash sha256 README.md
exit
```

---

## OpenCLI

**One terminal. One tool. Less bullshit.**

```text
┌──────────────────────────────────────────┐
│              O P E N C L I               │
│                                          │
│  system · files · web · git · network    │
│  notes · todos · calculator · utilities  │
│                                          │
│              Stay in the shell.          │
└──────────────────────────────────────────┘
```
