# Rede privada no cliente desktop

O instalador Windows prepara o serviço oficial Tailscale quando ele não está instalado. O MSI é baixado do servidor oficial, com SHA-256 fixado e assinatura Authenticode verificada. A autorização administrativa aparece pelo Windows. O Moonlight está incorporado no executável Cloud Game; o Tailscale é um serviço separado instalado pelo mesmo procedimento, não uma implementação de VPN dentro do executável.

O instalador `deploy/install_client_linux.py` atende Ubuntu 24.04 x86_64: verifica o pacote Cloud Game, adiciona o repositório oficial Tailscale com chave de assinatura verificada, instala os dois componentes e inicia `tailscaled`. Não é um pacote CLIENT para Bazzite ou outras distribuições. O HOST Bazzite usa `install.sh`.

## Autorizar e jogar

1. Abra Cloud Game e clique em **Conectar rede privada**. Autorize o dispositivo no navegador oficial. No Ubuntu, o sistema pede autorização administrativa para executar o comando fixo Tailscale.
2. Use a rede que contém o HOST, ou um compartilhamento autorizado pelo administrador. Duas contas Tailscale independentes não conectam as máquinas automaticamente.
3. Clique em **Verificar rede**. O aplicativo consulta o serviço local e mostra o IPv4 do dispositivo. `Running` comprova a conexão local à rede, não o acesso ao HOST ou ao Sunshine.
4. No painel administrativo do HOST, cadastre esse IPv4 no usuário do jogador. A regra de streaming permite somente o endereço autorizado para a sessão. Cadastrar o IP do HOST nesse campo impede o jogador de acessar o Sunshine.
5. Informe o HTTPS privado do HOST e as credenciais Cloud Game, prepare uma sessão e clique em **Jogar / Reconectar**.

O serviço Tailscale mantém o estado de autorização no armazenamento próprio. O Cloud Game não coleta a senha Tailscale, não instala chaves genéricas e não altera a rede de uma instalação existente automaticamente. Se o login demorar mais que o prazo da interface, conclua no navegador e use **Verificar rede** novamente.

Uma chave de cadastro não é uma licença permanente: sua expiração e a expiração das chaves dos dispositivos são independentes. Nunca publique uma chave reutilizável em um cliente distribuído. Revogue no painel Tailscale qualquer chave compartilhada por mensagem. Fontes oficiais: [auth keys](https://tailscale.com/docs/features/access-control/auth-keys), [instalação MSI](https://tailscale.com/docs/install/windows/msi) e [modo unattended](https://tailscale.com/docs/how-to/run-unattended).

## Conexão sem imagem

O cliente verifica a porta de descoberta do Sunshine antes do pareamento. Quando o painel responde mas essa porta não responde, revise o IPv4 autorizado, as regras Tailscale e o firewall do HOST. O teste TCP não comprova transporte UDP, codificação ou decodificação de vídeo.

Cada sessão descartável cria uma identidade Sunshine nova. Antes do primeiro pareamento da sessão, o cliente remove apenas a entrada Moonlight em cache associada ao IP desse HOST autenticado e aguarda a remoção antes de redescobrir. Na reconexão de uma sessão já pareada, conserva a identidade. Pareamento e abertura do desktop têm prazos e mensagens de erro; a consulta periódica não apaga mais o erro da conexão.

Se a tela de transmissão abrir mas não produzir imagem, registre o erro do Moonlight e consulte o diagnóstico do HOST. A instalação da rede não resolve incompatibilidade de GPU/captura. O perfil HOST `--software` serve para teste por CPU; não comprova desempenho em jogos. Gamepads no HOST nativo e GPU física ainda dependem de homologação.

## Distribuição e limites

O MSI Tailscale é obtido do fornecedor durante a instalação, não reempacotado no executável. As licenças, políticas e avisos do fornecedor continuam aplicáveis. Desinstalar Cloud Game preserva o serviço e as configurações Tailscale, que podem ser usados por outros aplicativos; a remoção da rede é feita separadamente nas configurações do sistema.

Esta integração atende o desktop Windows e Ubuntu. O APK Android atual não contém a VPN Tailscale e ainda exige configuração externa da rede; não apresentar esta alteração como integração Android concluída. Testes de instalação em CI não substituem login autorizado, teste de vídeo pela rede privada e homologação no hardware do jogador.
