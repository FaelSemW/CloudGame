# Distribuição pela internet

Destino autorizado: https://github.com/FaelSemW/CloudGame.

O instalador é gerado por `tools/release.py` para uma URL HTTPS concreta e incorpora o SHA-256 do pacote. Baixa para diretório temporário privado, verifica integridade, executa diagnóstico e só então solicita a elevação necessária para instalar o HOST. Não entra automaticamente no modo laboratório. Não modifica configurações para ocultar incompatibilidades.

Gerar e preparar uma distribuição:

```sh
python3 tools/package.py
python3 tools/release.py --base-url https://raw.githubusercontent.com/FaelSemW/CloudGame/main/downloads
```

Publicar `dist/cloud-game.pyz` em `downloads/cloud-game.pyz` e `dist/install.sh` em `install.sh`. Antes de anunciar o comando, verificar o conteúdo servido pelo GitHub. A URL usa HTTPS; o hash identifica o pacote exato, mas não substitui assinatura independente do distribuidor. O proprietário do repositório controla o script inicial.

O pipeline verifica código e produz o artefato de avaliação. Isso **não** significa release completa aprovada: clientes nativos e streaming em Bazzite ainda pendem de compilação e homologação. Não anunciar como instalador completo enquanto os critérios de ACCEPTANCE não forem cumpridos.
