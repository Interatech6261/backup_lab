# Guarda Arquivos Lab

Script para Windows que identifica arquivos nas pastas monitoradas e os
organiza em um compartilhamento de rede, usando a matrícula encontrada no nome
do item.

## Requisitos

- Windows
- Python 3
- Acesso ao compartilhamento de rede de destino

## Configuração

Ao iniciar, uma janela solicita:

- usuário e senha do compartilhamento (a senha não aparece enquanto é digitada);
- um ou mais caminhos de destino na rede (também é possível usar o seletor);
- uma ou mais pastas de origem (também é possível selecioná-las).

Informe caminhos adicionais um por linha. Esses dados são solicitados
novamente em cada execução e não são gravados pelo script. Ao clicar em
"Iniciar backup", a rotina começa; fechar a janela ou clicar em "Cancelar"
encerra sem executar. O endpoint opcional de logs continua configurável na
seção `CONFIG` no início do arquivo; use `None` para desabilitar o envio remoto.

## Execução

No Prompt de Comando ou PowerShell, na pasta do projeto:

```powershell
py backup_lab.py
```

## Atenção

O script **move** os itens processados: copia-os para o destino e depois remove
a origem. Teste primeiro com arquivos descartáveis e confirme a configuração e
o compartilhamento de destino antes de executar em pastas com dados reais.
