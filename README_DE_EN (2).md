# Standalone Prompts / Eigenständige Prompts

**Version:** 1.2.2
**Purpose / Zweck:** Every file in this directory is self-contained. It includes a universal deep-review core, one specialized profile, bilingual instructions, and profile references.

## Use / Verwendung

1. Choose the file matching the language or artifact you want to review.
2. Give that one file and the review target to an AI agent.
3. Fill in the `CONTEXT` / `KONTEXT` fields.
4. For multi-language repositories, use the main master prompt or provide multiple standalone files.

## File index / Dateiverzeichnis

| # | Deutsch | English | File | Integrated dependencies |
|---:|---|---|---|---|
| 1 | C | C | `01-c_DE_EN.md` | — |
| 2 | C++ | C++ | `02-cpp_DE_EN.md` | — |
| 3 | Rust | Rust | `03-rust_DE_EN.md` | — |
| 4 | Java | Java | `04-java_DE_EN.md` | — |
| 5 | Kotlin | Kotlin | `05-kotlin_DE_EN.md` | java |
| 6 | C# / .NET | C# / .NET | `06-csharp-dotnet_DE_EN.md` | — |
| 7 | F# | F# | `07-fsharp_DE_EN.md` | csharp-dotnet |
| 8 | JavaScript | JavaScript | `08-javascript_DE_EN.md` | — |
| 9 | TypeScript | TypeScript | `09-typescript_DE_EN.md` | javascript |
| 10 | Python | Python | `10-python_DE_EN.md` | — |
| 11 | Go | Go | `11-go_DE_EN.md` | — |
| 12 | PHP | PHP | `12-php_DE_EN.md` | — |
| 13 | Ruby / Rails | Ruby / Rails | `13-ruby-rails_DE_EN.md` | — |
| 14 | Swift / Objective-C | Swift / Objective-C | `14-swift-objective-c_DE_EN.md` | — |
| 15 | Dart / Flutter | Dart / Flutter | `15-dart-flutter_DE_EN.md` | — |
| 16 | Scala | Scala | `16-scala_DE_EN.md` | java |
| 17 | R | R | `17-r_DE_EN.md` | — |
| 18 | Julia | Julia | `18-julia_DE_EN.md` | — |
| 19 | Perl | Perl | `19-perl_DE_EN.md` | — |
| 20 | Lua | Lua | `20-lua_DE_EN.md` | — |
| 21 | Elixir / Erlang (BEAM) | Elixir / Erlang (BEAM) | `21-elixir-erlang-beam_DE_EN.md` | — |
| 22 | Haskell | Haskell | `22-haskell_DE_EN.md` | — |
| 23 | Bash / POSIX sh / zsh | Bash / POSIX sh / zsh | `23-shell-bash-posix-zsh_DE_EN.md` | — |
| 24 | PowerShell | PowerShell | `24-powershell_DE_EN.md` | — |
| 25 | SQL (alle Dialekte) | SQL (all dialects) | `25-sql_DE_EN.md` | — |
| 26 | HTML / CSS / Browser-Webartefakte | HTML / CSS / Browser Web Artifacts | `26-web-ui-html-css-browser_DE_EN.md` | — |
| 27 | JSON / YAML / XML / Konfigurationsdateien | JSON / YAML / XML / Configuration | `27-config-json-yaml-xml_DE_EN.md` | — |
| 28 | Docker / Containerfile | Docker / Containerfile | `28-docker-containerfile_DE_EN.md` | — |
| 29 | Kubernetes | Kubernetes | `29-kubernetes_DE_EN.md` | — |
| 30 | Terraform / OpenTofu | Terraform / OpenTofu | `30-terraform-opentofu_DE_EN.md` | — |
| 31 | Ansible | Ansible | `31-ansible_DE_EN.md` | — |
| 32 | Andere Sprache / Discovery | Other Language / Discovery | `32-other-language-discovery_DE_EN.md` | — |
| 33 | API (REST / GraphQL / gRPC / WebSocket) | API (REST / GraphQL / gRPC / WebSocket) | `33-api-rest-graphql-grpc-websocket_DE_EN.md` | — |
| 34 | NoSQL / Cache / Message Store | NoSQL / Cache / Message Store | `34-nosql-cache-message-store_DE_EN.md` | — |
| 35 | GitHub Actions / CI-CD / Release Automation | GitHub Actions / CI-CD / Release Automation | `35-github-actions-cicd_DE_EN.md` | — |
| 36 | Android | Android | `36-android_DE_EN.md` | kotlin, java |
| 37 | KI / LLM / Agent / RAG | AI / LLM / Agent / RAG | `37-ai-llm-agent-rag_DE_EN.md` | — |
| 38 | Ada / SPARK | Ada / SPARK | `38-ada-spark_DE_EN.md` | — |
| 39 | Fortran | Fortran | `39-fortran_DE_EN.md` | — |
| 40 | COBOL / Mainframe | COBOL / Mainframe | `40-cobol-mainframe_DE_EN.md` | — |
| 41 | Andere JVM-Sprachen (Groovy / Clojure) | Other JVM Languages (Groovy / Clojure) | `41-jvm-other-groovy-clojure_DE_EN.md` | java |

The machine-readable equivalent is `PROFILE_MANIFEST.json`. / Das maschinenlesbare Gegenstück ist `PROFILE_MANIFEST.json`.
