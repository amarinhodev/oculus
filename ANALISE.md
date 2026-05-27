---
title: OCULUS — Análise Técnica Completa
type: analysis-report
status: concluída
tags: [oculus, análise, python, google-meet, transcrição, gemini, obsidian, itops]
created: 2026-05-27
updated: 2026-05-27
---

# 🔭 O.C.U.L.U.S. — Relatório de Análise Técnica

> **Repositório:** https://github.com/andersonsilvaviva/oculus  
> **Analisado por:** Agente CLAW  
> **Data:** 2026-05-27  

---

## 📋 Descrição

**O.C.U.L.U.S.** (Omniscient Captions Universal Logging & Understanding System) é uma ferramenta de automação para captura, processamento e análise inteligente de transcrições de reuniões do Google Meet.

### Fluxo completo:
1. **Captura** — Extensão [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) captura legendas e chat em tempo real durante a reunião.
2. **Exportação** — Ao encerrar a reunião, a extensão salva o transcript como `.txt` em `~/Downloads/TranscripTonic/`.
3. **Monitoramento** — `watcher.py` detecta o novo arquivo via polling a cada 5 segundos.
4. **Processamento** — `processor.py` converte o `.txt` bruto em Markdown organizado (por falante + timestamp).
5. **Inteligência** — Após conversão, `watcher.py` aciona o Gemini CLI com a skill `oculus-analyzer` para análise semântica, extração de tasks/decisões e integração com o vault Obsidian.
6. **Organização** — Os arquivos Markdown são salvos em `Captions/` e integrados ao Obsidian Daily Log.

### Casos de uso:
- Registrar automaticamente reuniões de equipe (Daily ITOps, Weekly Infra Core, FUP Joca GenIA)
- Extrair tasks e decisões sem intervenção manual
- Integrar meetingnotes ao vault Obsidian do Anderson
- Suporte multilíngue (Português, Inglês, Espanhol)

---

## 🏗️ Arquitetura

```
oculus/
├── watcher.py               # Serviço de monitoramento (polling 5s) + orquestrador de análise
├── processor.py             # Parser do formato TranscripTonic → Markdown estruturado
├── config.example.py        # Template de configuração (usuário copia para config.py)
├── config.py                # [git-ignored] Configuração real com paths e credenciais locais
├── requirements.txt         # Dependências Python (apenas pyyaml)
├── .gitignore               # Protege config.py, env.yaml, *.pem, Captions/, logs
├── README.md                # Documentação completa
├── Captions/                # [git-ignored] Transcrições convertidas em Markdown
└── skills/
    └── oculus-analyzer/
        └── SKILL.md         # Skill para Gemini CLI (V8 - Fully Autonomous)
```

### Padrão arquitetural:
- **Pipeline linear**: Captura → Watch → Process → Analyze → Store
- **Desacoplamento parcial**: watcher e processor são separados (processor.py pode rodar standalone)
- **Configuração externalizada**: `config.py` (git-ignored) centraliza todos os paths
- **Extensão via skill**: A inteligência fica em `skills/oculus-analyzer/SKILL.md`, executada pelo Gemini CLI

### Componentes por responsabilidade:

| Componente | Responsabilidade |
|---|---|
| `watcher.py` | Monitoramento de diretório, orquestração, trigger de IA |
| `processor.py` | Parsing e estruturação do transcript bruto |
| `config.example.py` | Template de configuração (paths, identidade, idioma) |
| `skills/oculus-analyzer/SKILL.md` | Definição de comportamento do agente IA (Gemini) |

---

## 🛠️ Stack

| Categoria | Tecnologia | Versão/Obs |
|---|---|---|
| **Linguagem** | Python | 3.11+ |
| **Dependência Python** | `pyyaml` | Única dependência listada |
| **IA / LLM** | Gemini CLI | Google (externo) |
| **Extensão Browser** | TranscripTonic | Chrome Extension |
| **Knowledge Base** | Obsidian | Vault local |
| **Módulos stdlib** | `os`, `re`, `shutil`, `datetime`, `time`, `subprocess` | Sem deps extras |
| **Skill engine** | Gemini CLI + obsidian extension | `gemini-obsidian` |

### Observação sobre dependências:
O arquivo `requirements.txt` lista apenas `pyyaml`, porém o módulo `pyyaml` **não é importado em nenhum arquivo de código do repositório**. Isso indica que ou era usado em versão anterior ou está reservado para uso futuro (ex: leitura de `env.yaml`). As dependências reais do runtime são apenas stdlib.

---

## ✅ Pontos Positivos

1. **Propósito bem definido e focado** — O projeto resolve um problema real e específico (automação de meeting notes) sem scope creep.

2. **Separação clara de responsabilidades** — `watcher.py` orquestra, `processor.py` parseia, `config.py` centraliza configurações. Boa divisão.

3. **Configuração externalizada corretamente** — `config.py` é git-ignored e o repositório fornece `config.example.py` como template. Boa prática de segurança.

4. **Lógica de parsing robusta** — O `merge_fragments()` resolve o problema de fragmentos incrementais do TranscripTonic (que envia atualizações parciais da mesma fala). A regex de detecção de speaker é precisa.

5. **Nomenclatura de arquivos inteligente** — O padrão `YYYY-MM-DD_HH-MM_Title.md` facilita ordenação cronológica e integração com Obsidian.

6. **Suporte multilíngue** — `PREFERRED_LANGUAGE` em config permite gerar notas em PT/EN/ES, adequado para times internacionais.

7. **Skill FULLY AUTONOMOUS (V8)** — A skill do Gemini CLI é projetada para operar sem interação com o usuário, tomando decisões de onde salvar notas automaticamente. Muito adequado para background automation.

8. **Gitignore bem estruturado** — Protege `Captions/`, `config.py`, `env.yaml`, `*.pem`, logs. Sem risco de vazar dados sensíveis.

9. **Processamento em batch no startup** — O `run_batch_process()` processa arquivos pendentes na inicialização do watcher, evitando perda de transcrições caso o serviço esteja offline durante a reunião.

---

## ⚠️ Pontos de Melhoria

### 🔴 Alta Prioridade

1. **Sem tratamento de erros (try/except)** em `watcher.py` e `processor.py`:
   - `get_files()`: se `SOURCE_DIR` não existir e `os.makedirs()` falhar, o watcher quebra silenciosamente.
   - `processor.py`: parsing de datas tem apenas um `except: pass` genérico — engole qualquer erro sem log.
   - `analyze_file()`: `subprocess.Popen` sem captura de erros de inicialização (ex: `gemini` não instalado).

2. **Dependência oculta não documentada** — O sistema depende do Gemini CLI (`gemini` no PATH), mas isso não está no `requirements.txt` nem há verificação se o binário existe antes de chamar.

3. **Polling sem `watchdog`** — Usar `time.sleep(5)` + `os.listdir()` é ineficiente e cria latência de até 5 segundos. A biblioteca `watchdog` oferece eventos de filesystem em tempo real e é padrão para esse tipo de watcher. Não está nem no `requirements.txt`.

4. **Sem logging estruturado** — O código usa `print()` diretamente em vez de `logging` com níveis (DEBUG/INFO/WARNING/ERROR). Isso dificulta operação em produção/daemon mode.

### 🟡 Média Prioridade

5. **`pyyaml` listado mas não utilizado** — `requirements.txt` lista `pyyaml` mas nenhum arquivo importa `yaml`. Indica dead code ou arquivo desatualizado.

6. **Sem testes automatizados** — Não há `tests/` nem arquivos `test_*.py`. Funções como `merge_fragments()` e `process_section()` são ideais para unit tests (lógica determinística + casos edge).

7. **Sem mecanismo de retry para análise Gemini** — Se o `gemini` CLI falhar, não há retry. O log é append-only mas não há monitoramento de falhas.

8. **Hardcode de string "Google Meet transcript"** — O filtro de arquivos (`f.startswith("Google Meet transcript")`) é hardcodado em dois lugares (`watcher.py` e `processor.py`). Deveria ser uma constante em `config.py`.

9. **Parser frágil para nomes de arquivo** — O parsing de `fn_parts[1].split(" at ")` pode falhar se o nome da reunião contiver " at " (ex: "Reunião at Scale at 07-04-2026...").

10. **Sem suporte a múltiplos usuários** — `USER_NAME` é um único string. Em reuniões onde o usuário usa diferentes perfis/dispositivos, pode não ser detectado corretamente.

### 🟢 Baixa Prioridade

11. **Sem arquivo `setup.py` ou `pyproject.toml`** — O projeto poderia ser empacotado como CLI instalável (`pip install oculus`), mas não há estrutura de packaging.

12. **Sem systemd service file** — Para rodar o watcher como daemon em Linux (SP-Ubuntu), seria útil um `.service` file ou `Makefile` com targets de `start`/`stop`.

13. **README em inglês, projeto de time BR** — Para adoção pelo time ITOps da OLX Brasil, um README em PT-BR facilitaria onboarding.

---

## 🔴 Alertas de Segurança

### ✅ O que está bem protegido:
- `config.py` está no `.gitignore` — **credenciais locais não vazam para o repo**
- `env.yaml` está no `.gitignore`
- `*.pem` está no `.gitignore`
- Não há hardcode de tokens, keys ou passwords no código commitado

### ⚠️ Pontos de atenção:

1. **Logs de análise sem rotação** — `config.LOG_ANALYSIS` é um arquivo que só cresce (`open(..., 'a')`). Em produção, logs do Gemini podem conter conteúdo sensível de reuniões. Sem rotação, crescimento ilimitado e sem controle de acesso.

2. **Transcrições em texto plano em `Captions/`** — Os arquivos `.md` gerados contêm o conteúdo completo das reuniões. O diretório é local e git-ignored, mas não há criptografia ou controle de acesso.

3. **Gemini CLI recebe path completo do arquivo** — O prompt enviado ao Gemini inclui o path absoluto do arquivo de transcrição. Dependendo da configuração do Gemini CLI, isso pode ser logado remotamente.

4. **`subprocess.Popen` sem validação de input** — O `md_path` passado para `analyze_file()` vem de `os.listdir()` controlado, mas não há sanitização antes de injetar no prompt do Gemini. Risco baixo, mas existe.

---

## 📊 Avaliação Geral

| Dimensão | Nota | Obs |
|---|---|---|
| **Propósito/Clareza** | ⭐⭐⭐⭐⭐ | Muito bem definido |
| **Arquitetura** | ⭐⭐⭐⭐ | Boa separação, mas acoplamento com Gemini CLI |
| **Qualidade do Código** | ⭐⭐⭐ | Funcional, mas sem tratamento de erros adequado |
| **Segurança** | ⭐⭐⭐⭐ | Config bem protegida, mas logs sem rotação |
| **Testabilidade** | ⭐⭐ | Zero testes automatizados |
| **Manutenibilidade** | ⭐⭐⭐ | Simples de entender, difícil de monitorar em produção |
| **Documentação** | ⭐⭐⭐⭐⭐ | README excelente, SKILL.md detalhado |

**Avaliação geral: 3.5/5** — Projeto funcional e bem documentado para uso pessoal/experimental. Para adoção em produção no time ITOps, requer melhorias em tratamento de erros, logging estruturado e testes.

---

## 🚀 Próximos Passos Sugeridos

1. **Quick wins (< 1h cada):**
   - Adicionar `watchdog` ao `requirements.txt` e substituir polling por eventos
   - Adicionar `try/except` com logging nas funções críticas
   - Mover string `"Google Meet transcript"` para constante em `config.py`

2. **Médio prazo:**
   - Adicionar suite de testes para `merge_fragments()` e `process_section()`
   - Implementar log rotation (via `logging.handlers.RotatingFileHandler`)
   - Adicionar verificação de dependência do `gemini` CLI na inicialização

3. **Longo prazo:**
   - Criar systemd service para rodar em SP-Ubuntu como daemon
   - Criar script de instalação automática (Makefile ou shell script)
   - Adicionar suporte a outras fontes além do TranscripTonic

---

## 🔗 Referências
- [[Engineering/Projects/OCULUS]]
- [[daily/2026-05-27]]
- Repo: https://github.com/andersonsilvaviva/oculus
- TranscripTonic: https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag
- Gemini CLI: https://github.com/google/gemini-cli
