# Relatório de implementação

## Situação da entrega

**V1 ainda incompleta e não homologada.** Foi implementado um caminho real de controle e um backend Linux que chama libvirt/QEMU/nftables/Sunshine, sem streaming simulado. A execução disponível foi Windows, portanto o backend de hardware não pôde ser exercitado. Não foi transmitido um jogo nesta sessão de desenvolvimento.

## Inspeção inicial

Na inspeção inicial, `G:\New Cloud Game` estava vazia e Git foi inicializado. O código agora está versionado e publicado em https://github.com/FaelSemW/CloudGame. A autenticação de push foi concluída pelo proprietário.

Ferramentas confirmadas: Windows/PowerShell, Git, Node 22.23.3/npm 10.9.9 e runtime Python. JDK 21, Android SDK/NDK e Gradle foram preparados localmente e compilaram o APK. GitHub Actions disponibilizou Ubuntu 24.04/Qt e Windows/MSVC/Qt 6.12.0 para compilar os desktops. Não houve teste com GPU Bazzite nem aparelho Android. Por orientação do proprietário, não se controla a interface da máquina/VM pessoal.

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
- Clientes próprios nativos Android e Qt: autenticação HTTPS, consulta ao HOST, reserva, pareamento aprovado pela API e streaming através do motor Moonlight incorporado no mesmo APK/processo. Desktop oferece configurações nativas de vídeo, áudio e controles.
- Instalador Windows Inno Setup por usuário e pacote Ubuntu 24.04 `.deb`; pipeline de builds reais, teste de interface Linux e teste de instalação/inicialização/desinstalação Windows em runner descartável.
- Empacotador de fontes rastreados e submódulos fixos com overlays, manifesto de hashes e avisos; recusa submódulos divergentes e preserva permissões executáveis. Não inclui arquivos locais não rastreados.

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
| Nativos | `integrations/qt/`, `integrations/android/`, `tools/native_sources.py`, `tools/build-android.ps1` |
| Distribuição | `deploy/windows-client.iss`, `tools/package_linux.py`, `tools/source_bundle.py`, `install.ps1`, `.github/workflows/native-clients.yml` |
| Evidências nativas | `tools/smoke_desktop.py`, `tools/smoke_windows.ps1`, `tools/github_ci.py`, `docs/NATIVE-INTEGRATION.md` |

## Validação executada

23 testes Node e 20 testes Python aprovados, incluindo concorrência entre duas conexões SQLite, falhas de preparação/limpeza, ausência de confirmação explícita de descarte, reinício, limites de sessão, autenticação/revogação, proteção HTTP, rejeição de caminhos, IPs fora da rede, ausência de shares no XML, pareamento Sunshine por identificador e exclusão de arquivos privados do pacote de fontes. São testes com injeção de falhas; o backend de produção não possui modo fictício.

`npm run check` passou. O servidor real iniciou em loopback no Windows. APK Android debug, desktop Windows/instalador e desktop Linux/pacote compilaram na [execução 38226584427](https://github.com/FaelSemW/CloudGame/actions/runs/38226584427). O Linux abriu a interface em Xvfb. A inspeção do encerramento identificou um erro de lifetime do controlador QML; a correção passou no job Linux da [execução 38269256698](https://github.com/FaelSemW/CloudGame/actions/runs/38269256698). Alterações posteriores possuem seus próprios jobs e só devem ser consideradas validadas após conclusão. Não houve streaming real de jogo.

## Decisões e limitações relevantes

1. **VM inteira** em vez de diretório/home separado: protege o desktop do proprietário, com custo de RAM e necessidade de GPU dedicada. Não atende ainda instalação simples universal, sobretudo GPU única.
2. **Biblioteca dentro da base imutável**: jogos não são reinstalados por sessão. Patches/cache/saves locais são descartados; jogos que exigem grandes escritas ou anticheat incompatível devem ser restringidos.
3. **Moonlight incorporado**: os clientes nativos usam os projetos oficiais sem reimplementar codecs/protocolo; não exigem instalar outro Moonlight. A interface web anterior é somente controle e administração. O executável interno Windows ainda se chama `Moonlight.exe`, dentro da instalação Cloud Game.
4. **Tailscale + Serve**: sem portas administrativas públicas, mas depende de coordenação Tailscale e configuração correta da tailnet. Headscale/WireGuard são alternativas descritas, não recursos implementados.
5. **Bazzite não disponível**: instalador, systemd, SELinux, nft/firewalld, GPU reset e APIs Sunshine precisam ser homologados. Firewall pode bloquear encaminhamento até configuração específica; nenhuma regra global de segurança foi desativada para esconder isso.
6. **Licenças**: textos e obrigações registradas, inventário inicial dos submódulos. Auditoria de dependências transitivas e código correspondente é necessária antes de distribuir binários upstream ou imagem completa.

## Etapas restantes

Automatizar e homologar o provisionamento da imagem Linux limpa com Sunshine; preparar HOST com GPU dedicada/IOMMU; configurar Tailscale/HTTPS/firewalld; executar o roteiro ACCEPTANCE.md e corrigir incompatibilidades reais. Concluir avisos/fontes de runtimes redistribuídos, assinatura de produção Android e release pública com checksums. O bootstrap Windows consulta uma release que ainda não existe; não apresentar esse comando como instalador público funcionando. O bootstrap HOST anterior instala somente o controle e não entrega uma imagem de jogos pronta.

Os critérios de conclusão fornecidos pelo usuário continuam pendentes onde exigem instalação Bazzite, streaming Android/desktop real, isolamento em execução e descarte verificado em hardware. A aprovação dos testes de controle não encerra esses critérios.
