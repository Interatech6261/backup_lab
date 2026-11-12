# Guarda Arquivos Lab

Script para Windows que identifica arquivos nas pastas monitoradas e os
organiza em um compartilhamento de rede, usando a matrícula encontrada no nome
do item.

## Requisitos

- Windows
- Python 3
- Acesso ao compartilhamento de rede de destino

## Configuração

O usuário de rede e os compartilhamentos de destino ficam predefinidos no
código. Na primeira execução, uma janela solicita a senha e a guarda no
Gerenciador de Credenciais do Windows, vinculada à conta atual do Windows.
Depois disso, a senha não precisa ser digitada novamente nesse computador.
Ela não é incluída no script nem enviada ao GitHub.

Em cada execução, uma janela solicita somente as pastas de origem. Use
"Adicionar pasta..." para selecionar pastas ou informe caminhos, um por linha.
Clique em "Iniciar backup" para executar; "Cancelar" fecha sem executar.

Para remover a senha salva, apague a credencial `GuardaArquivosLab/Interatech6261/backup_lab`
no Gerenciador de Credenciais do Windows. O endpoint opcional de logs continua
configurável na seção `CONFIG` no início do arquivo; use `None` para desabilitar
o envio remoto.

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

O script abre a janela de configuração e inicia o backup ao clicar em
**Iniciar backup**. O comando baixa a cópia mais recente do GitHub, portanto
publique as alterações antes de executá-las dessa forma.

## Atenção

O script **move** os itens processados: copia-os para o destino e depois remove
a origem. Teste primeiro com arquivos descartáveis e confirme a configuração e
o compartilhamento de destino antes de executar em pastas com dados reais.
