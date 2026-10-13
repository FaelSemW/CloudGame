# Instalação do HOST e clientes nativos

O pacote HOST atual inclui o serviço de controle, painel, isolamento QEMU/libvirt, provisionador automático de Ubuntu/Xfce/Steam/Sunshine e descarte das sessões. Sunshine é baixado da release oficial com SHA-256 fixado durante a preparação. Não é necessário copiar o pacote manualmente para a máquina.

## HOST Bazzite

Depois de preparar os pré-requisitos em [BAZZITE.md](BAZZITE.md), execute no terminal do Bazzite:

```sh
curl -fsSL https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.sh | sh
```

Para teste em VM sem GPU dedicada:

```sh
curl -fsSL https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.sh | sh -s -- --software
```

O instalador verifica a integridade, confere ferramentas, pede elevação administrativa, prepara a imagem e valida um novo boot antes de configurar os serviços. O perfil software transmite vídeo real usando CPU, com desempenho limitado. A VM de testes precisa ter memória e espaço suficientes para executar uma segunda VM; não equivale ao desempenho de um PC com GPU.

**Limites atuais:** ferramentas nativas libvirt/QEMU, Tailscale conectado e HTTPS da tailnet ainda precisam estar disponíveis previamente. A CLI recusa conflitos e preserva instalações existentes; não implementa atualização automática. Instalação em Bazzite, GPU física e convivência com políticas particulares de firewall continuam pendentes de homologação. O pipeline já comprovou provisionamento, streaming nativo Linux por CPU e descarte entre boots.

A imagem não inclui jogos nem credenciais Steam. Jogos autorizados são preparados na base persistente conforme BAZZITE.md; login do jogador acontece apenas na interface oficial da Steam dentro da sessão.

## Clientes

Windows e Linux incorporam o motor Moonlight no próprio executável. Android incorpora o core no APK. Windows e Ubuntu 24.04 estão na [release desktop preview 0.1](https://github.com/FaelSemW/CloudGame/releases/tag/v0.1.0-desktop-preview.1), com fontes correspondentes e checksums. O script `install.ps1` baixa essa versão pública e confere o hash antes de instalar. Android permanece nos artefatos de desenvolvimento e não faz parte desta release desktop.

O painel web do HOST administra contas e sessões; ele não é um player de vídeo. Os clientes nativos são os players.

## Verificação e recuperação

`python3 cloud-game.pyz verify` confere os arquivos internos. O checksum externo não é assinatura de autoria. `doctor --software` permite conferir o perfil de testes sem exigir KVM. Consulte [ACCEPTANCE.md](ACCEPTANCE.md) para homologação e [BAZZITE.md](BAZZITE.md) para recuperação. Uma limpeza incompleta mantém o HOST bloqueado.

O modo antigo `install --lab` permanece disponível somente para desenvolver o painel e não transmite jogos; não é o procedimento de instalação do produto.
