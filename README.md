# Cloud Game

HOST Bazzite + CLIENT web responsivo para Android/Windows/Linux, com Sunshine e Moonlight oficiais como componentes de streaming externos.

**Estado: implementação inicial, ainda não uma V1 homologada.** O controle local funciona e tem testes automatizados. O caminho Linux de VM/GPU/rede está implementado, mas não foi executado em Bazzite. Não há APK, executável nativo próprio nem decoder Moonlight incorporado. O cliente abre instruções de conexão no Moonlight externo, explicitamente.

A pasta recebida estava vazia, sem Git ou código a preservar. Esta implementação inicializou o repositório e não substituiu um produto anterior.

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
- **CLIENT:** a mesma interface responsiva, com autenticação, estado consultado a cada 2 segundos, reserva, pareamento e encerramento. Usa Moonlight oficial externo para vídeo/áudio/entrada.
- **Isolamento:** VM KVM/QEMU Linux com GPU dedicada via VFIO. Disco qcow2 temporário sobre imagem-base somente leitura. Nenhuma pasta ou disco pessoal compartilhado. Escritas da sessão em tmpfs sem swap.
- **Controle privilegiado:** helper Python de operações fixas, UUIDs gerados no servidor, bloqueio entre processos e nftables limitando streaming a um IPv4 Tailscale autorizado.
- **Limpeza:** revoga tráfego, encerra VM, verifica ausência do QEMU, remove somente os arquivos esperados e mantém bloqueio em qualquer falha. Watchdog independente impõe prazo máximo.

Não há serviços de cobrança, nuvem obrigatória de processamento, banco remoto ou microserviços. Tailscale utiliza seu serviço de coordenação; alternativa autogerida e suas limitações estão documentadas.

## Documentação

- [Instalação, imagem de jogos, rede e recuperação no Bazzite](docs/BAZZITE.md)
- [Modelo de segurança e limites](docs/SECURITY.md)
- [Licenças e distribuição](docs/LICENSES.md)
- [Relatório, arquivos e evidências](docs/REPORT.md)
- [Roteiro de homologação em hardware real](docs/ACCEPTANCE.md)

O requisito de simplicidade para máquina com uma única GPU ainda não foi resolvido. Não implante para jogadores não confiáveis antes da homologação de isolamento, firewall e recuperação descrita no roteiro.
