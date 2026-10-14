# Cloud Game

HOST Bazzite e clientes Android/desktop com integração dos projetos oficiais Sunshine e Moonlight, em desenvolvimento.

**Mudança em andamento: HOST nativo, sem VM.** O código atual prepara Sunshine/Steam em namespaces Linux e desktop separado, sem Ubuntu/QEMU/VFIO. O instalador público abaixo ainda pertence ao backend antigo; aguarde a atualização para testar o modo nativo. [Arquitetura, retomada e limitações do novo backend](docs/NATIVE-HOST.md). Gamepads, biblioteca Steam compartilhada e GPU física ainda não estão homologados neste modo.

**Estado: implementação em andamento, ainda não uma V1 homologada.** Os clientes Android, Windows e Linux compilaram e incorporam o motor Moonlight, sem exigir outro aplicativo Moonlight instalado. O HOST agora usa sessões nativas Linux. Instalação Bazzite, jogos, GPU física, controles e streaming Android exigem homologação. Consulte [integração dos clientes e evidências](docs/NATIVE-INTEGRATION.md) e [limites do HOST nativo](docs/NATIVE-HOST.md).

A pasta recebida estava vazia, sem Git ou código a preservar. Esta implementação inicializou o repositório e não substituiu um produto anterior.

## Instalar a versão desktop de testes

[Downloads: desktop preview 0.1](https://github.com/FaelSemW/CloudGame/releases/tag/v0.1.0-desktop-preview.1). Inclui instalador Windows com Moonlight incorporado, cliente Ubuntu 24.04, pacote HOST, checksums e fontes correspondentes. Os downloads públicos foram conferidos após a publicação.

Windows, no PowerShell:

```powershell
irm https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.ps1 | iex
```

HOST Bazzite em VM, no terminal do Bazzite:

```sh
curl -fsSL https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.sh | sh -s -- --software
```

Não execute o comando acima enquanto o aviso de atualização pendente estiver no topo. O novo perfil por CPU é para testes, sem VM adicional. O assistente instala dependências via rpm-ostree, salva progresso para reinício, cria atalhos no menu e na área de trabalho e orienta Tailscale/HTTPS. O atalho **Cloud Game HOST** abre o painel; **Cloud Game — continuar instalação** retoma o assistente. Para tentar o perfil de GPU nativa em hardware compatível, remova `--software`. Não inclui jogos.

A release é de testes, não homologação em Bazzite/GPU. Android continua nos artefatos de desenvolvimento e não integra esta release desktop. Instalações existentes são preservadas; não há atualização automática.

## Executar o controle local

Requer Node.js 22.13+ (testado com 22.23.3). Não há dependências npm externas nem etapa de compilação.

```sh
npm start
```

Abra `http://127.0.0.1:8787`, use o código de instalação impresso no terminal e crie a conta administrativa. No Windows, o HOST permanece **bloqueado** porque não pode criar o ambiente Bazzite. Isso não é um modo de streaming simulado. O banco local fica em `data/`, ignorado pelo Git.

```sh
npm test
npm run check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Arquitetura implementada

- **HOST:** serviço Node, SQLite, autenticação e painel administrativo integrado. Escuta somente em loopback; Tailscale Serve termina HTTPS na rede privada.
- **CLIENT:** aplicativos nativos Android e Qt para Windows/Linux, com autenticação, estado consultado a cada 2 segundos, reserva, pareamento e encerramento. Incorporam o código oficial Moonlight para vídeo/áudio/entrada. A interface web permanece como painel do HOST e alternativa de controle manual.
- **Isolamento:** usuário de serviço, namespaces bubblewrap, desktop privado e cgroup systemd. Sem VM, imagem Ubuntu ou VFIO. Home/runtime temporários em tmpfs, sem swap em disco. Diretórios pessoais do proprietário não são compartilhados.
- **Controle privilegiado:** helper Python de operações fixas, UUIDs gerados no servidor, bloqueio entre processos e nftables limitando streaming a um IPv4 Tailscale autorizado.
- **Limpeza:** revoga tráfego, encerra processos do cgroup, verifica namespace e arquivos temporários e mantém bloqueio em qualquer falha. Watchdog independente impõe prazo máximo.

Não há serviços de cobrança, nuvem obrigatória de processamento, banco remoto ou microserviços. Tailscale utiliza seu serviço de coordenação; alternativa autogerida e suas limitações estão documentadas.

## Documentação

- [Instalação, isolamento, rede, recuperação e limites nativos](docs/NATIVE-HOST.md)
- [Licenças e distribuição](docs/LICENSES.md)
- [Relatório, arquivos e evidências](docs/REPORT.md)
- [Roteiro de homologação em hardware real](docs/ACCEPTANCE.md)

O backend nativo não exige uma segunda GPU. Isso não comprova compatibilidade de todos os drivers: GPU física, entrada e biblioteca compartilhada continuam pendentes. Não implante para jogadores não confiáveis antes da homologação de isolamento, firewall e recuperação.
