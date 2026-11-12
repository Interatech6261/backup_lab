# Guarda Arquivos Lab

Script para Windows que identifica arquivos nas pastas monitoradas e os
organiza em um compartilhamento de rede, usando a matrícula encontrada no nome
do item.

## Requisitos

- Windows
- Python 3
- Acesso ao compartilhamento de rede de destino

## Configuração

Na primeira execução, o programa cria automaticamente um arquivo local em
`%LOCALAPPDATA%\GuardaArquivosLab\config.json` (normalmente em
`C:\Users\<usuário>\AppData\Local\GuardaArquivosLab\config.json`) e abre a
configuração inicial das pastas. Depois de clicar em "Iniciar backup", as
opções são salvas. Nas próximas execuções, uma janela oferece os botões
"Iniciar backup", "Configurar pastas..." e "Sair".

Também é possível fechar o programa e editar esse JSON a qualquer momento. Por
exemplo, no PowerShell:

```powershell
notepad "$env:LOCALAPPDATA\GuardaArquivosLab\config.json"
```

Também é possível abrir diretamente a configuração das pastas com
`py backup_lab.py --configurar`. As alterações feitas no JSON são carregadas
na próxima execução. Não adicione uma senha ao arquivo: se `SENHA_REDE` estiver
vazio, ela será solicitada uma vez e armazenada no Gerenciador de Credenciais
do Windows, vinculada à conta atual. Mantenha `SENHA_REDE` vazio e não grave
senhas no código nem no arquivo de configuração.

## Execução

No Prompt de Comando ou PowerShell, na pasta do projeto:

```powershell
py backup_lab.py
```

### Executar diretamente pelo GitHub (PowerShell)

Com Python instalado, rode este comando para baixar a versão da branch `main`
e abrir o script:

```powershell
$url="https://raw.githubusercontent.com/Interatech6261/backup_lab/main/backup_lab.py"; $file="$env:TEMP\backup_lab.py"; Invoke-WebRequest -Uri $url -OutFile $file -ErrorAction Stop; if ($?) { py $file }
```

Na primeira execução, a janela pedirá as pastas e a senha da rede. Nas
execuções seguintes, escolha **Iniciar backup** ou **Configurar pastas...** na
janela inicial. Para abrir a configuração diretamente:

```powershell
py $file --configurar
```

O script abre a janela de configuração e inicia o backup ao clicar em
**Iniciar backup**. O comando baixa a cópia mais recente do GitHub, portanto
publique as alterações antes de executá-las dessa forma.

## Atenção

O script **move** os itens processados: copia-os para o destino e depois remove
a origem. Teste primeiro com arquivos descartáveis e confirme a configuração e
o compartilhamento de destino antes de executar em pastas com dados reais.
