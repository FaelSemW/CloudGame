# Relatório de implementação

## Situação da entrega

**V1 ainda incompleta e não homologada.** Foi implementado um caminho real de controle e um backend Linux que chama libvirt/QEMU/nftables/Sunshine, sem streaming simulado. A execução disponível foi Windows, portanto o backend de hardware não pôde ser exercitado. Não foi transmitido um jogo nesta sessão de desenvolvimento.

## Inspeção inicial

`G:\New Cloud Game` estava vazia; `git status` confirmou ausência de repositório. Não existiam configurações, dependências, licenças ou funcionalidades a preservar. Git foi inicializado, sem criar commits ou publicar remotamente.

Ferramentas confirmadas: Windows/PowerShell, Git, Node 22.23.3/npm 10.9.9, SQLite 3.51.3 embutido. WSL informou não estar instalado. Nenhum SDK .NET foi listado; Java/ADB, Python global, Go e Cargo não foram encontrados no PATH pesquisado. Um runtime Python fornecido pelo ambiente Codex foi usado apenas para análise sintática e testes portáveis. Não há evidência de GPU Bazzite, Qt/C++ toolchain, SDK/NDK Android ou aparelho Android acessível.

## Implementado

- Contas administrativas/jogadores, setup de uso único, hashes scrypt, tokens revogáveis, throttle persistido de login e API pequena autenticada.
- Estado exclusivo persistido em SQLite; rejeição de outra reserva; retomada idempotente da própria sessão; separação de preparação, pronto, streaming, reconexão, limpeza e bloqueio.
- Painel do HOST integrado ao cliente responsivo, criação/desativação de jogadores, troca de senha de jogador, diagnósticos e auditoria.
- Adaptador root restrito, sem shell remoto, com lock e operações enumeradas; XML de domínio gerado internamente, sem caminhos fornecidos pelo jogador.
- VM transient com overlay qcow2 em tmpfs sobre base protegida, GPU/áudio via VFIO, verificações de IOMMU/ACS/swap, sem pastas do proprietário.
- Regras nftables limitadas à própria tabela; streaming encaminhado ao peer Tailscale autorizado, sem encaminhar administração Sunshine.
- Helper interno que consulta Sunshine real, envia PIN pela API local e usa journal da invocação corrente para monitorar conexões.
- Limpeza fail-closed: revogar rede, destruir VM, conferir processos e arquivos; novas sessões bloqueadas em erro. Recuperação no restart e watchdog root independente.
- Instalador HOST com lançador gráfico opcional, systemd/SELinux paths e runtime Node oficial verificado por checksum; provisionador de guest que preserva configurações existentes.
- Documentação de implantação, licenças, ameaças e testes em hardware.

## Arquivos criados

| Área | Arquivos |
|---|---|
| Serviço | `host/server.mjs`, `host/store.mjs`, `host/sessions.mjs`, `host/backend.mjs` |
| Cliente | `client/index.html`, `client/app.js`, `client/style.css`, `client/manifest.webmanifest`, `client/icon.svg` |
| Virtualização | `deploy/vm_helper.py`, `deploy/vm.example.json`, `deploy/network_setup.py` |
| Guest/Sunshine | `deploy/prepare_guest.py`, `deploy/cloud-game-guest`, `deploy/cloud-game-sunshine.service`, `deploy/sunshine.conf`, `deploy/apps.json` |
| Instalação/boot | `deploy/install_host.py`, `deploy/install-gui.py`, unidades `deploy/cloud-game*.service`, `deploy/cloud-game-watchdog.timer`, `deploy/var-lib-cloudgame-volatile.mount` |
| Testes | `tests/control.test.mjs`, `tests/test_vm_helper.py` |
| Licenças/docs | `LICENSE`, `licenses/*`, `README.md`, `docs/BAZZITE.md`, `docs/SECURITY.md`, `docs/LICENSES.md`, `docs/ACCEPTANCE.md`, este relatório |
| Projeto | `package.json`, `package-lock.json`, `.gitignore`, `.gitattributes` |

## Validação executada

22 testes Node aprovados, incluindo concorrência entre duas conexões SQLite, falhas de preparação/limpeza, ausência de confirmação explícita de descarte, verificação do HOST ocioso, reinício, limite absoluto, desconexão, pareamento, autenticação/revogação e proteção HTTP. 11 testes Python de política aprovados, incluindo rejeição de caminhos, IPs fora da rede, ausência de shares no XML e fechamento de firewall antes de descarte. São testes com injeção de falhas; o backend de produção não possui modo fictício.

`npm run check` passou. `py_compile` foi executado nos scripts Python. `npm start` iniciou o servidor real em loopback no Windows. A interface de primeira configuração foi inspecionada no navegador em largura de desktop e celular; nenhuma rolagem horizontal foi detectada. Não foi validada uma sessão de streaming pela UI, nem um APK/EXE compilado.

## Decisões e limitações relevantes

1. **VM inteira** em vez de diretório/home separado: protege o desktop do proprietário, com custo de RAM e necessidade de GPU dedicada. Não atende ainda instalação simples universal, sobretudo GPU única.
2. **Biblioteca dentro da base imutável**: jogos não são reinstalados por sessão. Patches/cache/saves locais são descartados; jogos que exigem grandes escritas ou anticheat incompatível devem ser restringidos.
3. **Moonlight externo**: a integração nativa foi avaliada e não implementada. O produto possui HOST e cliente web de controle, mas ainda requer instalar o aplicativo Moonlight separadamente. Não há vídeo no navegador, APK/EXE próprio ou abertura automática garantida do Moonlight.
4. **Tailscale + Serve**: sem portas administrativas públicas, mas depende de coordenação Tailscale e configuração correta da tailnet. Headscale/WireGuard são alternativas descritas, não recursos implementados.
5. **Bazzite não disponível**: instalador, systemd, SELinux, nft/firewalld, GPU reset e APIs Sunshine precisam ser homologados. Firewall pode bloquear encaminhamento até configuração específica; nenhuma regra global de segurança foi desativada para esconder isso.
6. **Licenças**: textos e obrigações registradas, inventário inicial dos submódulos. Auditoria de dependências transitivas e código correspondente é necessária antes de distribuir binários upstream ou imagem completa.

## Etapas restantes

Preparar HOST com duas GPUs/virtualização, criar imagem Linux limpa com Sunshine e jogos autorizados, configurar Tailscale/HTTPS/firewalld, instalar e executar o roteiro completo ACCEPTANCE.md. Depois corrigir incompatibilidades observadas, empacotar e simplificar a instalação. Integração nativa Android/Qt e distribuição assinada são trabalho adicional, não funcionalidades já entregues.

Os critérios de conclusão fornecidos pelo usuário continuam pendentes onde exigem instalação Bazzite, streaming Android/desktop real, isolamento em execução e descarte verificado em hardware. A aprovação dos testes de controle não encerra esses critérios.
