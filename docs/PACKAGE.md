# Pacote de avaliação 0.1

Este pacote instala o controle HOST e sua interface web. **Não é a V1 completa:** não contém APK, cliente Windows nativo ou Moonlight embutido compilado. Streaming e descarte via GPU ainda precisam de homologação em hardware. Não use para disponibilizar acesso a terceiros antes dessa validação.

## Testar agora no Bazzite em VirtualBox

Copie `cloud-game.pyz` para Downloads dentro do Bazzite. Abra um terminal nessa pasta e execute, como usuário comum:

```sh
python3 cloud-game.pyz install --lab
```

O comando verifica o pacote, baixa Node oficial (internet necessária), preserva a licença, instala em `~/.local/share/cloud-game-lab` e inicia o servidor. Abra **http://127.0.0.1:8787**, informe o código mostrado no terminal e crie seu administrador. A senha é da plataforma, nunca da Steam. É possível testar login, administração de usuários e registros. O estado bloqueado é esperado: laboratório não executa sessões nem simula streaming.

Mantenha o terminal aberto. Ctrl+C encerra o servidor. Nas próximas vezes:

```sh
python3 cloud-game.pyz run
```

Dados e contas persistem na pasta `data` da instalação. Reinstalações são recusadas para preservar dados. O modo laboratório não configura inicialização automática, rede privada ou privilégios administrativos.

## HOST de produção — preparação obrigatória

```sh
python3 cloud-game.pyz doctor
sudo python3 cloud-game.pyz install
```

Antes, siga `docs/BAZZITE.md` no projeto: libvirt/KVM, GPU dedicada com IOMMU/VFIO, imagem-base limpa com Sunshine, Tailscale e ferramentas do sistema. O instalador não consegue transformar a GPU virtual do VirtualBox em GPU dedicada nem preparar automaticamente uma imagem de jogos licenciados. Pré-requisitos ausentes interrompem a instalação; não há fallback inseguro para o desktop do proprietário. O serviço de produção possui inicialização automática, mas permanece bloqueado até a preparação e verificação da imagem. Falhas parciais preservam arquivos e exigem revisão administrativa.

## Verificação

`python3 cloud-game.pyz verify` verifica todos os arquivos internos. O SHA-256 externo está em `SHA256SUMS`; não é uma assinatura de autoria. `doctor` retorna código 2 quando faltam pré-requisitos. O pacote não publica portas na internet nem usa serviços pagos. Para homologação use `docs/ACCEPTANCE.md`.
