# Instalação do HOST e clientes nativos

O novo pacote HOST inclui controle, painel, sessões nativas bubblewrap, Sunshine/Steam e descarte temporário. Não instala VM, Ubuntu ou QEMU. Sunshine é baixado da release oficial em RPM com SHA-256 fixado. Não é necessário copiar o pacote para a máquina. Confira no README se a publicação do pacote nativo já foi concluída antes de usar o comando.

## HOST Bazzite

Execute no terminal do Bazzite; o [assistente guiado](SETUP.md) prepara as dependências:

```sh
curl -fsSL https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.sh | sh
```

Para teste em VM sem GPU dedicada:

```sh
curl -fsSL https://raw.githubusercontent.com/FaelSemW/CloudGame/main/install.sh | sh -s -- --software
```

O instalador verifica integridade, confere ferramentas, pede elevação e configura os serviços nativos. O perfil software transmite vídeo real por CPU, com desempenho limitado. Dentro de uma VM Bazzite existente ele não cria outra VM. Esse teste não equivale ao desempenho de um PC com GPU.

**Fluxo guiado:** dependências ausentes via rpm-ostree; reinício com progresso salvo e retomada pelo menu. Tailscale pede autorização no navegador e o assistente orienta MagicDNS/HTTPS. O atalho **Cloud Game HOST** abre o painel pela busca do menu/Super ou área de trabalho. Configurações conflitantes são preservadas; não há migração automática de um HOST VM já instalado. Bazzite, GPU física e firewall real continuam pendentes de homologação.

Não inclui jogos nem credenciais Steam. Login acontece pela interface oficial da Steam. Gamepads e importação transparente da biblioteca persistente ainda não estão implementados no novo backend; veja [limitações nativas](NATIVE-HOST.md).

## Clientes

Windows e Linux incorporam o motor Moonlight no próprio executável. Android incorpora o core no APK. Windows e Ubuntu 24.04 estão na [release desktop preview 0.1](https://github.com/FaelSemW/CloudGame/releases/tag/v0.1.0-desktop-preview.1), com fontes correspondentes e checksums. O script `install.ps1` baixa essa versão pública e confere o hash antes de instalar. Android permanece nos artefatos de desenvolvimento e não faz parte desta release desktop.

O painel web do HOST administra contas e sessões; ele não é um player de vídeo. Os clientes nativos são os players.

## Verificação e recuperação

`python3 cloud-game.pyz verify` confere arquivos internos. O checksum externo não é assinatura de autoria. `doctor --software` confere ferramentas nativas; KVM não é necessário. Consulte [NATIVE-HOST.md](NATIVE-HOST.md) para diagnóstico e retomada. Limpeza incompleta mantém o HOST bloqueado.

O modo antigo `install --lab` permanece disponível somente para desenvolver o painel e não transmite jogos; não é o procedimento de instalação do produto.
